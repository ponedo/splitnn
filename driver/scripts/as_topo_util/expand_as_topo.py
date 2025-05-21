import json
import argparse
from collections import defaultdict, Counter

def load_as_list(as_list_path, region_filter):
    """Load AS numbers from the AS list JSONL file and filter by region."""
    as_numbers = {}
    with open(as_list_path, 'r') as file:
        for line in file:
            data = json.loads(line)
            as_numbers[data["asn"]] = data["country"]["iso"]
    return as_numbers

def load_as_relationships(as_rel_path):
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
            graph[as1].add(as2)
            graph[as2].add(as1)
    return graph

def expand_topology(graph, as_numbers, target_count, region_filter):
    """Expand the topology by iteratively adding ASes with the most connections to existing nodes."""
    if not graph:
        print("No valid topology.")
        return {}
    
    # Initialize with ASes from the specified regions
    seed_asns = {asn for asn, country in as_numbers.items() if country in region_filter and asn in graph}
    if not seed_asns:
        print("No ASes found in the specified regions.")
        return {}
    
    expanded_graph = {asn: set() for asn in seed_asns}
    for asn in seed_asns:
        expanded_graph[asn] = graph[asn].copy()
    
    while len(expanded_graph) < target_count:
        # Count connections between current topology and outside nodes
        candidate_counts = Counter()
        for asn in expanded_graph:
            for neighbor in graph[asn]:
                if neighbor not in expanded_graph:
                    candidate_counts[neighbor] += 1
        
        if not candidate_counts:
            print("No more connections available for expansion.")
            break
        
        # Select AS(es) with the highest number of connections to current topology
        max_connections = max(candidate_counts.values())
        candidates = [asn for asn, count in candidate_counts.items() if count == max_connections]
        
        # Add selected AS(es) to the topology
        for asn in candidates:
            if len(expanded_graph) >= target_count:
                break
            expanded_graph[asn] = graph[asn].copy()
        
        # Remove dangling edges (edges to nodes outside expanded_graph)
        for asn in expanded_graph:
            expanded_graph[asn] = {neighbor for neighbor in expanded_graph[asn] if neighbor in expanded_graph}
        
        # Compute total link number in current topology
        total_links = sum(len(neighbors) for neighbors in expanded_graph.values()) // 2
        
        print(f"Iteration {len(expanded_graph)}: Added {len(candidates)} ASes, max_connections {max_connections}, total links {total_links}, total nodes {len(expanded_graph)}")
    
    # Ensure final output only contains edges with nodes in the expanded graph
    valid_nodes = set(expanded_graph.keys())
    for asn in expanded_graph:
        expanded_graph[asn] = {neighbor for neighbor in expanded_graph[asn] if neighbor in valid_nodes}
    
    # Collect country codes of final topology
    final_countries = {as_numbers[asn] for asn in expanded_graph if asn in as_numbers}
    print(f"Final country codes in topology: {final_countries}")
    
    return expanded_graph

def save_expanded_topology(graph, output_path):
    """Save the expanded topology to a file."""
    valid_nodes = set(graph.keys())
    with open(output_path, 'w') as file:
        file.write(" ".join(valid_nodes) + "\n")
        for as1, neighbors in graph.items():
            for as2 in neighbors:
                if as1 in valid_nodes and as2 in valid_nodes and as1 < as2:  # Ensure only valid edges are saved
                    file.write(f"{as1} {as2}\n")

def main():
    parser = argparse.ArgumentParser(description="Expand AS topology from CAIDA dataset")
    parser.add_argument("as_list_path", type=str, help="Path to the AS list JSONL file")
    parser.add_argument("as_rel_path", type=str, help="Path to the AS relationship file")
    parser.add_argument("output_path", type=str, help="Path to save the expanded topology")
    parser.add_argument("target_count", type=int, help="Target AS count for expansion")
    parser.add_argument("regions", type=str, help="Comma-separated list of region codes to initialize the topology")
    args = parser.parse_args()
    
    region_filter = set(args.regions.split(","))
    as_numbers = load_as_list(args.as_list_path, region_filter)
    graph = load_as_relationships(args.as_rel_path)
    expanded_graph = expand_topology(graph, as_numbers, args.target_count, region_filter)
    save_expanded_topology(expanded_graph, args.output_path)

if __name__ == "__main__":
    main()
