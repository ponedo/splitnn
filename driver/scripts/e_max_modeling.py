# Measuring of E_max(n) for T_vm modeling in the paper
from partition.core import partition_topo
from partition.partition_topo_vm import partition_graph_across_vm
from partition.fmt_util import read_graph_from_topo_file
import os
import subprocess
import multiprocessing

############################## constants ##############################

DRIVER_SCRIPT_WORKDIR = os.path.dirname(os.path.abspath(__file__))
DRIVER_WORKDIR = os.path.join(DRIVER_SCRIPT_WORKDIR, "..")
RESULTS_DIR = os.path.join(DRIVER_WORKDIR, "..", "results")
os.chdir(DRIVER_WORKDIR) # Change current working directory
LOCAL_TOPO_DIR = os.path.join(DRIVER_WORKDIR, "topo")

############################ script config ############################

n_range = range(1, 2)
run_num = 10
topologies = [
    ["grid", "100", "100"],
    ["clos", "32"],
    ["as", "large"],
]

#######################################################################

def get_full_topo_filename(topo_args):
    return f"{'_'.join(topo_args)}.txt"

def prepare_topologies():
    for topo in topologies:
        # Generate the topology file
        print(f"Processing topology: {topo}")
        topo_type = topo[0]
        full_topo_filename = get_full_topo_filename(topo)
        full_topo_filepath = os.path.join(LOCAL_TOPO_DIR, full_topo_filename)
        generate_topo_type_script_path = os.path.join(DRIVER_WORKDIR, "scripts", "topo", f"generate_{topo_type}_topo.py")
        try:
            generate_topology_cmd = \
                ["python3", generate_topo_type_script_path] + topo[1:] + [full_topo_filepath]
        except IndexError:
            generate_topology_cmd = \
                ["python3", generate_topo_type_script_path, full_topo_filepath]
        result = subprocess.run(generate_topology_cmd, capture_output=True, text=True)

def generate_topo_nodes_and_adjlist(topo):
    # Generate nodes and adjlist
    topo_type = topo[0]
    full_topo_filename = get_full_topo_filename(topo)
    full_topo_filepath = os.path.join(LOCAL_TOPO_DIR, full_topo_filename)
    nodes, adjacency_list = read_graph_from_topo_file(full_topo_filepath)
    return nodes, adjacency_list

def partition_topo_pseudo(nodes, adjacency_list, n):
    # Perform the portition but not storing the result into file
    node2serverid = partition_graph_across_vm(nodes, adjacency_list, n, 0, random=True)
    return node2serverid

def get_partition_stats(nodes, adjacency_list, node2serverid, n):
    # Count the number of edges in each partition as well dangling edges
    partition_stats = {}
    for _, server_id in node2serverid.items():
        if server_id not in partition_stats:
            partition_stats[server_id] = {
                "node_count": 0,
                "edge_count": 0,
                "dangling_edges": 0
            }
    # Count nodes in each partition
    for node in nodes:
        server_id = node2serverid[node]
        if server_id in partition_stats:
            partition_stats[server_id]["node_count"] += 1
        else:
            partition_stats[server_id] = {
                "node_count": 1,
                "edge_count": 0,
                "dangling_edges": 0
            }

    # Count edges in each partition
    for u in nodes:
        for v in adjacency_list[u]:
            if u >= v:
                continue
            u_server_id = node2serverid[u]
            v_server_id = node2serverid[v]
            if u_server_id == v_server_id:
                partition_stats[u_server_id]["edge_count"] += 1
            else:
                partition_stats[u_server_id]["edge_count"] += 1
                partition_stats[u_server_id]["edge_count"] += 1
                partition_stats[u_server_id]["dangling_edges"] += 1
                partition_stats[v_server_id]["dangling_edges"] += 1
    # print(partition_stats)
    return partition_stats

