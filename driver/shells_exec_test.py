import os
import time
import json
import argparse
import subprocess
import shutil
from copy import deepcopy
from scripts.partition_topo import partition_graph
from itertools import product
from util.remote import *
from util.topo_info import *
from util.factor import *
from util.common import *
from util.mnt_utils import *
from util.exec_utils import *

############################ Constants ###############################

DRIVER_WORKDIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(DRIVER_WORKDIR) # Change cuurent working directory

# REPEAT_TIME = 1
SERVER_CONFIG_PATH = "server_config.json"
INFRA_BIN_PATH = "bin/topo_setup_test"
INFRA_TMP_PATH = "tmp"
INFRA_TOPO_PATH = "tmp/topo"
INFRA_MNT_DIR = "tmp/mnt"
LOCAL_TOPO_DIR = "topo"
LOCAL_MNT_DIR = "mnt"
LOCAL_EXEC_CONFIG_PATH = "exec_config.json"
LOCAL_RESULT_DIR = "raw_results"
REMOTE_RESULT_PATHS = [
    ("file", "tmp/setup_log.txt"),
    ("file", "tmp/clean_log.txt"),
    ("file", "tmp/link_log.txt"),
    ("dir", "tmp/ctr_log"),
    ("dir", "tmp/kern_func"),
    ("dir", "tmp/cctr_time.txt"),
    ("dir", "tmp/cpu_mem_usage.txt"),
]

######################### Command options ############################

const_options = {
    "s": SERVER_CONFIG_PATH
}

shells = [
    {"size": [16, 30], "domain_size": [4, 10]},
    {"size": [40, 50], "domain_size": [8, 10]},
    {"size": [60, 60], "domain_size": [6, 10]},
    # {"size": [48, 36], "domain_size": [8, 9]},
    # {"size": [48, 36], "domain_size": [8, 9]},
    # {"size": [48, 36], "domain_size": [8, 9]},
    # {"size": [48, 36], "domain_size": [8, 9]},
]

# shells = [
#     # {"size": [20, 10], "domain_size": [10, 5]},
#     {"size": [20, 20], "domain_size": [5, 5]},
# ]

server_spec_options = {
    "i": lambda i: i
}

######################### Helper functions ############################

def connect_remote_machines(server_config_list):
    remote_machines = []
    for server in server_config_list:
        remote_machine = RemoteMachine(
            server["ipAddr"], server["user"],
            server["password"], working_dir=server["infraWorkDir"])
        machine = remote_machine.connect()
        remote_machines.append(machine)
    return remote_machines


def prepare_env_on_remote_machines(remote_machines, server_config_list):
    server_config_src_path = os.path.join(DRIVER_WORKDIR, SERVER_CONFIG_PATH)
    server_config_src_dst_paths = {
        server["ipAddr"]: (
            server_config_src_path,
            os.path.join(server["infraWorkDir"], SERVER_CONFIG_PATH),
            False
        ) for server in server_config_list
    }
    send_file_to_multiple_machines(
        remote_machines, server_config_src_dst_paths)

    # Recompile virtual network manager on all machines
    execute_command_on_multiple_machines(
        remote_machines, {
            server["ipAddr"]: (
                "make", server["infraWorkDir"], None, False
            ) for server in server_config_list
        }
    )


def get_full_topo_filename(topo_args):
    return f"{'_'.join(topo_args)}.txt"


def get_sub_topo_filename(topo_args, i):
    full_topo_filename = get_full_topo_filename(topo_args)
    splited_topo_filename = full_topo_filename.split('.')
    if len(splited_topo_filename) == 1:
        splited_sub_topo_filename = splited_topo_filename + [f"sub{i}"] # without .txt suffix
    else:
        splited_sub_topo_filename = splited_topo_filename[:-1] + [f"sub{i}"] + splited_topo_filename[-1:] # with .txt suffix
    sub_topo_filename = '.'.join(splited_sub_topo_filename)
    return sub_topo_filename


