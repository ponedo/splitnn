import os
from .bird_utils import *
from .common import *

def generate_one_node_mnt_dir(node_id, node_mnt_dir, node_info, mnt_config):
    etc_dir_path = os.path.join(node_mnt_dir, "etc")
    clear_or_create_directory(etc_dir_path)
    bird_conf_dst_path = os.path.join(etc_dir_path, "bird.conf")
    generate_one_node_bird_conf(node_id, node_info, bird_conf_dst_path)

    # Add an entry in mnt_config.json
    mnt_config["mnts"].append({
        "node_id": node_id,
        "volume_opt": "etc/:/share/etc/"
    })
