# Utils for reading AS relationship data from CAIDA
# 0 small: JP,KR
# 1 mediem: CN,HK,MO,TW,BN,ID,KH,LA,MM,PH,SG,TH,TL,VN
# 2 large: TW,MO,AF,AM,AU,AZ,BD,BN,BT,CN,FJ,HK,IN,ID,JP,KH,KP,KR,LA,MG,MM,MN,NP,NZ,PH,SG,LK,TH,TL,VN

import os
import json
import argparse
import shutil

DRIVER_WORKDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
AS_DATA_DIR = os.path.join(DRIVER_WORKDIR, "data")
AS_TOPO_CONFIG_FILEPATH = os.path.join(AS_DATA_DIR, "as_topo_config.json")

def generate_as_topology(size, filepath):
    with open(AS_TOPO_CONFIG_FILEPATH, 'r') as f:
        as_topo_config = json.load(f)
    try:
        src_filepath = os.path.join(AS_DATA_DIR, as_topo_config[size])
    except KeyError:
        print(f"Invalid size: {size}")
        exit(1)
    dst_filepath = filepath
    shutil.copy(src_filepath, dst_filepath)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='A script to generate BGP AS topology')
    parser.add_argument('size', type=str, help='Size of AS topology')
    parser.add_argument('filepath', type=str, help='Output file name')
    args = parser.parse_args()

    size = args.size
    filepath = args.filepath

    generate_as_topology(size, filepath)
    print(f"AS topology generated in {filepath}.")