# example_node_info = {
#     "lo_ipv4_addr": "10.0.0.0",
#     "lo_ipv6_addr": "fd01::0",
#     "local_as_number": 1,
#     "local_as_network": "fd01::0/124",
#     "ospf_disabled_intfs": [
#         "eth-0-1",
#         "eth-0-2",
#     ],
#     "ebgp_neighbors": [
#         {
#             "peer_node_id": 1,
#             "peer_intf_ipv6_addr": "fd02::1",
#             "peer_as_number": 2,
#             "local_intf": "eth-0-1",
#             "local_intf_ipv6_addr": "fd02::0",
#         }
#     ],
#     "ibgp_neighbors": [
#         {
#             "peer_node_id": 1,
#             "peer_lo_ipv6_addr": "fd02::1",
#             "peer_as_number": 2,
#         }
#     ]
# }
def generate_node_info(
        domain_id, lo_ipv4_addr, lo_ipv6_addr,
        local_as_network_prefix,
        ):
    lo_ipv4_addr = lo_ipv4_addr
    lo_ipv6_addr = lo_ipv6_addr
    local_as_number = domain_id + 1
    local_as_network = local_as_network_prefix
    node_info = {
        "lo_ipv4_addr": lo_ipv4_addr,
        "lo_ipv6_addr": lo_ipv6_addr,
        "local_as_number": local_as_number,
        "local_as_network": local_as_network,
        "ospf_disabled_intfs": [],
        "ebgp_neighbors": [],
        "ibgp_neighbors": [],
    }
    return node_info


def next_power_of_2(X):
    if X <= 0:
        raise ValueError("X must be a positive integer")
    K = (X - 1).bit_length()  # Get the smallest K where 2^K >= X
    power_of_2 = 1 << K       # Compute 2^K
    return power_of_2, K


def get_next_neighbor(i, j, shell_x, shell_y, prev_shell_node_num):
    inshell_id = i * shell_y + j
    if j < shell_y - 1:
        next_neighbor_inshell_id = inshell_id + 1
        next_neighbor_node_id = prev_shell_node_num + next_neighbor_inshell_id
    else:
        next_neighbor_inshell_id = inshell_id - (shell_y - 1)
        next_neighbor_node_id = prev_shell_node_num + next_neighbor_inshell_id
    return next_neighbor_node_id, next_neighbor_inshell_id


def get_right_neighbor(i, j, shell_x, shell_y, prev_shell_node_num):
    inshell_id = i * shell_y + j
    if i < shell_x - 1:
        right_neighbor_inshell_id = inshell_id + shell_y
        right_neighbor_node_id = prev_shell_node_num + right_neighbor_inshell_id
    else:
        right_neighbor_inshell_id = inshell_id - (shell_x - 1) * shell_y
        right_neighbor_node_id = prev_shell_node_num + right_neighbor_inshell_id
    return right_neighbor_node_id, right_neighbor_inshell_id


def get_prev_neighbor(i, j, shell_x, shell_y, prev_shell_node_num):
    inshell_id = i * shell_y + j
    if j > 0:
        prev_neighbor_inshell_id = inshell_id - 1
        prev_neighbor_node_id = prev_shell_node_num + prev_neighbor_inshell_id
    else:
        prev_neighbor_inshell_id = inshell_id + (shell_y - 1)
        prev_neighbor_node_id = prev_shell_node_num + prev_neighbor_inshell_id
    return prev_neighbor_node_id, prev_neighbor_inshell_id


def get_left_neighbor(i, j, shell_x, shell_y, prev_shell_node_num):
    inshell_id = i * shell_y + j
    if i > 0:
        left_neighbor_inshell_id = inshell_id - shell_y
        left_neighbor_node_id = prev_shell_node_num + left_neighbor_inshell_id
    else:
        left_neighbor_inshell_id = inshell_id + (shell_x - 1) * shell_y
        left_neighbor_node_id = prev_shell_node_num + left_neighbor_inshell_id
    return left_neighbor_node_id, left_neighbor_inshell_id


def next_is_border(i, j, domain_x, domain_y, shell_x, shell_y):
    return j == shell_y - 1 or j % domain_y == domain_y - 1


def right_is_border(i, j, domain_x, domain_y, shell_x, shell_y):
    return i == shell_x - 1 or i % domain_x == domain_x - 1


def prev_is_border(i, j, domain_x, domain_y, shell_x, shell_y):
    return j == 0 or j % domain_y == 0


def left_is_border(i, j, domain_x, domain_y, shell_x, shell_y):
    return i == 0 or i % domain_x == 0


