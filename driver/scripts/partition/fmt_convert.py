import argparse


def convert_topo_to_metis_graph(input_filepath, output_filepath):
    node_names = None
    adj_matrix = None
    edge_weight = 1
    edge_num = 0

    # First scan of file: Get nodes and remove dangling nodes
    tmp_adj_matrix = {}
    with open(input_filepath, 'r') as f:
        # Parse all nodes first
        nodes_str = f.readline().strip()
        node_names = nodes_str.split()

        for node_name in node_names:
            tmp_adj_matrix[node_name] = []

        # Scan links
        for line in f:
            node_name_i, node_name_j = line.strip().split()
            if node_name_i not in tmp_adj_matrix:
                tmp_adj_matrix[node_name_i] = []
            if node_name_j not in tmp_adj_matrix:
                tmp_adj_matrix[node_name_j] = []
            tmp_adj_matrix[node_name_i].append(node_name_j)
            tmp_adj_matrix[node_name_j].append(node_name_i)
        
        # Remove dangling nodes
        for node_name in tmp_adj_matrix:
            if len(tmp_adj_matrix[node_name]) == 0:
                node_names.remove(node_name)
        
        # Allocate integer node id
        node_name2id = {}
        nodeid2name = {}
        for i, node_name in enumerate(node_names):
            node_name2id[node_name] = i + 1
            nodeid2name[i + 1] = node_name
        node_ids = nodeid2name.keys()

    # Second scan of file: Read all links
    with open(input_filepath, 'r') as f:
        # Skip the first line
        nodes_str = f.readline()

        # Scan links
        adj_matrix = {}
        for line in f:
            node_name_i, node_name_j = line.strip().split()
            node_id_i, node_id_j = node_name2id[node_name_i], node_name2id[node_name_j]
            if node_id_i not in adj_matrix:
                adj_matrix[node_id_i] = []
            if node_id_j not in adj_matrix:
                adj_matrix[node_id_j] = []
            adj_matrix[node_id_i].append((node_id_j, edge_weight))
            adj_matrix[node_id_j].append((node_id_i, edge_weight))
            edge_num += 1

    # Generate a graph with edge weight
    node_num = len(node_ids)
    with open(output_filepath, 'w') as f:
        f.write(f"{node_num} {edge_num} 1\n")
        for i, node_id in enumerate(sorted(adj_matrix)):
            assert i == node_id - 1
            # Write a line containing node name
            node_name = nodeid2name[node_id]
            f.write(f"% node_name: {node_name}\n")
            # Write a line for neighbors
            adj_line = ""
            adj = adj_matrix[node_id]
            for neighbor, edge_weight in adj:
                adj_line += f" {neighbor} {edge_weight}"
            f.write(f"{adj_line}\n")

    return node_ids, nodeid2name, adj_matrix, edge_num


def convert_metis_graph_to_topo(input_filepath, output_filepath):
    pass


def convert_adjlist_to_metis_graph(nodes, adjacency_list, output_filepath):
    # Allocate integer node id
    node_name2id = {}
    nodeid2name = {}
    for i, node_name in enumerate(nodes):
        node_name2id[node_name] = i + 1
        nodeid2name[i + 1] = node_name
    node_ids = nodeid2name.keys()

    # Generate a graph with edge weight
    edge_weight = 1
    edge_num = 0
    adj_matrix = {}
    for node_name in nodes:
        node_id = node_name2id[node_name]
        for neighbor in adjacency_list[node_name]:
            neighbor_id = node_name2id[neighbor]
            if node_id not in adj_matrix:
                adj_matrix[node_id] = []
            if neighbor_id not in adj_matrix:
                adj_matrix[neighbor_id] = []
            adj_matrix[node_id].append((neighbor_id, edge_weight))
            adj_matrix[neighbor_id].append((node_id, edge_weight)) # adjacency_list is already bidirectional
            edge_num += 1

    # Generate a graph with edge weight
    node_num = len(node_ids)
    with open(output_filepath, 'w') as f:
        f.write(f"{node_num} {edge_num} 1\n")
        for i, node_id in enumerate(sorted(adj_matrix)):
            assert i == node_id - 1
            # Write a line containing node name
            node_name = nodeid2name[node_id]
            f.write(f"% node_name: {node_name}\n")
            # Write a line for neighbors
            adj_line = ""
            adj = adj_matrix[node_id]
            for neighbor, edge_weight in adj:
                adj_line += f" {neighbor} {edge_weight}"
            f.write(f"{adj_line}\n")

    return node_ids, nodeid2name, adj_matrix, edge_num