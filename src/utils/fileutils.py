# ---------------------------------------------------------------------------------------
# Application to read a one sample or multi-sample VCF file and save it to a postgres DB
#
# Author: Donald Friggieri
# email: dfriggieri@gmail.com
# ---------------------------------------------------------------------------------------

import threading
import os

file_lock = threading.Lock()


def thread_safe_write_to_file(filepath, str):
    with file_lock:
        with open(filepath, "a") as f:
            f.write(str + '\n')


def delete_file(filepath):
    if os.path.exists(filepath):
        os.remove(filepath)
        print(f'Deleted file: {filepath}')