import sys
from collections import defaultdict

def analyze_graph(file_path):
    with open(file_path, 'r') as f:
        lines = f.readlines()

    # First line: node list
    nodes = list(map(int, lines[0].split()))
    node_set = set(nodes)
    n = len(node_set)

    # Build edge list and degree counter
    edges = set()
    degree = defaultdict(int)

    for line in lines[1:]:
        u, v = map(int, line.split())
        if u == v:
            continue  # skip self-loops
        edge = tuple(sorted((u, v)))  # undirected
        if edge not in edges:
            edges.add(edge)
            degree[u] += 1
            degree[v] += 1

    m = len(edges)

    degree_values = list(degree.values())
    min_deg = min(degree_values) if degree_values else 0
    max_deg = max(degree_values) if degree_values else 0
    avg_deg = sum(degree_values) / n if n > 0 else 0

    # Graph density (undirected)
    density = (2 * m) / (n * (n - 1)) if n > 1 else 0

    print(f"Node count     : {n}")
    print(f"Edge count     : {m}")
    print(f"Min degree     : {min_deg}")
    print(f"Average degree : {avg_deg:.2f}")
    print(f"Max degree     : {max_deg}")
    print(f"Graph density  : {density:.6f}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python analyze_graph.py <path_to_file>")
    else:
        analyze_graph(sys.argv[1])
