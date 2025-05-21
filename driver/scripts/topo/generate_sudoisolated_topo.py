import sys
import argparse

def generate_isolated(l, n, filepath):
    nodes = []
    edges = []

    # Generate nodes in the grid
    for i in range(n + 2):
        nodes.append(i+1)

    # Generate links connecting first two big nodes
    for i in range(l):
        edges.append((1, 2))

    # Write nodes and edges to the output file
    with open(filepath, 'w') as f:
        # Write nodes
        f.write(' '.join(map(str, nodes)) + '\n')
        # Write edges
        for edge in edges:
            f.write(f"{edge[0]} {edge[1]}\n")


if __name__ == "__main__":
    # A sudo isolated topo is consisted of:
    # 1. two big nodes connected with *l* links
    # 2. other *n* isolated nodes
    parser = argparse.ArgumentParser(description='A script to generate sudo topo')
    parser.add_argument('l', type=int, help='# of links that connect first two big nodes')
    parser.add_argument('n', type=int, help='# of nodes')
    parser.add_argument('filepath', type=str, help='Output file name')
    args = parser.parse_args()

    l = args.l
    n = args.n
    filepath = args.filepath

    if n < 0:
        print("n >= 0 should be satisfied")
        sys.exit(1)

    generate_isolated(l, n, filepath)
    print(f"Sudo isolated topology containing {l} links and {n} isolated nodes is generated in {filepath}.")
