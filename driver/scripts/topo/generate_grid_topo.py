import argparse

def generate_grid_topology(x, y, filepath):
    nodes = []
    edges = []

    # Generate nodes in the grid
    for i in range(x):
        for j in range(y):
            node_id = i * y + j + 1  # Node indexing starts at 1
            nodes.append(node_id)

    # Generate edges within the grid, considering marginal cases where x or y might be 1
    for i in range(x):
        for j in range(y):
            node_id = i * y + j + 1

            # Connect to the right neighbor, wrap around if y > 1
            if y > 1:
                if j < y - 1:
                    right_neighbor = node_id + 1
                    edges.append((node_id, right_neighbor))
                else:
                    # Connect the right boundary to the left boundary (wrap around)
                    left_neighbor = node_id - (y - 1)
                    edges.append((node_id, left_neighbor))

            # Connect to the bottom neighbor, wrap around if x > 1
            if x > 1:
                if i < x - 1:
                    bottom_neighbor = node_id + y
                    edges.append((node_id, bottom_neighbor))
                else:
                    # Connect the bottom boundary to the top boundary (wrap around)
                    top_neighbor = node_id - (x - 1) * y
                    edges.append((node_id, top_neighbor))

    # Write nodes and edges to the output file
    with open(filepath, 'w') as f:
        # Write nodes
        f.write(' '.join(map(str, nodes)) + '\n')
        # Write edges
        for edge in edges:
            f.write(f"{edge[0]} {edge[1]}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='A script to generate grid topology')
    parser.add_argument('x', type=int, help='Grid topology length')
    parser.add_argument('y', type=int, help='Grid topology width')
    parser.add_argument('filepath', type=str, help='Output file name')
    args = parser.parse_args()

    x = args.x
    y = args.y
    filepath = args.filepath

    generate_grid_topology(x, y, filepath)
    print(f"Grid topology with {x}x{y} nodes and toroidal edges generated in {filepath}.")
