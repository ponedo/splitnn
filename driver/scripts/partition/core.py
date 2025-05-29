from .fmt_util import *
from .partition_topo_vm import partition_graph_across_vm
from .partition_topo_pm import partition_graph_across_pm
from .compute_tdf import compute_tdf

def partition_topo(input_topo_filepath, server_config_list):
    """
    INPUT: A file "xxx.txt" indicating the topology.
    OUTPUT: A series of files "xxx.sub0.txt", "xxx.sub1.txt", ..., "xxx.subN.txt" indicating the sub-topologies.
    """
    # Read the topology file
    nodes, adjacency_list = read_graph_from_topo_file(input_topo_filepath)

    # Read server configuration
    pm2servernum = {}
    serverid2pmid = {}
    for i, server in enumerate(server_config_list):
        pm_id = server["phyicalMachineId"]
        if pm2servernum.get(pm_id) is None:
            pm2servernum[pm_id] = 0
        pm2servernum[pm_id] += 1
        serverid2pmid[i] = pm_id
    print(f"Partitioning...")
    print(f"# of physical machines: {len(pm2servernum)}")
    print(f"# of servers: {len(server_config_list)}")

    # Output nodeid2pmid
    node2pmid = partition_graph_across_pm(nodes, adjacency_list, server_config_list, input_topo_filepath)

    # Construct the sub-graph of each PM for partitioning
    pmid2nodes = {} # Construct node list
    for pm_id in pm2servernum.keys():
        pmid2nodes[pm_id] = []
    for node, pm_id in node2pmid.items():
        pmid2nodes[pm_id].append(node)
    pmid2adjacencylist = {} # Construct adjacency list
    for pm_id in pmid2nodes.keys():
        pmid2adjacencylist[pm_id] = {}
        for node in pmid2nodes[pm_id]:
            pmid2adjacencylist[pm_id][node] = []
    for node, pm_id in node2pmid.items():
        # If the node is not dangling, add its neighbors in the same PM into the adjacency list
        for neighbor in adjacency_list[node]:
            if node2pmid[neighbor] == pm_id:
                if neighbor not in pmid2adjacencylist[pm_id]:
                    pmid2adjacencylist[pm_id][neighbor] = []
                if node not in pmid2adjacencylist[pm_id]:
                    pmid2adjacencylist[pm_id][node] = []
                pmid2adjacencylist[pm_id][node].append(neighbor)
                pmid2adjacencylist[pm_id][neighbor].append(node)

    # Partition the sub-graph of each PM into VMs
    import concurrent.futures
    def partition_vm_task(pm_id, pmid2nodes, pmid2adjacencylist, pm_server_num, acc_server_num):
        # print(f"Partitioning with PM #{pm_id}...")
        return partition_graph_across_vm(
            pmid2nodes[pm_id], pmid2adjacencylist[pm_id], pm_server_num, acc_server_num
        )
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        acc_server_num = 0
        for pm_id, pm_server_num in pm2servernum.items():
            futures.append(executor.submit(partition_vm_task, pm_id, pmid2nodes, pmid2adjacencylist, pm_server_num, acc_server_num))
            acc_server_num += pm_server_num
        node2serverid = {}
        for future in concurrent.futures.as_completed(futures):
            node2serverid.update(future.result())
    # acc_server_num = 0
    # node2serverid = {}
    # for pm_id, pm_server_num in pm2servernum.items():
    #     print(f"Partitioning with PM #{pm_id}...")
    #     node2serverid_pm = partition_graph_across_vm(
    #         pmid2nodes[pm_id], pmid2adjacencylist[pm_id], pm_server_num, acc_server_num)
    #     node2serverid.update(node2serverid_pm)
    #     acc_server_num += pm_server_num

    # Print # of nodes in each server
    serverid2nodes = {}
    for node_name, server_id in node2serverid.items():
        if serverid2nodes.get(server_id) is None:
            serverid2nodes[server_id] = []
        serverid2nodes[server_id].append(node_name)
    for server_id in sorted(serverid2nodes.keys()):
        print(f"Server {server_id}: {len(serverid2nodes[server_id])} nodes")

    # Scan the adjacency_list, and allocate VXLAN IDs for cross-pm edges and cross-vm-intra-pm edges
    write_subtopos_to_file(nodes, adjacency_list, node2serverid, acc_server_num, input_topo_filepath)

    # Calculate and print TDF of TBS-METIS and METIS
    tbs_metis_node2server_id = node2serverid
    metis_node2server_id = partition_graph_across_vm(
        nodes, adjacency_list, len(server_config_list), 0)
    tbs_metis_tdf = compute_tdf(nodes, adjacency_list, tbs_metis_node2server_id, serverid2pmid)
    metis_tdf = compute_tdf(nodes, adjacency_list, metis_node2server_id, serverid2pmid)

    print(f"TDF of TBS-METIS: {tbs_metis_tdf}")
    print(f"TDF of METIS: {metis_tdf}")

    return tbs_metis_tdf, metis_tdf