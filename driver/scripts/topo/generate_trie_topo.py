import sys
import argparse

def generate_trie_topology(n, k, filepath):
    nodes = []
    edges = []

    # Generate nodes
    for i in range(n):
        nodes.append(i + 1)

    # Generate edges
    cur_layer = 0
    upper_layer_node_num = 0
    all_upper_layer_node_num = 0
    cur_node_num = 0
    all_nodes_added = False
    while True:
        cur_layer_max_node_num = k ** cur_layer
        for i in range(cur_layer_max_node_num):
            if cur_layer_max_node_num == 1:
                cur_node_num += 1
                break
            cur_node_code = cur_node_num + 1
            cur_node_in_layer_id = i
            parent_node_in_layer_id = cur_node_in_layer_id // k
            parent_node_id = \
                all_upper_layer_node_num - upper_layer_node_num + parent_node_in_layer_id
            parent_node_code = parent_node_id + 1
            edges.append((cur_node_code, parent_node_code))
            cur_node_num += 1
            if cur_node_num >= n:
                all_nodes_added = True
                break
        if all_nodes_added:
            break
        cur_layer += 1
        upper_layer_node_num = cur_layer_max_node_num
        all_upper_layer_node_num += cur_layer_max_node_num

    # Write nodes and edges to the output file
    with open(filepath, 'w') as f:
        # Write nodes
        f.write(' '.join(map(str, nodes)) + '\n')
        # Write edges
        for edge in edges:
            f.write(f"{edge[0]} {edge[1]}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='A script to generate trie topology')
    parser.add_argument('n', type=int, help='Node number')
    parser.add_argument('k', type=int, help='Max number of children for each node')
    parser.add_argument('filepath', type=str, help='Output file name')
    args = parser.parse_args()

    n = args.n
    k = args.k
    filepath = args.filepath

    generate_trie_topology(n, k, filepath)
    print(f"Trie topology generated in {filepath}.")
