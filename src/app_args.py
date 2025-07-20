# ---------------------------------------------------------------------------------------
# Application arguments: Validate the input and output file arguments.
#
# Author: Donald Friggieri
# email: dfriggieri@gmail.com
# ---------------------------------------------------------------------------------------
from os import cpu_count
from pathlib import Path
from argparse import ArgumentParser


def setup_args():
    """
    Return an initialised command line argument parser.

    Returns:
        ArgumentParser: If successful, return an argument parser object for the command line options specified.
    """
    parser = \
        ArgumentParser(
            description="A tool to parse a single sample or a multi-sample VCF file and save it to a PostgreSQL "
                        "database.!")
    
    # Input related parameters
    parser.add_argument("-i", "--input", help="Input VCF file.", required=True)
    parser.add_argument("-d", "--database", help="PostgreSQL DB name.", required=True)
    parser.add_argument("-c", "--create", action="store_true", default=True,
                        help="Delete and recreate database if already exists.", required=False)
    parser.add_argument("-u", "--username", help="PostgreSQL user.", required=True)
    parser.add_argument("-p", "--password", help="PostgreSQL password.", required=True)
    parser.add_argument("-l", "--host", help="PostgreSQL host name.", required=True)
    parser.add_argument("-b", "--batch", type=int, choices=[2000, 5000, 10000, 20000],
                        default=10000, help="Batch size.", required=False)
    parser.add_argument("-t", "--cores", type=int, default=cpu_count() // 2,
                        help=f"Number of CPU cores/threads to use for processing. "
                             f"Default: {cpu_count() // 2} (half of available cores).", required=False)
    
    parser.add_argument('-v', action='version', version='%(prog)s 1.0')
    
    return parser.parse_args()


def validate_arguments(args):
    """
    Method to validate the application's arguments such as validating the input files and output directory path exist.

    Parameters:
        args (parser.parse_args()): The application's argparse arguments.
    Returns:
        str, str: File format, file name.
    """
    input_params = {
        args.input: ('vcf file', '.vcf')
    }

    # Check input file formats and assert file exist on disk
    for k, v in input_params.items():
        if not k.endswith(v[1]):
            print(f'ERROR: Allowed {v[0]} file formats are {v[1]}')
            return -1
            
        if not Path(k).exists() or not Path.is_file(Path(k)):
            print(f'Error: \'{k}\' does not exist or argument given is not a file!')
            return -1

    # Validate cores argument
    if args.cores < 1:
        print('ERROR: Number of cores must be at least 1')
        return -1

    if args.cores > cpu_count():
        print(f'ERROR: Number of cores ({args.cores}) cannot exceed available cores ({cpu_count()})')
        return -1

    return 0
