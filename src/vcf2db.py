#!/usr/bin/env python3
# ---------------------------------------------------------------------------------------
# Application to read a one sample or multi-sample VCF file and save it to a postgres DB
#
# Author: Donald Friggieri
# email: dfriggieri@gmail.com
# ---------------------------------------------------------------------------------------

import psycopg2
from psycopg2.pool import SimpleConnectionPool
from multiprocessing import Pool, cpu_count
from cyvcf2 import VCF
from app_args import setup_args, validate_arguments
from timeit import default_timer as timer


def create_database(dbname, user, password, host):
    print("Creating database...")
    conn = psycopg2.connect(dbname='postgres', user=user, password=password, host=host)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("DROP DATABASE IF EXISTS " + dbname)
    cur.execute("CREATE DATABASE " + dbname)
    cur.close()
    conn.close()


def create_tables(csq_fields, dbname, user, password, host):
    print("Creating tables...")
    conn = psycopg2.connect(dbname=dbname, user=user, password=password, host=host)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE samples (
            id SERIAL PRIMARY KEY,
            sample_name VARCHAR(255) UNIQUE NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE variants_partitioned (
            id SERIAL,
            chromosome VARCHAR(10) NOT NULL,
            position INTEGER NOT NULL,
            ref VARCHAR(255) NOT NULL,
            quality FLOAT,
            filter VARCHAR(255),
            PRIMARY KEY (chromosome, position, id)
        ) PARTITION BY RANGE (chromosome, position)
    """)

    for chromosome in range(1, 23):
        cur.execute(f"""
            CREATE TABLE variants_chr{chromosome} PARTITION OF variants_partitioned
            FOR VALUES FROM ('chr{chromosome}', 0) TO ('chr{chromosome}', 250000000)
        """)

    cur.execute("""
        CREATE TABLE variants_chrX PARTITION OF variants_partitioned
        FOR VALUES FROM ('chrX', 0) TO ('chrX', 250000000)
    """)

    cur.execute("""
        CREATE TABLE variants_chrY PARTITION OF variants_partitioned
        FOR VALUES FROM ('chrY', 0) TO ('chrY', 250000000)
    """)

    cur.execute("""
        CREATE TABLE alts (
            id SERIAL PRIMARY KEY,
            variant_chromosome VARCHAR(10) NOT NULL,
            variant_position INTEGER NOT NULL,
            variant_id INTEGER NOT NULL,
            alt VARCHAR(255) NOT NULL,
            FOREIGN KEY (variant_chromosome, variant_position, variant_id) REFERENCES variants_partitioned (chromosome, position, id) ON DELETE CASCADE
        )
    """)

    annotation_columns = ", ".join([f"{field} TEXT" for field in csq_fields])
    cur.execute(f"""
        CREATE TABLE annotations (
            id SERIAL PRIMARY KEY,
            {annotation_columns}
        )
    """)

    cur.execute("""
        CREATE TABLE variant_annotations (
            id SERIAL PRIMARY KEY,
            alt_id INTEGER NOT NULL,
            annotation_id INTEGER NOT NULL,
            FOREIGN KEY (alt_id) REFERENCES alts (id) ON DELETE CASCADE,
            FOREIGN KEY (annotation_id) REFERENCES annotations (id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE genotypes (
            id SERIAL PRIMARY KEY,
            alt_id INTEGER NOT NULL,
            sample_id INTEGER NOT NULL,
            genotype VARCHAR(255),
            dp INTEGER,
            gq INTEGER,
            ad JSONB,
            pl JSONB,
            FOREIGN KEY (alt_id) REFERENCES alts (id) ON DELETE CASCADE,
            FOREIGN KEY (sample_id) REFERENCES samples (id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE sample_relationships (
            id SERIAL PRIMARY KEY,
            sample_id1 INTEGER NOT NULL,
            sample_id2 INTEGER NOT NULL,
            relationship VARCHAR(255) NOT NULL,
            FOREIGN KEY (sample_id1) REFERENCES samples (id) ON DELETE CASCADE,
            FOREIGN KEY (sample_id2) REFERENCES samples (id) ON DELETE CASCADE,
            UNIQUE(sample_id1, sample_id2)
        )
    """)

    conn.commit()
    cur.close()
    conn.close()


def get_csq_fields(vcf_reader):
    info_header = vcf_reader.raw_header.split("##INFO=<ID=CSQ")[1].split("Format: ")[1].split('">')[0]
    csq_fields = info_header.split('|')
    return csq_fields


def create_sample(cur, sample_name):
    cur.execute("INSERT INTO samples (sample_name) VALUES (%s) RETURNING id", (sample_name,))
    return cur.fetchone()[0]


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
        INSERT INTO genotypes (alt_id, sample_id, genotype, dp, gq, ad, pl)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
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

            csq_annotations = variant.INFO.get('CSQ', '').split(',')
            for csq in csq_annotations:
                annotation_values = csq.split('|')
                cur.execute(annotation_insert_query, annotation_values)
                annotation_id = cur.fetchone()[0]
                cur.execute(variant_annotation_insert_query, (alt_id, annotation_id))

            for sample in sample_ids.keys():
                sample_id = sample_ids[sample]
                gt = variant.genotypes[sample_id-1]
                gt_string = '/' if gt[2] is False else '|'.join(map(str, gt[:2]))  # Genotype
                dp, gq, ad, pl = 0, 0, None, None
                genotype_data.append((alt_id, sample_id, gt_string, dp, gq, ad, pl))

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

    batch_size = args.batch
    num_variants = sum(1 for _ in VCF(args.input))
    num_batches = (num_variants + batch_size - 1) // batch_size
    print(f"Variants to process: {num_variants}. Batches to process: {num_batches}.")

    conn_params = {
        'dbname': args.database,
        'user': args.username,
        'password': args.password,
        'host': args.host
    }

    pool_args = [(args.input, index, batch_size, sample_ids, conn_params, csq_fields) for index in range(num_batches)]

    start = timer()
    with Pool((cpu_count() * 2) // 3) as pool:
        pool.starmap(process_batch, pool_args)
    print(f"Elapsed time to process batches: {timer() - start}")


if __name__ == "__main__":
    main()
