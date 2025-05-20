from string import Template
from .common import *

bird_conf_template = Template("""
log syslog all;

protocol device {
}

protocol direct {
	ipv4;			# Connect to default IPv4 table
	ipv6;			# ... and to default IPv6 table
}

protocol kernel {
	ipv4 {			# Connect protocol to IPv4 table by channel
	      export all;	# Export to protocol. default is export none
	};
}

protocol kernel {
	ipv6 { export all; };
}

protocol static {
	ipv6;
	route $LOCAL_AS_NETWORK blackhole;
}

protocol ospf v3 {
 	ipv6 {
		import all;
		export filter {
			if source = RTS_BGP then ospf_metric1 = 10 * (bgp_path.len + 1);
			accept;
		};
	};
	area 0 {
		interface $OSPF_DISABLED_INTFS \"-lo\", \"*\" {
			type broadcast;		# Detected by default
			cost 5;		# Interface metric
			hello 10;
            dead 1000;
		};
	};
}

$EBGP_CONFIG

$IBGP_CONFIG
""")

ebgp_instance_conf_template = Template("""
protocol bgp neighbor$PEER_NODE_ID {
	local as $LOCAL_AS_NUMBER;
	neighbor $PEER_INTF_ADDR as $PEER_AS_NUMBER external;
	hold time 0;
	ipv6 {
		import filter {
			if source = RTS_OSPF then reject;
			bgp_local_pref = 200;
			accept;
		};
		export filter {
			if source = RTS_OSPF then reject;  # Block all OSPF routes
			if net.len = $LOCAL_AS_NETWORK_LEN then accept;  # Only announce the aggregated route
			reject;
		};
	};
}
""")

ibgp_instance_conf_template = Template("""
protocol bgp neighbor$PEER_NODE_ID {
	local as $LOCAL_AS_NUMBER;
	neighbor $PEER_INTF_ADDR as $PEER_AS_NUMBER internal;
	hold time 0;
	ipv6 {
        # import filter {
		# 	if source = RTS_OSPF then reject;
		# 	bgp_local_pref = 100;
		# 	accept;
		# };
        import none;
		export filter {
			if source = RTS_OSPF then reject;  # Block all OSPF routes
			if net.len = $LOCAL_AS_NETWORK_LEN then accept;  # Only announce the aggregated route
			reject;
		};
	};
}
""")


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
def generate_one_node_bird_conf(node_id, node_info, dst_path):
    # Configure OSPF disabled interfaces
    ospf_disabled_intfs = node_info["ospf_disabled_intfs"]
    ospf_disabled_intfs_str = ""
    for intf in ospf_disabled_intfs:
        ospf_disabled_intfs_str += f"\"-{intf}\""
        ospf_disabled_intfs_str += ", "

    # Configure ebgp neighbors
    ebgp_config = ""
    for ibgp_neighbor in node_info["ebgp_neighbors"]:
        local_as_network_len = node_info["local_as_network"].split('/')[1]
        bgp_instance_config = ebgp_instance_conf_template.substitute(
            PEER_NODE_ID=ibgp_neighbor["peer_node_id"],
            LOCAL_AS_NUMBER=node_info["local_as_number"],
            PEER_INTF_ADDR=ibgp_neighbor["peer_intf_ipv6_addr"],
            PEER_AS_NUMBER=ibgp_neighbor["peer_as_number"],
            LOCAL_AS_NETWORK_LEN=local_as_network_len,
        )
        ebgp_config += bgp_instance_config
    
    # Configure ebgp neighbors
    ibgp_config = ""
    for ibgp_neighbor in node_info["ibgp_neighbors"]:
        local_as_network_len = node_info["local_as_network"].split('/')[1]
        bgp_instance_config = ibgp_instance_conf_template.substitute(
            PEER_NODE_ID=ibgp_neighbor["peer_node_id"],
            LOCAL_AS_NUMBER=node_info["local_as_number"],
            PEER_INTF_ADDR=ibgp_neighbor["peer_lo_ipv6_addr"],
            PEER_AS_NUMBER=ibgp_neighbor["peer_as_number"],
            LOCAL_AS_NETWORK_LEN=local_as_network_len,
        )
        ibgp_config += bgp_instance_config

    # Generate bird conf string
    bird_conf_str = bird_conf_template.substitute(
        LOCAL_AS_NETWORK=node_info["local_as_network"],
        OSPF_DISABLED_INTFS=ospf_disabled_intfs_str,
        EBGP_CONFIG=ebgp_config,
        IBGP_CONFIG=ibgp_config,
    )

    output_string(dst_path, bird_conf_str)
