DEFAULT_CROSS_MACHINE_BW = 10000 # Mbps

cross_machine_bw = {
    (0, 1): 10000,
    (0, 2): 10000,
    (0, 3): 10000,
    (0, 4): 10000,
    (0, 5): 10000,
    (1, 2): 10000,
    (1, 3): 10000,
    (1, 4): 10000,
    (1, 5): 10000,
    (2, 3): 10000,
    (2, 4): 10000,
    (2, 5): 10000,
    (3, 4): 10000,
    (3, 5): 10000,
    (4, 5): 10000,
}

def get_cross_machine_bw(pm_id_0, pm_id_1):
    assert not pm_id_0 == pm_id_1
    if pm_id_0 > pm_id_1:
        pm_id_0, pm_id_1 = pm_id_1, pm_id_0
    cross_machine_bw_key = (pm_id_0, pm_id_1)
    return cross_machine_bw.get(cross_machine_bw_key, DEFAULT_CROSS_MACHINE_BW)

def compute_tdf(nodes, adjacency_list, node2server_id, serverid2pmid):
    # Suppose each virtual link is 100 Mbps, the load on a cross-machine
    # link is the sum of the loads of all virtual links that traverse it.

    # Traverse the adjacency list and compute the load on each cross-machine link
    cross_machine_load = {}
    for node in nodes:
        server_id = node2server_id[node]
        pm_id = serverid2pmid[server_id]
        for neighbor in adjacency_list[node]:
            neighbor_server_id = node2server_id[neighbor]
            neighbor_pm_id = serverid2pmid[neighbor_server_id]
            if pm_id < neighbor_pm_id: # Avoid double counting
                # This is a cross-machine link
                cross_machine_bw_key = (min(pm_id, neighbor_pm_id), max(pm_id, neighbor_pm_id))
                if cross_machine_bw_key not in cross_machine_load:
                    cross_machine_load[cross_machine_bw_key] = 0
                cross_machine_load[cross_machine_bw_key] += 100  # Assuming each link has a load of 100Mbps

    # Calculate cross-machine relative load
    cross_machine_relative_load = {}
    for (pm_id_0, pm_id_1), load in cross_machine_load.items():
        bw = get_cross_machine_bw(pm_id_0, pm_id_1)
        if bw > 0:
            relative_load = load / bw
        else:
            relative_load = float('inf')  # Infinite load if bandwidth is zero
        cross_machine_relative_load[(pm_id_0, pm_id_1)] = relative_load

    # Calculate TDF
    tdf = max(cross_machine_relative_load.values(), default=0)
    return tdf
