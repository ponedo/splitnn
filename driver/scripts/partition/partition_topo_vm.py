import metis
import shutil
import argparse
import time
import numpy as np
from .fmt_util import *
from scipy.sparse import lil_matrix


def create_metis_adjacency_list(nodes, adjacency_list):
    """Converts the adjacency list to METIS format where indices must be contiguous."""
    node_to_index = {node: idx for idx, node in enumerate(nodes)}
    index_to_node = {idx: node for node, idx in node_to_index.items()}
    metis_adjacency_list = []

    start_time = time.time()
    neighbor_count = 0
    for node in nodes:
        # Convert the node's neighbors from IDs to indices
        # neighbors_with_weight = [(node_to_index[neighbor], 1) for neighbor in adjacency_list[node]]  # Add default weight 1
        # metis_adjacency_list.append(neighbors_with_weight)
        neighbors = [node_to_index[neighbor] for neighbor in adjacency_list[node]]  # Add default weight 1
        metis_adjacency_list.append(neighbors)
        neighbor_count += 1
        # if neighbor_count % 1000 == 0:
        #     print(f"Neighbor count: {neighbor_count}")
    # print("Adjacency list conversion completed. Time-cost: ", time.time() - start_time)

    return metis_adjacency_list, node_to_index, index_to_node


def partition_graph_across_vm(nodes, adjacency_list, num_partitions, acc_server_num):
    """Partitions the graph into num_partitions using METIS and writes each subgraph."""
    if num_partitions == 1:
        return nodes, adjacency_list

    # Convert adjacency list to METIS format with correct indices
    start_time = time.time()
    metis_adjacency_list, node_to_index, index_to_node = create_metis_adjacency_list(nodes, adjacency_list)

    # Partition the graph into num_partitions parts using METIS
    # print("Calling metis.part_graph...")
    start_time = time.time()
    _, parts = metis.part_graph(metis_adjacency_list, nparts=num_partitions)
    # print("Partitioning completed. Time-cost: ", time.time() - start_time)

    node2serverid = {}
    for idx, part in enumerate(parts):
        node = index_to_node[idx]  # Convert index back to original node ID
        server_id = part + acc_server_num
        node2serverid[node] = server_id

    return node2serverid


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='A script to generate positions and events')
    parser.add_argument('-f', '--input-file', type=str, required=True, help='Input file name')
    parser.add_argument('-n', '--num-partition', type=int, required=True, help='# of partitions')
    args = parser.parse_args()

    input_filepath = args.input_file
    num_partitions = args.num_partition

    partition_graph_across_vm(input_filepath, num_partitions)
