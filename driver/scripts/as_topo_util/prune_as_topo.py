import json
import heapq
import argparse
from collections import defaultdict

def load_as_list(as_list_path):
    """Load AS numbers from the AS list JSONL file."""
    as_numbers = set()
    with open(as_list_path, 'r') as file:
        for line in file:
            data = json.loads(line)
            as_numbers.add(data["asn"])
    return as_numbers

def load_as_relationships(as_rel_path, as_numbers):
    """Load AS relationships from the relationship file, ignoring comments."""
    graph = defaultdict(set)
    with open(as_rel_path, 'r') as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("#"):
                continue  # Ignore comment lines
            parts = line.split("|")
            if len(parts) != 3:
                continue  # Ignore malformed lines
            as1, as2 = parts[0], parts[1]
            if as1 in as_numbers and as2 in as_numbers:
                graph[as1].add(as2)
                graph[as2].add(as1)
    return graph

def prune_topology(graph, target_count):
    """Iteratively remove nodes until the topology has the target AS count."""
    iteration = 0
    while len(graph) > target_count:
        iteration += 1
        # Identify leaf nodes (nodes with only one connection)
        leaf_nodes = [asn for asn, neighbors in graph.items() if len(neighbors) == 1]
        pruned_count = len(leaf_nodes)
        min_degree = min(len(neighbors) for neighbors in graph.values()) if graph else 0
        
        if leaf_nodes:
            for leaf in leaf_nodes:
                if leaf in graph:
                    neighbor = next(iter(graph[leaf]))  # Get the single neighbor
                    graph[neighbor].discard(leaf)  # Remove leaf from its neighbor
                    del graph[leaf]  # Remove leaf node itself
        else:
            # If no leaf nodes, remove nodes with the lowest degree
            low_degree_nodes = [asn for asn, neighbors in graph.items() if len(neighbors) == min_degree]
            pruned_count = len(low_degree_nodes)
            
            for node in low_degree_nodes:
                for neighbor in graph[node]:
                    graph[neighbor].discard(node)  # Remove node from its neighbors
                del graph[node]  # Remove node itself
        
        print(f"Iteration {iteration}: Pruned {pruned_count} nodes, lowest degree {min_degree}, remaining {len(graph)} nodes")
    
    return graph

def save_pruned_topology(graph, output_path):
    """Save the pruned topology to a file."""
    with open(output_path, 'w') as file:
        file.write(" ".join(graph.keys()) + "\n")
        for as1, neighbors in graph.items():
            for as2 in neighbors:
                if as1 < as2:  # Avoid duplicate edges
                    file.write(f"{as1} {as2}\n")

def main():
    parser = argparse.ArgumentParser(description="Prune AS topology from CAIDA dataset")
    parser.add_argument("as_list_path", type=str, help="Path to the AS list JSONL file")
    parser.add_argument("as_rel_path", type=str, help="Path to the AS relationship file")
    parser.add_argument("output_path", type=str, help="Path to save the pruned topology")
    parser.add_argument("target_count", type=int, help="Target AS count after pruning")
    args = parser.parse_args()
    
    as_numbers = load_as_list(args.as_list_path)
    graph = load_as_relationships(args.as_rel_path, as_numbers)
    pruned_graph = prune_topology(graph, args.target_count)
    save_pruned_topology(pruned_graph, args.output_path)

if __name__ == "__main__":
    main()
