import yaml
import argparse

def generate_clos_topology_yaml(k, filepath='clos_topology.yaml'):
    nodes = []
    edges = []

    p = k
    c = k // 2
    superspine_num = (k // 2) ** 2
    spine_per_pod = k // 2
    leaf_per_pod = k // 2

    name2id = {}
    node_id = 1

    print(f"Generating nodes...")
    # Generate leaves, spines for each pod
    for pod_id in range(1, p + 1):
        # Leaves and spines
        for leaf_id in range(1, leaf_per_pod + 1):
            node_name = f'pod{pod_id}_leaf{leaf_id}'
            name2id[node_name] = node_id
            nodes.append(node_id)
            node_id += 1
        
        for spine_id in range(1, spine_per_pod + 1):
            node_name = f'pod{pod_id}_spine{spine_id}'
            name2id[node_name] = node_id
            nodes.append(node_id)
            node_id += 1

    # Superspines (shared across all pods)
    for superspine_id in range(1, superspine_num + 1):
        node_name = f'superspine{superspine_id}'
        name2id[node_name] = node_id
        nodes.append(node_id)
        node_id += 1

    print(f"Generating links...")
    # Generate clients connected to each leaf
    client_id = 1
    for pod_id in range(1, p + 1):
        for leaf_id in range(1, leaf_per_pod + 1):
            for client_id in range(1, c + 1):
                node_name = f'pod{pod_id}_leaf{leaf_id}_client{client_id}'
                name2id[node_name] = node_id
                nodes.append(node_id)
                node_id += 1
                client_id += 1

    # Create leaf to spine links for each pod
    for pod_id in range(1, p + 1):
        for leaf_id in range(1, leaf_per_pod + 1):
            for spine_id in range(1, spine_per_pod + 1):
                node_id_i = name2id[f'pod{pod_id}_leaf{leaf_id}']
                node_id_j = name2id[f'pod{pod_id}_spine{spine_id}']
                edges.append((node_id_i, node_id_j))

    # Create spine to superspine links (shared across pods)
    for pod_id in range(1, p + 1):
        superspine_id = 1
        for spine_id in range(1, spine_per_pod + 1):
            for i in range(1, k // 2 + 1):
                node_id_i = name2id[f'pod{pod_id}_spine{spine_id}']
                node_id_j = name2id[f'superspine{superspine_id}']
                edges.append((node_id_i, node_id_j))
                superspine_id += 1

    # Create client to leaf links
    client_id = 1
    for pod_id in range(1, p + 1):
        for leaf_id in range(1, leaf_per_pod + 1):
            for client_id in range(1, c + 1):
                node_id_i = name2id[f'pod{pod_id}_leaf{leaf_id}_client{client_id}']
                node_id_j = name2id[f'pod{pod_id}_leaf{leaf_id}']
                edges.append((node_id_i, node_id_j))

    print(f"Writing topology into file...")
    # Write nodes and edges to the output file
    with open(filepath, 'w') as f:
        # Write nodes
        f.write(' '.join(map(str, nodes)) + '\n')
        # Write edges
        for edge in edges:
            f.write(f"{edge[0]} {edge[1]}\n")

    print(f"Topology generated successfully.")

    total_nodes = int((5 / 4) * (k ** 2) + (k ** 3) / 4)
    print(f"Total nodes: {total_nodes} ({superspine_num + p * (spine_per_pod + leaf_per_pod) + c * leaf_per_pod * p})")


def main():
    parser = argparse.ArgumentParser(description='Generate CLOS topology YAML for Containerlab.')
    parser.add_argument('k', type=int, help='Fat Tree parameter (number of ports per switch)')
    parser.add_argument('filepath', type=str, help='Output file name')
    args = parser.parse_args()

    generate_clos_topology_yaml(args.k, args.filepath)


if __name__ == "__main__":
    main()