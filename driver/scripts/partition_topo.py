import metis
import shutil
import argparse

def read_graph_from_file(filepath):
    """Reads the graph from the old format and returns a node list and adjacency list in the correct format."""
    nodes = []
    adjacency_list = {}

    with open(filepath, 'r') as f:
        # Read the first line to get node indices
        nodes = list(map(int, f.readline().split()))

        # Initialize adjacency list
        for node in nodes:
            adjacency_list[node] = []

        # Read subsequent lines for edges
        for line in f:
            u, v = map(int, line.split())
            adjacency_list[u].append(v)
            adjacency_list[v].append(u)  # Since the graph is undirected

    return nodes, adjacency_list

def create_metis_adjacency_list(nodes, adjacency_list):
    """Converts the adjacency list to METIS format where indices must be contiguous."""
    node_to_index = {node: idx for idx, node in enumerate(nodes)}
    index_to_node = {idx: node for node, idx in node_to_index.items()}

    metis_adjacency_list = []

    for node in nodes:
        # Convert the node's neighbors from IDs to indices
        neighbors = [(node_to_index[neighbor], 1) for neighbor in adjacency_list[node]]  # Add default weight 1
        metis_adjacency_list.append(neighbors)

    return metis_adjacency_list, node_to_index, index_to_node

def write_subgraph_to_file(filepath, nodes, edges, dangling_edges):
    """Writes the subgraph to the new format file."""
    with open(filepath, 'w') as f:
        # Write nodes
        f.write(' '.join(map(str, nodes)) + '\n')

        # Write internal edges
        for edge in edges:
            f.write(f"{edge[0]} {edge[1]}\n")

        # Write dangling edges
        for edge in dangling_edges:
            f.write(f"{edge[0]} {edge[1]}\n")

def partition_graph(filepath, num_partitions):
    """Partitions the graph into num_partitions using METIS and writes each subgraph."""
    nodes, adjacency_list = read_graph_from_file(filepath)

    if num_partitions == 1:
        
        tmp_filepath_arr = filepath.strip().split('.')
        tmp_filepath_arr = tmp_filepath_arr[0:1] + [f"sub0"] + tmp_filepath_arr[1:]
        output_filepath = '.'.join(tmp_filepath_arr)
        shutil.copyfile(filepath, output_filepath)
        return

    # Convert adjacency list to METIS format with correct indices
    metis_adjacency_list, node_to_index, index_to_node = create_metis_adjacency_list(nodes, adjacency_list)

    # Partition the graph into num_partitions parts using METIS
    _, parts = metis.part_graph(metis_adjacency_list, nparts=num_partitions)

    # Collect nodes and edges for each partition
    subgraphs = {i: {'nodes': [], 'edges': [], 'dangling': []} for i in range(num_partitions)}

    # Group nodes into their respective subgraphs
    for idx, part in enumerate(parts):
        node = index_to_node[idx]  # Convert index back to original node ID
        subgraphs[part]['nodes'].append(node)

    # Allocate Vxlan IDs for dangling edges
    to_alloc_vxlan_id = 4097
    edge2id = {}

    # Group edges into internal and dangling
    for u in nodes:
        u_index = node_to_index[u]
        for v in adjacency_list[u]:
            if u >= v:
                continue
            v_index = node_to_index[v]
            u_part = parts[u_index]
            v_part = parts[v_index]
            if u_part == v_part:
                subgraphs[u_part]['edges'].append((u, v))
            else:
                # Allocate vxlan ID for the dangling edge
                cur_vxlan_id = edge2id.get((u, v))
                if cur_vxlan_id is None:
                    edge2id[(u, v)] = to_alloc_vxlan_id
                    cur_vxlan_id = edge2id[(u, v)]
                    to_alloc_vxlan_id += 1
                # Add the dangling edge
                subgraphs[u_part]['dangling'].append((u, f"{v}_external_{v_part}_{cur_vxlan_id}"))
                subgraphs[v_part]['dangling'].append((v, f"{u}_external_{u_part}_{cur_vxlan_id}"))

    # Write each subgraph to a file in the new format
    for i in range(num_partitions):
        tmp_filepath_arr = filepath.strip().split('.')
        tmp_filepath_arr = tmp_filepath_arr[0:1] + [f"sub{i}"] + tmp_filepath_arr[1:]
        output_filepath = '.'.join(tmp_filepath_arr)
        write_subgraph_to_file(output_filepath,
                               subgraphs[i]['nodes'],
                               subgraphs[i]['edges'],
                               subgraphs[i]['dangling'])
        print(f"Subgraph {i} written to {output_filepath}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='A script to generate positions and events')
    parser.add_argument('-f', '--input-file', type=str, required=True, help='Input file name')
    parser.add_argument('-n', '--num-partition', type=int, required=True, help='# of partitions')
    args = parser.parse_args()

    input_filepath = args.input_file
    num_partitions = args.num_partition

    partition_graph(input_filepath, num_partitions)
