import sys
import argparse

def generate_isolated(n, filepath):
    nodes = []
    edges = []

    # Generate nodes in the grid
    for i in range(n):
        nodes.append(i+1)

    # Write nodes and edges to the output file
    with open(filepath, 'w') as f:
        # Write nodes
        f.write(' '.join(map(str, nodes)) + '\n')
        # Write edges
        for edge in edges:
            f.write(f"{edge[0]} {edge[1]}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='A script to generate positions and events')
    parser.add_argument('n', type=int, help='# of nodes')
    parser.add_argument('filepath', type=str, help='Output file name')
    args = parser.parse_args()

    n = args.n
    filepath = args.filepath

    if n < 2:
        print("n >= 2 should be satisfied")
        sys.exit(1)

    generate_isolated(n, filepath)
    print(f"Isolated topology with {n} nodes is generated in {filepath}.")
