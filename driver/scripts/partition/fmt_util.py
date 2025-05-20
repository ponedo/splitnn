# def read_graph_from_topo_file(filepath):
#     """Reads the graph from the old format and returns a node list and adjacency list in the correct format."""
#     nodes = []
#     adjacency_list = {}

#     with open(filepath, 'r') as f:
#         # Read the first line to get node indices
#         nodes = list(map(int, f.readline().split()))

#         # Initialize adjacency list
#         for node in nodes:
#             adjacency_list[node] = []

#         # Read subsequent lines for edges
#         for line in f:
#             u, v = map(int, line.split())
#             adjacency_list[u].append(v)
#             adjacency_list[v].append(u)  # Since the graph is undirected

#     return nodes, adjacency_list


def read_graph_from_topo_file(input_filepath):
    """Reads the graph from the old format and returns a node list and adjacency list in the correct format."""
    nodes = None
    adjacency_list = None
    edge_num = 0

    ################# NODE_NAMES to NODES
    ############ return based on tmp_adjacency_list ? adj_list containing node names
    ############# modify partition_topo_pm, let it not read input file

    # First scan of file: Get nodes and remove dangling nodes
    tmp_adjacency_list = {}
    with open(input_filepath, 'r') as f:
        # Parse all nodes first
        nodes_str = f.readline().strip()
        nodes = nodes_str.split()

        for node_name in nodes:
            tmp_adjacency_list[node_name] = []

        # Scan links
        for line in f:
            node_name_i, node_name_j = line.strip().split()
            if node_name_i not in tmp_adjacency_list:
                tmp_adjacency_list[node_name_i] = []
            if node_name_j not in tmp_adjacency_list:
                tmp_adjacency_list[node_name_j] = []
            tmp_adjacency_list[node_name_i].append(node_name_j)
            tmp_adjacency_list[node_name_j].append(node_name_i)
        
        # Remove dangling nodes
        for node_name in tmp_adjacency_list:
            if len(tmp_adjacency_list[node_name]) == 0:
                nodes.remove(node_name)

    # Second scan of file: Read all links
    with open(input_filepath, 'r') as f:
        # Skip the first line
        nodes_str = f.readline()

        # Scan links
        adjacency_list = {}
        for line in f:
            node_name_i, node_name_j = line.strip().split()
            if node_name_i not in adjacency_list:
                adjacency_list[node_name_i] = []
            if node_name_j not in adjacency_list:
                adjacency_list[node_name_j] = []
            adjacency_list[node_name_i].append(node_name_j)
            adjacency_list[node_name_j].append(node_name_i)
            edge_num += 1

    return nodes, adjacency_list


def write_subtopo_to_file(filepath, nodes, edges, dangling_edges):
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


def write_subtopos_to_file(
    nodes, adjacency_list,
    node2serverid, server_num, input_topo_filepath):
    # Collect nodes and edges for each partition
    subgraphs = {i: {'nodes': [], 'edges': [], 'dangling': []} for i in range(server_num)}

    # Group nodes into their respective subgraphs
    for node, serverid in node2serverid.items():
        subgraphs[serverid]['nodes'].append(node)

    # Allocate Vxlan IDs for dangling edges
    to_alloc_vxlan_id = 4097
    edge2id = {}

    # Group edges into internal and dangling
    for u in nodes:
        for v in adjacency_list[u]:
            if u >= v:
                continue
            u_server_id = node2serverid[u]
            v_server_id = node2serverid[v]
            if u_server_id == v_server_id:
                subgraphs[u_server_id]['edges'].append((u, v))
            else:
                # Allocate vxlan ID for the dangling edge
                cur_vxlan_id = edge2id.get((u, v))
                if cur_vxlan_id is None:
                    edge2id[(u, v)] = to_alloc_vxlan_id
                    cur_vxlan_id = edge2id[(u, v)]
                    to_alloc_vxlan_id += 1
                # Add the dangling edge
                subgraphs[u_server_id]['dangling'].append((u, f"{v}_external_{v_server_id}_{cur_vxlan_id}"))
                subgraphs[v_server_id]['dangling'].append((v, f"{u}_external_{u_server_id}_{cur_vxlan_id}"))

    # Write each subgraph to a file in the new format
    for i in range(server_num):
        tmp_filepath_arr = input_topo_filepath.strip().split('.')
        tmp_filepath_arr = tmp_filepath_arr[0:1] + [f"sub{i}"] + tmp_filepath_arr[1:]
        output_filepath = '.'.join(tmp_filepath_arr)
        write_subtopo_to_file(output_filepath,
                               subgraphs[i]['nodes'],
                               subgraphs[i]['edges'],
                               subgraphs[i]['dangling'])
        print(f"Subgraph {i} written to {output_filepath}")
