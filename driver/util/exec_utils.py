from .common import *

# Op templates
set_netsysctl_op = {
    "op": "set_netsysctl",
    "args": [
        "/proc/sys/net/ipv6/conf/all/forwarding",
        "1"
    ]
}
setup_lo_op = {
    "op": "linkup",
    "args": [
        "lo"
    ]
}
set_lo_ipv4_addr_op = lambda lo_ipv4_addr: {
    "op": "ipaddr",
    "args": [
        f"{lo_ipv4_addr}/32",
        "lo"
    ]
}
set_lo_ipv6_addr_op = lambda lo_ipv6_addr: {
    "op": "ipaddr",
    "args": [
        f"{lo_ipv6_addr}/128",
        "lo"
    ]
}
set_bgp_intf_addr_op = lambda addr, intf: {
    "op": "ipaddr",
    "args": [
        f"{addr}/127",
        f"{intf}"
    ]
}
start_bird_op = {
    "op": "cmd",
    "args": [
        "bird",
        "-c",
        "/share/etc/bird.conf"
    ]
}

# example_node_info = {
#     "lo_ipv4_addr": "10.0.0.0",
#     "lo_ipv6_addr": "fd01::0",
#     "local_as_number": 1,
#     "local_as_network": "fd01::0/124",
#     "ospf_disabled_intfs": [
#         "eth-0-1",
#         "eth-0-2",
#     ],
#     "ebgp_neighbors": [
#         {
#             "peer_node_id": 1,
#             "peer_intf_ipv6_addr": "fd02::1",
#             "peer_as_number": 2,
#             "local_intf": "eth-0-1",
#             "local_intf_ipv6_addr": "fd02::0",
#         }
#     ],
#     "ibgp_neighbors": [
#         {
#             "peer_node_id": 1,
#             "peer_lo_ipv6_addr": "fd02::1",
#             "peer_as_number": 2,
#         }
#     ]
# }
def generate_one_node_setup_exec_entry(node_id, node_info, exec_config):
    # Construct ops array
    setup_ops = []
    setup_ops.append(set_netsysctl_op)
    setup_ops.append(setup_lo_op)
    setup_ops.append(set_lo_ipv4_addr_op(node_info["lo_ipv4_addr"]))
    setup_ops.append(set_lo_ipv6_addr_op(node_info["lo_ipv6_addr"]))
    for ebgp_neighbor in node_info["ebgp_neighbors"]:
        setup_ops.append(set_bgp_intf_addr_op(
            ebgp_neighbor["local_intf_ipv6_addr"],
            ebgp_neighbor["local_intf"],
        ))
    
    # Construct exec_entry
    setup_exec_entry = {
        "node_id": node_id,
        "ops": setup_ops
    }
    exec_config["exec_entries"].append(setup_exec_entry)


def generate_one_node_routerup_exec_entry(node_id, node_info, exec_config):
    # Start router
    router_up_ops = []
    router_up_ops.append(start_bird_op)
    router_up_exec_entry = {
        "node_id": node_id,
        "ops": router_up_ops
    }
    exec_config["exec_entries"].append(router_up_exec_entry)