def get_domain_id(i, j, domain_x, domain_y, shell_x, shell_y):
    domain_i, domain_j = i // domain_x, j // domain_y
    domain_id = domain_i * (shell_y // domain_y) + domain_j
    return domain_id


def get_domain_corner_node_ids(
        domain_i, domain_j,
        domain_x, domain_y,
        shell_x, shell_y,
        prev_shell_node_num
        ):
    bl_i = domain_i * domain_x
    bl_j = domain_j * domain_y
    bl_inshell_id = bl_i * shell_y + bl_j
    tl_inshell_id = bl_inshell_id + domain_y - 1
    br_inshell_id = bl_inshell_id + (domain_x - 1) * shell_y
    tr_inshell_id = br_inshell_id + domain_y - 1
    corners = {
        "tl": tl_inshell_id + prev_shell_node_num,
        "tr": tr_inshell_id + prev_shell_node_num,
        "bl": bl_inshell_id + prev_shell_node_num,
        "br": br_inshell_id + prev_shell_node_num,
    }
    return corners


def add_ospf_disabled_intf(
        local_node_id, peer_node_id, node_infos,
        ):
    node_infos[local_node_id]["ospf_disabled_intfs"].append(
        f"{local_node_id}-{peer_node_id}")


def add_ebgp_neighbor(
        local_node_id, peer_node_id,
        local_intf_ipv6_addr, peer_intf_ipv6_addr,
        local_domain_id, peer_domain_id,
        node_infos
        ):
    local_bgp_neighbor = {
        "peer_node_id": peer_node_id,
        "peer_intf_ipv6_addr": peer_intf_ipv6_addr,
        "peer_as_number": peer_domain_id + 1,
        "local_intf": f"{local_node_id}-{peer_node_id}",
        "local_intf_ipv6_addr": local_intf_ipv6_addr,
    }
    peer_bgp_neighbor = {
        "peer_node_id": local_node_id,
        "peer_intf_ipv6_addr": local_intf_ipv6_addr,
        "peer_as_number": local_domain_id + 1,
        "local_intf": f"{peer_node_id}-{local_node_id}",
        "local_intf_ipv6_addr": peer_intf_ipv6_addr,
    }
    node_infos[local_node_id]["ebgp_neighbors"].append(local_bgp_neighbor)
    node_infos[peer_node_id]["ebgp_neighbors"].append(peer_bgp_neighbor)

valid_ibgp_pairs = [
    ("tl", "tr"),
    ("tr", "tl"),
    ("tl", "bl"),
    ("bl", "tl"),
]
def add_ibgp_neighbors(
        local_node_id, local_position,
        domain_id, domain_corner_node_ids,
        node_infos
        ):
    for peer_position, peer_node_id in domain_corner_node_ids.items():
        # if peer_position == local_position:
        #     continue
        if (local_position, peer_position) not in valid_ibgp_pairs:
            continue
        ibgp_neighbor = {
            "peer_node_id": peer_node_id,
            "peer_lo_ipv6_addr": node_infos[peer_node_id]["lo_ipv6_addr"],
            "peer_as_number": domain_id + 1,
        }
        node_infos[local_node_id]["ibgp_neighbors"].append(ibgp_neighbor)


def generate_shell_conf(shell, prev_shell_node_num, nodes, edges, node_infos):
    shell_x, shell_y = shell["size"][0], shell["size"][1]
    domain_x, domain_y = shell["domain_size"][0], shell["domain_size"][1]
    assert shell_y > 1 and shell_x > 1

    # Init domain specific data structure
    domain_size = domain_x * domain_y
    domain_num_x = (shell_x // domain_x)
    domain_num_y = (shell_y // domain_y)
    domain_num = domain_num_x * domain_num_y
    domain_network_size, k = next_power_of_2(domain_size)
    domain_network_prefix_len = 128 - k
    domain_network_starting_addrs = []
    domain_lo_ipv4_generators = []
    domain_lo_ipv6_generators = []
    domain_corners = []
    cur_starting_ipv4_addr = ipaddress.IPv4Address("10.0.0.0")
    cur_starting_ipv6_addr = ipaddress.IPv6Address("fd01::0")
    for domain_id in range(domain_num):
        domain_network_starting_addrs.append(
            str(cur_starting_ipv6_addr))
        domain_lo_ipv4_generators.append(
            IPv4AddressGenerator(str(cur_starting_ipv4_addr)))
        domain_lo_ipv6_generators.append(
            IPv6AddressGenerator(str(cur_starting_ipv6_addr)))
        cur_starting_ipv4_addr += domain_network_size
        cur_starting_ipv6_addr += domain_network_size
        cur_domain_corners = get_domain_corner_node_ids(
            domain_id // domain_num_y, domain_id % domain_num_y,
            domain_x, domain_y, shell_x, shell_y,
            prev_shell_node_num)
        domain_corners.append(cur_domain_corners)

    # Init bgp link addr generator
    link_ipv6_addr_generator = IPv6AddressGenerator("fd02::0")

    # Generate nodes in the grid
    for i in range(shell_x):
        for j in range(shell_y):
            inshell_id = i * shell_y + j
            node_id = prev_shell_node_num + inshell_id
            domain_id = get_domain_id(i, j, domain_x, domain_y, shell_x, shell_y)

            # Generate node info
            nodes.append(node_id)
            node_infos.append(
                generate_node_info(
                    domain_id,
                    domain_lo_ipv4_generators[domain_id].get_next_ipaddr(),
                    domain_lo_ipv6_generators[domain_id].get_next_ipaddr(),
                    f"{domain_network_starting_addrs[domain_id]}/{domain_network_prefix_len}",
                )
            )

    # Generate link and bgp neighbor info
    for i in range(shell_x):
        for j in range(shell_y):
            inshell_id = i * shell_y + j
            node_id = prev_shell_node_num + inshell_id
            domain_id = get_domain_id(i, j, domain_x, domain_y, shell_x, shell_y)

            # Get neighbor ids
            next_neighbor_node_id, next_neighbor_inshell_id = \
                get_next_neighbor(i, j, shell_x, shell_y, prev_shell_node_num)
            right_neighbor_node_id, right_neighbor_inshell_id = \
                get_right_neighbor(i, j, shell_x, shell_y, prev_shell_node_num)
            prev_neighbor_node_id, prev_neighbor_inshell_id = \
                get_prev_neighbor(i, j, shell_x, shell_y, prev_shell_node_num)
            left_neighbor_node_id, left_neighbor_inshell_id = \
                get_left_neighbor(i, j, shell_x, shell_y, prev_shell_node_num)

            # Connect link to the neighbors
            edges.append((node_id, next_neighbor_node_id))
            edges.append((node_id, right_neighbor_node_id))

            # If current node is at border, configure ospf disabled links
            if next_is_border(i, j, domain_x, domain_y, shell_x, shell_y):
                add_ospf_disabled_intf(node_id, next_neighbor_node_id, node_infos)
            if right_is_border(i, j, domain_x, domain_y, shell_x, shell_y):
                add_ospf_disabled_intf(node_id, right_neighbor_node_id, node_infos)
            if prev_is_border(i, j, domain_x, domain_y, shell_x, shell_y):
                add_ospf_disabled_intf(node_id, prev_neighbor_node_id, node_infos)
            if left_is_border(i, j, domain_x, domain_y, shell_x, shell_y):
                add_ospf_disabled_intf(node_id, left_neighbor_node_id, node_infos)

            # If current node is border router, configure bgp links
            if next_is_border(i, j, domain_x, domain_y, shell_x, shell_y) and \
                right_is_border(i, j, domain_x, domain_y, shell_x, shell_y):
                right_neighbor_domain_id = get_domain_id(
                    right_neighbor_inshell_id // shell_y,
                    right_neighbor_inshell_id % shell_y,
                    domain_x, domain_y, shell_x, shell_y
                )
                add_ebgp_neighbor(
                    node_id, right_neighbor_node_id,
                    link_ipv6_addr_generator.get_next_ipaddr(),
                    link_ipv6_addr_generator.get_next_ipaddr(),
                    domain_id, right_neighbor_domain_id,
                    node_infos
                )
                add_ibgp_neighbors(
                    node_id, "tr",
                    domain_id, domain_corners[domain_id],
                    node_infos
                )
            elif prev_is_border(i, j, domain_x, domain_y, shell_x, shell_y) and \
                left_is_border(i, j, domain_x, domain_y, shell_x, shell_y):
                # left_neighbor_domain_id = get_domain_id(
                #     left_neighbor_inshell_id // shell_y,
                #     left_neighbor_inshell_id % shell_y,
                #     domain_x, domain_y, shell_x, shell_y
                # )
                # add_ebgp_neighbor(
                #     node_id, left_neighbor_node_id,
                #     link_ipv6_addr_generator.get_next_ipaddr(),
                #     link_ipv6_addr_generator.get_next_ipaddr(),
                #     domain_id, left_neighbor_domain_id,
                #     node_infos
                # )
                add_ibgp_neighbors(
                    node_id, "bl",
                    domain_id, domain_corners[domain_id],
                    node_infos
                )
            elif next_is_border(i, j, domain_x, domain_y, shell_x, shell_y) and \
                left_is_border(i, j, domain_x, domain_y, shell_x, shell_y):
                next_neighbor_domain_id = get_domain_id(
                    next_neighbor_inshell_id // shell_y,
                    next_neighbor_inshell_id % shell_y,
                    domain_x, domain_y, shell_x, shell_y
                )
                if j < shell_y - 1:
                    # Avoid up-down ring
                    add_ebgp_neighbor(
                        node_id, next_neighbor_node_id,
                        link_ipv6_addr_generator.get_next_ipaddr(),
                        link_ipv6_addr_generator.get_next_ipaddr(),
                        domain_id, next_neighbor_domain_id,
                        node_infos
                    )
                add_ibgp_neighbors(
                    node_id, "tl",
                    domain_id, domain_corners[domain_id],
                    node_infos
                )
            elif prev_is_border(i, j, domain_x, domain_y, shell_x, shell_y) and \
                right_is_border(i, j, domain_x, domain_y, shell_x, shell_y):
                # prev_neighbor_domain_id = get_domain_id(
                #     prev_neighbor_inshell_id // shell_y,
                #     prev_neighbor_inshell_id % shell_y,
                #     domain_x, domain_y, shell_x, shell_y
                # )
                # add_ebgp_neighbor(
                #     node_id, prev_neighbor_node_id,
                #     link_ipv6_addr_generator.get_next_ipaddr(),
                #     link_ipv6_addr_generator.get_next_ipaddr(),
                #     domain_id, prev_neighbor_domain_id,
                #     node_infos
                # )
                add_ibgp_neighbors(
                    node_id, "br",
                    domain_id, domain_corners[domain_id],
                    node_infos
                )


def generate_topology(shells):
    node_infos = [] # node_id -> info
    nodes = []
    edges = []

    prev_shell_node_num = 0
    for shell in shells:
        shell_x, shell_y = shell["size"][0], shell["size"][1]
        generate_shell_conf(shell, prev_shell_node_num, nodes, edges, node_infos)
        prev_shell_node_num += shell_x * shell_y

    # Write nodes and edges to the output file
    with open(os.path.join(LOCAL_TOPO_DIR, "shells.txt"), 'w') as f:
        # Write nodes
        f.write(' '.join(map(str, nodes)) + '\n')
        # Write edges
        for edge in edges:
            f.write(f"{edge[0]} {edge[1]}\n")

    return node_infos


def prepare_topology(remote_machines):
    topo = ["shells"]
    full_topo_filename = get_full_topo_filename(topo)
    full_topo_filepath = os.path.join(DRIVER_WORKDIR, "topo", full_topo_filename)

    # Partition topology
    partition_graph(full_topo_filepath, len(server_config_list))
    # script_path = os.path.join(DRIVER_WORKDIR, "scripts", f"partition_topo.py")
    # partition_topology_cmd = ["python3", script_path, "-f", topo_filepath, "-n", f"{len(servers)}"]
    # result = subprocess.run(partition_topology_cmd, capture_output=True, text=True, env=env)

    # Send sub-topo to servers
    sub_topo_src_dst_filepaths = {}
    for i, server in enumerate(server_config_list):
        sub_topo_filename = get_sub_topo_filename(topo, i)
        sub_topo_src_filepath = os.path.join(os.path.dirname(full_topo_filepath), sub_topo_filename)
        sub_topo_dst_filepath = os.path.join(server["infraWorkDir"], INFRA_TOPO_PATH, sub_topo_filename)
        sub_topo_src_dst_filepaths[server["ipAddr"]] = \
            (sub_topo_src_filepath, sub_topo_dst_filepath, False)
    send_file_to_multiple_machines(
        remote_machines, sub_topo_src_dst_filepaths)


def prepare_mnt_dir(remote_machines, topo_name, node_infos):
    # Init local mnt_dir and mnt_config dict
    topo = topo_name.split('_')
    clear_or_create_directory(LOCAL_MNT_DIR)
    mnt_config = {"mnts": []}

    # Remove remote mnt dirs
    execute_command_on_multiple_machines(
        remote_machines, {
            server["ipAddr"]: (
                f"rm -rf {INFRA_MNT_DIR}", server["infraWorkDir"], None, True
            ) for server in server_config_list
        }
    )

    # Get all sub topologies
    full_topo_filename = get_full_topo_filename(topo)
    full_topo_filepath = os.path.join(DRIVER_WORKDIR, "topo", full_topo_filename)
    sub_topo_src_dst_filepaths = {}
    for i, server in enumerate(server_config_list):
        # Get node list for the sub topo
        sub_topo_filename = get_sub_topo_filename(topo, i)
        sub_topo_src_filepath = os.path.join(os.path.dirname(full_topo_filepath), sub_topo_filename)
        with open(sub_topo_src_filepath, 'r') as f:
            first_line = f.readline()
            node_id_list = [int(e) for e in first_line.strip().split()]
        # Prepare mnt dir for the sub topo
        server_mnt_dir = os.path.join(LOCAL_MNT_DIR, f"server{i}")
        os.makedirs(server_mnt_dir, exist_ok=True)
        for node_id in node_id_list:
            node_mnt_dir = os.path.join(server_mnt_dir, f"node{node_id}")
            os.makedirs(node_mnt_dir, exist_ok=True)
            generate_one_node_mnt_dir(node_id, node_mnt_dir, node_infos[node_id], mnt_config)
        # Output mnt_config.json
        output_dict_as_json(os.path.join(server_mnt_dir, "mnt_config.json"), mnt_config)
        dst_mnt_dir_path = os.path.join(server["infraWorkDir"], INFRA_TMP_PATH, "mnt")
        sub_topo_src_dst_filepaths[server["ipAddr"]] = \
            (server_mnt_dir, dst_mnt_dir_path, True)
    send_file_to_multiple_machines(
        remote_machines, sub_topo_src_dst_filepaths)


def prepare_exec_config(remote_machines, topo_name, node_infos):
    # Init local mnt_dir and mnt_config dict
    topo = topo_name.split('_')
    exec_config = {"exec_entries": []}

    # Get all sub topologies
    full_topo_filename = get_full_topo_filename(topo)
    full_topo_filepath = os.path.join(DRIVER_WORKDIR, "topo", full_topo_filename)
    sub_topo_src_dst_filepaths = {}
    for i, server in enumerate(server_config_list):
        # Get node list for the sub topo
        sub_topo_filename = get_sub_topo_filename(topo, i)
        sub_topo_src_filepath = os.path.join(os.path.dirname(full_topo_filepath), sub_topo_filename)
        with open(sub_topo_src_filepath, 'r') as f:
            first_line = f.readline()
            node_id_list = [int(e) for e in first_line.strip().split()]
        # Prepare exec_config for the sub topo
        for node_id in node_id_list:
            generate_one_node_setup_exec_entry(node_id, node_infos[node_id], exec_config)
        for node_id in node_id_list:
            generate_one_node_routerup_exec_entry(node_id, node_infos[node_id], exec_config)
        # Output mnt_config.json
        output_dict_as_json("exec_config.json", exec_config)
        dst_exec_config_path = os.path.join(server["infraWorkDir"], INFRA_TMP_PATH, "exec_config.json")
        sub_topo_src_dst_filepaths[server["ipAddr"]] = \
            ("exec_config.json", dst_exec_config_path, True)
    send_file_to_multiple_machines(
        remote_machines, sub_topo_src_dst_filepaths)

################################# Main ##################################

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Execute a batch of experiments')
    args = parser.parse_args()

    # Read configuration of servers
    with open(SERVER_CONFIG_PATH, 'r') as f:
        server_config = json.load(f)
        server_config_list = server_config["servers"]

    # Connect to remote machine
    remote_machines = connect_remote_machines(server_config_list)

    # Config servers on remote machines
    prepare_env_on_remote_machines(remote_machines, server_config_list)

    # Generate topo file and node info
    node_infos = generate_topology(shells)

    # Prepare topologies and distribute them onto servers
    prepare_topology(remote_machines)

    # Prepare mnt_dir (with mnt_config.json)
    prepare_mnt_dir(remote_machines, "shells", node_infos)

    # Prepare exec_config.json
    prepare_exec_config(remote_machines, "shells", node_infos)

    # Close connection
    for remote_machine in remote_machines:
        remote_machine.close_connection()