def one_run(run_idx):
    topo2max_edge_counts = {}
    for topo in topologies:
        # Get max subpartition edge count for each n value
        max_edge_counts = []
        for n in n_range:
            print(f"Run_idx: {run_idx}, Topo: {topo}, n: {n}...")

            # Generate nodes and adjacency list for the topology
            nodes, adjacency_list = generate_topo_nodes_and_adjlist(topo)

            # Partition the topology
            node2serverid = partition_topo_pseudo(nodes, adjacency_list, n)

            # Get partition stats
            partition_stats = get_partition_stats(nodes, adjacency_list, node2serverid, n)

            # Get largest edge count
            max_edge_count = max(partition_stats[server_id]["edge_count"] for server_id in partition_stats)
            max_edge_counts.append(max_edge_count)

        # Store the max edge counts for the current topology
        topo2max_edge_counts[topo[0]] = max_edge_counts

    return topo2max_edge_counts

#######################################################################
# Main execution starts here
if __name__ == "__main__":
    print("-" * 20)
    print("Starting partitioning runs...")
    print(f"Number of runs: {run_num}")
    print(f"Topology configurations: {topologies}")
    print(f"Node range: {n_range}")
    print("-" * 20)

    # Prepare the topologies
    prepare_topologies()

    import concurrent.futures

    # Run the partitioning multiple times in parallel
    run_idx2topo2max_edge_counts = []
    num_cores = multiprocessing.cpu_count()
    num_workers = max(1, int(num_cores * 2 / 3))
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(one_run, run_idx) for run_idx in range(run_num)]
        for future in concurrent.futures.as_completed(futures):
            topo2max_edge_counts = future.result()
            run_idx2topo2max_edge_counts.append(topo2max_edge_counts)
    print("-" * 20)
    # # Run the partitioning multiple times
    # run_idx2topo2max_edge_counts = []
    # for run_idx in range(run_num):
    #     print(f"Run {run_idx + 1}/{run_num}...")
    #     topo2max_edge_counts = one_run()
    #     run_idx2topo2max_edge_counts.append(topo2max_edge_counts)
    #     print("-" * 20)

    # Average the results across runs
    topo2avg_max_edge_counts = {}
    for topo in topologies:
        # Initialize the average counts for this topology
        avg_max_edge_counts = [0] * len(n_range)
        for run_idx in range(run_num):
            # Get the max edge counts for this topology in this run
            max_edge_counts = run_idx2topo2max_edge_counts[run_idx][topo[0]]
            # Add to the average counts
            for i in range(len(n_range)):
                avg_max_edge_counts[i] += max_edge_counts[i]
        # Average the counts across runs
        topo2avg_max_edge_counts[topo[0]] = [count / run_num for count in avg_max_edge_counts]

    # Average the results across topologies
    average_max_edge_counts = []
    for i in range(len(n_range)):
        avg_count = sum(topo2avg_max_edge_counts[topo][i] for topo in topo2avg_max_edge_counts) / len(topo2avg_max_edge_counts)
        average_max_edge_counts.append(avg_count)

    # Store the results to a file
    output_filepath = os.path.join(RESULTS_DIR, "E_max.txt")
    with open(output_filepath, 'w') as f:
        f.write(f"Number of runs: {run_num}\n")
        f.write(f"Topology configurations: {topologies}\n")
        f.write(f"Node range: {list(n_range)}\n")
        f.write("Average max edge counts:\n")
        # Store results of each run
        for run_idx, topo2avg_max_edge_counts in enumerate(run_idx2topo2max_edge_counts):
            f.write(f"Run {run_idx + 1}:\n")
            for topo, max_edge_counts in topo2avg_max_edge_counts.items():
                f.write(f"{topo}: {max_edge_counts}\n")
        # Store results averaged across runs
        f.write("-" * 20 + "\n")
        f.write(f"Results averaged across runs:\n")
        for topo, max_edge_counts in topo2avg_max_edge_counts.items():
            f.write(f"{topo}: {max_edge_counts}\n")
        # Store results averaged across topologies
        f.write("-" * 20 + "\n")
        f.write(f"Results averaged across runs and topos: {average_max_edge_counts}\n")
