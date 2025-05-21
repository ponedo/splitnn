import argparse


def generate_star_topology(n, filepath):
    nodes = []
    edges = []

    # Generate nodes
    for i in range(n):
        nodes.append(i + 1)
        if i > 0:
            edges.append((1, i + 1))
    # Write nodes and edges to the output file
    with open(filepath, 'w') as f:
        # Write nodes
        f.write(' '.join(map(str, nodes)) + '\n')
        # Write edges
        for edge in edges:
            f.write(f"{edge[0]} {edge[1]}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='A script to generate star topology')
    parser.add_argument('n', type=int, help='Node number')
    parser.add_argument('filepath', type=str, help='Output file name')
    args = parser.parse_args()

    n = args.n
    filepath = args.filepath

    generate_star_topology(n, filepath)
    print(f"star topology generated in {filepath}.")
