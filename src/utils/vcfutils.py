# ---------------------------------------------------------------------------------------
# Application to read a one sample or multi-sample VCF file and save it to a postgres DB
#
# Author: Donald Friggieri
# email: dfriggieri@gmail.com
# ---------------------------------------------------------------------------------------

genotype_map = {
    # Diploid
    '0/0': 'HOM_REF', '0|0': 'HOM_REF',
    '0/1': 'HET', '1/0': 'HET', '0|1': 'HET', '1|0': 'HET',
    '1/1': 'HOM_ALT', '1|1': 'HOM_ALT',
    '0/2': 'HET_ALT1', '2/0': 'HET_ALT1', '0|2': 'HET_ALT1', '2|0': 'HET_ALT1',
    '1/2': 'HET_ALT', '2/1': 'HET_ALT', '1|2': 'HET_ALT', '2|1': 'HET_ALT',
    '2/2': 'HOM_ALT2', '2|2': 'HOM_ALT2',
    './.': 'MISSING',

    # Haploid
    '0': 'HOM_REF',
    '1': 'HET_ALT',
    '2': 'HET_ALT',  # In theory should never happen for a haploid cell/organism
    '.': 'MISSING'
}

def get_csq_fields(vcf_reader):
    try:
        info_header = vcf_reader.raw_header.split("##INFO=<ID=CSQ")[1].split("Format: ")[1].split('">')[0]
        csq_fields = info_header.split('|')

        return csq_fields
    except IndexError:
        print("ERROR: VCF file does not contain CSQ annotation field!")
        return ""

def map_genotype(gt):
    return genotype_map.get(gt, 'MISSING')  # Default to 'MISSING' if genotype is not in the map