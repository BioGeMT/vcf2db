#!/usr/bin/env python3
"""
Generate a mock VCF file with 100 variants per chromosome (1-22, X, Y)
for testing the vcf2db.py application.
"""

import random

# Define common gene symbols for each chromosome
CHROMOSOME_GENES = {
    "1": ["WASH7P", "DDX11L1", "MIR6859-1", "OR4F5", "OR4F16"],
    "2": ["PXDN", "MYT1L", "TPO", "COLEC11", "ADI1"],
    "3": ["CHL1", "CNTN4", "CRBN", "SUMF1", "LRRN1"],
    "4": ["ADRA2C", "MFSD10", "TACC3", "FGFR3", "IDUA"],
    "5": ["PLEKHG4B", "SDHA", "PDCD6", "SLC12A7", "TERT"],
    "6": ["IRF4", "EXOC2", "HLA-A", "HLA-B", "HLA-C"],
    "7": ["COL28A1", "ACTB", "FBXL18", "ACTG1", "FSCN3"],
    "8": ["CLN8", "MCPH1", "ANGPT2", "AGPAT5", "XKR5"],
    "9": ["DMRT1", "SMARCA2", "VLDLR", "MLLT3", "PTPRD"],
    "10": ["SVIL", "TRDMT1", "ADARB2", "KLF6", "IL15RA"],
    "11": ["HRAS", "RASSF7", "IRF7", "CDHR5", "NAP1L4"],
    "12": ["KDM5A", "CCND2", "FGF23", "FGF6", "C12orf4"],
    "13": ["TPTE2", "PSPC1", "ZMYM5", "ZMYM2", "GJA3"],
    "14": ["FOXG1", "OR4N2", "OR4K2", "OR4K5", "OR4K1"],
    "15": ["CHSY1", "SELS", "SNRPN", "UBE3A", "HERC2"],
    "16": ["SOX8", "DEX1", "NPIP", "PDXDC1", "NTAN1"],
    "17": ["DOC2B", "RPH3AL", "FAM57A", "GEMIN4", "GLOD4"],
    "18": ["ROCK1", "USP14", "THOC1", "COLEC12", "CETN1"],
    "19": ["STK11", "ATP5D", "MIMT1", "CDKN2D", "AP1M2"],
    "20": ["SOX12", "ZCCHC3", "DEFB125", "DEFB126", "DEFB127"],
    "21": ["TPTE", "BAGE", "BAGE2", "LIPI", "RBM11"],
    "22": ["IL17RA", "CECR1", "CECR2", "BCL2L13", "BID"],
    "X": ["PLCXD1", "GTPBP6", "PPP2R3B", "SHOX", "CRLF2"],
    "Y": ["SRY", "RPS4Y1", "ZFY", "PRKY", "USP9Y"]
}

# Define consequences with their impacts
CONSEQUENCES = [
    ("missense_variant", "MODERATE"),
    ("synonymous_variant", "LOW"),
    ("intron_variant", "MODIFIER"),
    ("3_prime_UTR_variant", "MODIFIER"),
    ("5_prime_UTR_variant", "MODIFIER"),
    ("upstream_gene_variant", "MODIFIER"),
    ("downstream_gene_variant", "MODIFIER"),
    ("intergenic_variant", "MODIFIER"),
    ("frameshift_variant", "HIGH"),
    ("stop_gained", "HIGH")
]

# Nucleotides
NUCLEOTIDES = ["A", "C", "G", "T"]

def get_random_bases(ref_base):
    """Return a random base different from ref_base"""
    alt_options = [b for b in NUCLEOTIDES if b != ref_base]
    return random.choice(alt_options)

