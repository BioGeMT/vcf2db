#!/usr/bin/env python3
# ---------------------------------------------------------------------------------------
# Application to read one sample or multi-sample VCF file and save it to a postgres DB
#
# Author: Donald Friggieri
# email: dfriggieri@gmail.com
# ---------------------------------------------------------------------------------------

import os
import json
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from multiprocessing import Pool
from cyvcf2 import VCF
from timeit import default_timer as timer

from app_args import setup_args, validate_arguments
from utils.vcfutils import get_csq_fields, map_genotype
from utils.dbutils import create_database, create_tables, create_sample
from utils.fileutils import delete_file, thread_safe_write_to_file

err_annotation_filename = 'annotation_errors.txt'


def process_batch(vcf_filepath, batch_index, batch_size, sample_ids, conn_params, csq_fields):
    conn_pool = SimpleConnectionPool(1, 10, **conn_params)
    conn = conn_pool.getconn()
    cur = conn.cursor()

    vcf_reader = VCF(vcf_filepath)
    variants_batch = [variant for i, variant in enumerate(vcf_reader) if i // batch_size == batch_index]

    variant_insert_query = """
        INSERT INTO variants_partitioned (chromosome, position, ref, quality, filter)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    """
    alt_insert_query = """
        INSERT INTO alts (variant_chromosome, variant_position, variant_id, alt)
        VALUES (%s, %s, %s, %s)
        RETURNING id
    """

    if len(csq_fields) != 0:
        annotation_insert_query = """
            INSERT INTO annotations ({})
            VALUES ({})
            RETURNING id
        """.format(", ".join(csq_fields), ", ".join(["%s"] * len(csq_fields)))
        variant_annotation_insert_query = """
            INSERT INTO variant_annotations (alt_id, annotation_id)
            VALUES (%s, %s)
        """

    genotype_insert_query = """
        INSERT INTO genotypes (alt_id, sample_id, genotype, genotype_hr, is_phased, dp, gq, ad, pl)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    variant_ids = []
    for variant in variants_batch:
        cur.execute(variant_insert_query, (variant.CHROM, variant.POS, variant.REF, variant.QUAL, variant.FILTER))
        variant_ids.append((cur.fetchone()[0], variant.CHROM, variant.POS))

    genotype_data = []

    for idx, variant in enumerate(variants_batch):
        variant_id, chromosome, position = variant_ids[idx]
        for alt in variant.ALT:
            cur.execute(alt_insert_query, (variant.CHROM, variant.POS, variant_id, alt))
            alt_id = cur.fetchone()[0]

            if len(csq_fields) != 0:
                csq_annotations = variant.INFO.get('CSQ', '').split(',')
                for csq in csq_annotations:
                    annotation_values = csq.split('|')
                    try:
                        cur.execute(annotation_insert_query, annotation_values)
                        annotation_id = cur.fetchone()[0]
                        cur.execute(variant_annotation_insert_query, (alt_id, annotation_id))
                    except:
                        thread_safe_write_to_file(err_annotation_filename,
                                                  f"error - annotation: variantId: {variant_id}, Chromosome: {chromosome}, Position: {position}, Annotation: {csq}")

            variant_format = variant.FORMAT
            for sample in sample_ids.keys():
                sample_id = sample_ids[sample]

                # Get genotype for sample
                gt = variant.genotypes[sample_id - 1]
                # Old style genotype reporting for diploid chromosomes (eg. chr Y)
                if len(gt) == 2:
                    gt_string = str(gt[0]) if gt[0] != -1 else '.'
                    is_phased = gt[1]
                else:
                    gt_string = '/'.join(map(str, gt[:2])) if gt[2] is False else '|'.join(map(str, gt[:2]))  # Genotype
                    gt_string = gt_string if gt_string != '-1/-1' else './.'
                    is_phased = gt[2]

                dp = 0; gq = 0; ad = None; pl = None
                try:
                    dp = int(variant.gt_depths[sample_id - 1]) if 'DP' in variant_format else 0  # Depth
                    gq = int(variant.gt_quals[sample_id - 1]) if 'GQ' in variant_format else 0  # Genotype Quality
                    ad = {'gt_ref_depths': int(variant.gt_ref_depths[sample_id - 1]),
                          'gt_alt_depths': int(variant.gt_alt_depths[sample_id - 1])} if 'AD' in variant_format else None
                    pl = {'gt_phred_ll_homref': int(variant.gt_phred_ll_homref[sample_id - 1]),
                          'gt_phred_ll_het': int(variant.gt_phred_ll_het[sample_id - 1]),
                        'gt_phred_ll_homalt': int(variant.gt_phred_ll_homalt[sample_id - 1])} if 'PL' in variant_format else None
                except IndexError:
                    thread_safe_write_to_file(err_annotation_filename,
                                              f"error - format: variantId: {variant_id}, Chromosome: {chromosome}, Position: {position}, Sample: {sample}")

                genotype_data.append((alt_id, sample_id, gt_string, map_genotype(gt_string), is_phased, dp, gq,
                                      json.dumps(ad), json.dumps(pl)))

    cur.executemany(genotype_insert_query, genotype_data)

    conn.commit()
    cur.close()
    conn_pool.putconn(conn)
    conn_pool.closeall()

    print(f"Batch {batch_index} processed.")


def main():
    # Setup and read the arguments which the application is able to accept
    args = setup_args()

    # Validate input and output arguments and exit if an error is encountered
    if validate_arguments(args) != 0:
        exit(1)

    # Delete annotations log file
    delete_file(err_annotation_filename)

    if args.create is True:
        create_database(args.database, args.username, args.password, args.host)

    vcf_reader = VCF(args.input)
    csq_fields = get_csq_fields(vcf_reader)
    create_tables(csq_fields, args.database, args.username, args.password, args.host)

    conn = psycopg2.connect(dbname=args.database, user=args.username, password=args.password, host=args.host)
    cur = conn.cursor()

    samples = vcf_reader.samples
    sample_ids = {sample: create_sample(cur, sample) for sample in samples}

    conn.commit()
    cur.close()
    conn.close()

    print("Calculating number of variants and batches for processing...")
    batch_size = args.batch
    num_variants = sum(1 for _ in VCF(args.input))
    num_batches = (num_variants + batch_size - 1) // batch_size
    print(f"Variants to process: {num_variants}. Batches to process: {num_batches}.")

    conn_params = {
        'dbname': args.database,
        'user': args.username,
        'password': args.password,
        'host': args.host,
        'keepalives': 1,
        'keepalives_idle': 30,
        'keepalives_interval': 5,
        'keepalives_count': 5
    }

    pool_args = [(args.input, index, batch_size, sample_ids, conn_params, csq_fields) for index in range(num_batches)]

    start = timer()
    with Pool(args.cores) as pool:
        pool.starmap(process_batch, pool_args)
    print(f"Elapsed time to process batches: {timer() - start}")
    print("Variant processing ready!\n")
    if os.path.exists(err_annotation_filename):
        print(f'Warning: Errors where encountered during processing and were written to \'{err_annotation_filename}\'!')


if __name__ == "__main__":
    main()
