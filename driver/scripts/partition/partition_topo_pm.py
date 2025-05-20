import os
import metis
import shutil
import argparse
import subprocess
from .fmt_convert import *


# TBS partitioning need to be downloaded from https://github.com/tbs2022/tbs. Please change this path to the "build" directory compiled out from that project.
TBS_BIN_DIR = "/home/cnic/open-src/tbs/build"
TBS_BIN_PATH = os.path.join(TBS_BIN_DIR, "tbs")


def partition_graph_across_pm(
    nodes, adjacency_list, server_config_list, input_topo_filepath):
    """Partitions the graph across multiple physical machines with TBS according to config."""

    # Scan IDs of physical machines
    distinct_pm_ids = set()
    for i, server in enumerate(server_config_list):
        pm_id = server["phyicalMachineId"]
        distinct_pm_ids.add(pm_id)
    
    # If the number of PMs is 1, return the original topology
    if len(distinct_pm_ids) == 1:
        print("Only one PM is available. No partitioning needed.")
        node2pmid = {}
        for node in nodes:
            node2pmid[node] = list(distinct_pm_ids)[0]
        return node2pmid

    # Convert the topology file into metis graph format
    topo_file_dir = os.path.dirname(input_topo_filepath)
    topo_filename = os.path.basename(input_topo_filepath)
    topo_filename_elements = topo_filename.split('.')
    full_graph_metis_filename = '.'.join(topo_filename_elements[:-1]) + ".graph"
    full_graph_metis_filepath = os.path.join(topo_file_dir, full_graph_metis_filename)
    node_ids, nodeid2name, adj_matrix, edge_num = \
        convert_adjlist_to_metis_graph(nodes, adjacency_list, full_graph_metis_filepath)
    node_num = len(node_ids)

    # Call TBS partitioning program
    pm_num = len(distinct_pm_ids)
    node_num = len(node_ids)
    cpu_capacity = int(1.05 * node_num // pm_num)
    generate_topology_cmd = [
        TBS_BIN_PATH, full_graph_metis_filepath,
        f"--k={pm_num}",
        f"--cpu_capacity={cpu_capacity}",
        "--preconfiguration=esocial"
    ]
    print(f"Running TBS partitioning with command: {' '.join(generate_topology_cmd)}")
    original_dir = os.getcwd()
    os.chdir(TBS_BIN_DIR)
    try:
        stderr_output = []
        with subprocess.Popen(generate_topology_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as proc:
            for line in proc.stdout:
                print(line, end='')
            for line in proc.stderr:
                stderr_output.append(line)
                print(line, end='')
            proc.wait()
    finally:
        os.chdir(original_dir)
    # If returncode is 0, but stderr is non-empty and contains 'Traceback', treat as error, and exit the program
    # print(f"proc.returncode: {proc.returncode}")
    if proc.returncode != 0 or any("Traceback" in line for line in stderr_output):
        print("Error occurred while running TBS partitioning:")
        for line in stderr_output:
            print(line, end='')
        exit(1)
    # result = subprocess.run(generate_topology_cmd, capture_output=True, text=True)

    # Acquire partition result
    partition_output_filepath = os.path.join(TBS_BIN_DIR, f"tmppartition{pm_num}")
    nodeid2pmid = {}
    with open(partition_output_filepath, 'r') as f:
        for i, line in enumerate(f):
            node_id = i + 1
            pm_id = int(line.strip())
            nodeid2pmid[node_id] = pm_id
            if pm_id not in distinct_pm_ids:
                print(f"Node {node_id} is assigned to PM {pm_id}, which is not in the server list.")
                exit(1)
    node2pmid = {}
    for node_id, pm_id in nodeid2pmid.items():
        node_name = nodeid2name[node_id]
        node2pmid[node_name] = pm_id

    # Print # of nodes in each PM
    pmid2nodes = {}
    for node_name, pm_id in node2pmid.items():
        if pmid2nodes.get(pm_id) is None:
            pmid2nodes[pm_id] = []
        pmid2nodes[pm_id].append(node_name)
    for pm_id in sorted(pmid2nodes.keys()):
        print(f"PM {pm_id} has {len(pmid2nodes[pm_id])} nodes.")

    return node2pmid