def generate_mock_vcf(output_file, variants_per_chromosome=100):
    """
    Generate a mock VCF file with the specified number of variants per chromosome.
    """
    # VCF header
    vcf_header = """##fileformat=VCFv4.2
##fileDate=20250323
##source=MockVCF
##INFO=<ID=CSQ,Number=.,Type=String,Description="Consequence annotations from Ensembl VEP. Format: Allele|Consequence|IMPACT|SYMBOL|Gene|Feature_type|Feature|BIOTYPE|EXON|INTRON|HGVSc|HGVSp|cDNA_position|CDS_position|Protein_position|Amino_acids|Codons|Existing_variation|DISTANCE|STRAND|FLAGS|VARIANT_CLASS|SYMBOL_SOURCE|HGNC_ID|CANONICAL|SIFT|PolyPhen">
##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">
##FORMAT=<ID=DP,Number=1,Type=Integer,Description="Read Depth">
##FORMAT=<ID=GQ,Number=1,Type=Integer,Description="Genotype Quality">
##FORMAT=<ID=AD,Number=R,Type=Integer,Description="Allelic Depths">
##FORMAT=<ID=PL,Number=G,Type=Integer,Description="Phred-scaled Genotype Likelihoods">
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE1\tSAMPLE2"""

    with open(output_file, 'w') as vcf:
        vcf.write(vcf_header + "\n")

        # Generate variants for each chromosome
        chromosomes = [str(i) for i in range(1, 23)] + ["X", "Y"]

        for chrom in chromosomes:
            genes = CHROMOSOME_GENES.get(chrom, ["UNKNOWN"])

            for i in range(variants_per_chromosome):
                # Generate position (increasing to avoid duplicates)
                pos = 100000 + (i * 1000)

                # Generate REF and ALT
                ref = random.choice(NUCLEOTIDES)
                alt = get_random_bases(ref)

                # Pick a gene for this chromosome
                gene = random.choice(genes)

                # Generate a random ENSG ID for the gene
                ensg = f"ENSG{random.randint(100000000, 999999999)}"
                enst = f"ENST{random.randint(100000000, 999999999)}"
                ensp = f"ENSP{random.randint(100000000, 999999999)}"

                # Pick a consequence and impact
                consequence, impact = random.choice(CONSEQUENCES)

                # Generate variant details
                variant_data = {
                    "chrom": f"chr{chrom}",
                    "pos": pos,
                    "id": ".",
                    "ref": ref,
                    "alt": alt,
                    "qual": "255",
                    "filter": "PASS",
                    "info": f"CSQ={alt}|{consequence}|{impact}|{gene}|{ensg}|Transcript|{enst}|protein_coding|{random.randint(1,10)}/{random.randint(10,20)}||{enst}.{random.randint(1,10)}:c.{random.randint(1,1000)}{ref}>{alt}|{ensp}.{random.randint(1,5)}:p.{random.choice(['Ala', 'Val', 'Leu', 'Ile', 'Pro', 'Phe', 'Trp', 'Met'])}{random.randint(1,300)}{random.choice(['Ala', 'Val', 'Leu', 'Ile', 'Pro', 'Phe', 'Trp', 'Met'])}|{random.randint(1,1000)}|{random.randint(1,1000)}|{random.randint(1,300)}|{random.choice(['A', 'V', 'L', 'I', 'P', 'F', 'W', 'M'])}/{random.choice(['A', 'V', 'L', 'I', 'P', 'F', 'W', 'M'])}|{random.choice(['Gct', 'Gcc', 'Gca', 'Gcg'])}/{random.choice(['Aat', 'Aac', 'Gat', 'Gac'])}||{random.randint(0,1000)}|{random.choice(['-1', '1'])}||SNV|HGNC|{random.randint(10000, 99999)}|YES||||"
                }

                # Generate genotype data for two samples
                genotypes = []
                for sample in range(2):
                    # Generate random genotype (0/0, 0/1, or 1/1)
                    gt_type = random.choices([0, 1, 2], weights=[0.5, 0.3, 0.2])[0]

                    if gt_type == 0:  # Reference homozygous
                        gt = "0/0"
                        depth = random.randint(20, 50)
                        ad = f"{depth},0"
                        pl = "0,255,255"
                    elif gt_type == 1:  # Heterozygous
                        gt = "0/1"
                        depth = random.randint(20, 50)
                        ref_depth = depth // 2
                        alt_depth = depth - ref_depth
                        ad = f"{ref_depth},{alt_depth}"
                        pl = "255,0,255"
                    else:  # Alt homozygous
                        gt = "1/1"
                        depth = random.randint(20, 50)
                        ad = f"0,{depth}"
                        pl = "255,255,0"

                    genotypes.append(f"{gt}:{depth}:99:{ad}:{pl}")

                # Write the variant line
                variant_line = f"{variant_data['chrom']}\t{variant_data['pos']}\t{variant_data['id']}\t{variant_data['ref']}\t{variant_data['alt']}\t{variant_data['qual']}\t{variant_data['filter']}\t{variant_data['info']}\tGT:DP:GQ:AD:PL\t{genotypes[0]}\t{genotypes[1]}"
                vcf.write(variant_line + "\n")

if __name__ == "__main__":
    output_file = "mock_comprehensive.vcf"
    generate_mock_vcf(output_file, variants_per_chromosome=100)
    print(f"Generated mock VCF file with 100 variants per chromosome (1-22, X, Y): {output_file}")