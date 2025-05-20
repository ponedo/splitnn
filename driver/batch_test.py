import os
import time
import json
import math
import argparse
import subprocess
import shutil
from copy import deepcopy
from scripts.partition.core import partition_topo
from itertools import product
from util.common import *
from util.remote import *
from util.topo_info import *
from util.factor import *

############################ Constants ###############################

DRIVER_WORKDIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(DRIVER_WORKDIR) # Change cuurent working directory

# REPEAT_TIME = 1
SERVER_CONFIG_PATH = "server_config.json"
INFRA_BIN_PATH = "bin/topo_setup_test"
INFRA_TOPO_DIR = "tmp/topo"
LOCAL_RESULT_DIR = "raw_results"
LOCAL_TOPO_DIR = os.path.join(DRIVER_WORKDIR, "topo")
REMOTE_RESULT_PATHS = [
    ("file", "tmp/setup_log.txt"),
    ("file", "tmp/clean_log.txt"),
    ("file", "tmp/link_log.txt"),
    # ("dir", "tmp/cctr_log"),
    # ("dir", "tmp/kern_func"),
    # ("dir", "tmp/cctr_time.txt"),
    ("dir", "tmp/setup_cpu_mem_usage.txt"),
    ("dir", "tmp/clean_cpu_mem_usage.txt"),
]

######################### Command options ############################

const_options = {
    "s": SERVER_CONFIG_PATH
}

SERVER_BBNS_NUM_TEST = False
USE_BEST_BBNS_NUM = False
assert not (SERVER_BBNS_NUM_TEST and USE_BEST_BBNS_NUM)
var_options = {
    # Topologies
    "t": [
        # ["isolated", "100"],
        # ["grid", "100", "100"],
        # ["isolated", "10000"],
        # ["grid", "50", "50"],
        # ["isolated", "3600"],

        # ["grid", "10", "10"],
        # ["grid", "20", "20"],
        # ["grid", "30", "30"],
        # ["grid", "40", "40"],
        # ["grid", "50", "50"],
        # ["grid", "60", "60"],
        # ["grid", "70", "70"],
        # ["grid", "75", "75"],
        # ["grid", "80", "80"],
        # ["grid", "85", "85"],
        # ["grid", "90", "90"],
        # ["grid", "95", "95"],
        # ["grid", "100", "100"],

        # ["clos", "8"],
        # ["clos", "12"],
        # ["clos", "16"],
        # ["clos", "20"],
        # ["clos", "24"],
        # ["clos", "28"],
        # ["clos", "32"],

        # ["chain", "1251"],
        # ["chain", "2501"],
        # ["chain", "3751"],
        # ["chain", "5001"],
        # ["chain", "6251"],
        # ["chain", "7501"],
        # ["chain", "8751"],
        # ["chain", "10001"],

        # ["trie", "1251", "10"],
        # ["trie", "2501", "10"],
        # ["trie", "3751", "10"],
        # ["trie", "5001", "10"],
        # ["trie", "6251", "10"],
        # ["trie", "7501", "10"],
        # ["trie", "8751", "10"],
        # ["trie", "10001", "10"],

        # ["as", "small"],
        # ["as", "medium"],
        # ["as", "large"],
    ],

    "b": [
        1,
        # 2,
        # 3,
        # 4,
        # 5,
        # 50,
        # 100,
    ],

    "a": [
        # "dynamic",
        "naive",
    ],

    "d": [
        0,
        # 1
    ],

    "N": [
        "cctr",
        # "goctr"
    ],

    "l": [
        "ntlbr",
    ],

    # "p": [
    #     0,
    #     2,
    #     4,
    #     8
    # ]
}

if SERVER_BBNS_NUM_TEST or USE_BEST_BBNS_NUM:
    del(var_options["b"])

server_spec_options = {
    "i": lambda i: i
}


# If there is overlap between option keys defined above, raise an error and exit
all_keys = [
    set(d.keys()) \
        for d in [const_options, var_options, server_spec_options]
]
for i, keys1 in enumerate(all_keys):
    for j, keys2 in enumerate(all_keys):
        if i < j and keys1 & keys2:  # Find intersection
            print(f"Overlap found between dict {i} and dict {j}: {keys1 & keys2}")
            exit(1)

######################### Helper functions ############################

def connect_remote_machines(server_config_list):
    remote_machines = []
    for server in server_config_list:
        remote_machine = RemoteMachine(
            server["ipAddr"], server["user"],
            server["password"], working_dir=server["infraWorkDir"])
        machine = remote_machine.connect()
        remote_machines.append(machine)
    return remote_machines


def prepare_env_on_remote_machines(remote_machines, server_config_list):
    server_config_src_path = os.path.join(DRIVER_WORKDIR, SERVER_CONFIG_PATH)
    server_config_src_dst_paths = {
        server["ipAddr"]: (
            server_config_src_path,
            os.path.join(server["infraWorkDir"], SERVER_CONFIG_PATH),
            False
        ) for server in server_config_list
    }
    
    # # Synchronize code
    # execute_command_on_multiple_machines(
    #     remote_machines, {
    #         server["ipAddr"]: (
    #             "./sync_code.sh rigid", os.path.join(server["infraWorkDir"], ".."), None, False
    #         ) for server in server_config_list
    #     }
    # )

    send_file_to_multiple_machines(
        remote_machines, server_config_src_dst_paths)

    # Recompile virtual network manager on all machines
    execute_command_on_multiple_machines(
        remote_machines, {
            server["ipAddr"]: (
                "make", server["infraWorkDir"], None, False
            ) for server in server_config_list
        }
    )

    # Pull docker image on each machine
    execute_command_on_multiple_machines(
        remote_machines, {
            server["ipAddr"]: (
                f"./scripts/pull_docker_image.sh {server['dockerImageName']}", server["infraWorkDir"], None, True
            ) for server in server_config_list
        }
    )


def get_full_topo_filename(topo_args):
    return f"{'_'.join(topo_args)}.txt"


def get_sub_topo_filename(topo_args, i):
    full_topo_filename = get_full_topo_filename(topo_args)
    splited_topo_filename = full_topo_filename.split('.')
    if len(splited_topo_filename) == 1:
        splited_sub_topo_filename = splited_topo_filename + [f"sub{i}"] # without .txt suffix
    else:
        splited_sub_topo_filename = splited_topo_filename[:-1] + [f"sub{i}"] + splited_topo_filename[-1:] # with .txt suffix
    sub_topo_filename = '.'.join(splited_sub_topo_filename)
    return sub_topo_filename


BEST_K_FACTOR = 2.353
def get_server_best_bbns_num(sub_topo_filepath, i):
    line_num = count_lines_islice(sub_topo_filepath)
    link_num = line_num - 1
    best_bbns_num = math.ceil(BEST_K_FACTOR * math.sqrt(link_num))
    print(f"Server {i} topo link num: {link_num}, best bbns num: {best_bbns_num}")
    return best_bbns_num


def prepare_topology(remote_machines, topos):
    for topo in topos:
        # Generate the topology file
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

        # Partition the topology accross multiple physical machine (TBS) and multiple VMs within a physical machine
        partition_topo(full_topo_filepath, server_config_list)
        # script_path = os.path.join(DRIVER_WORKDIR, "scripts", f"partition_topo.py")
        # partition_topology_cmd = ["python3", script_path, "-f", topo_filepath, "-n", f"{len(servers)}"]
        # result = subprocess.run(partition_topology_cmd, capture_output=True, text=True, env=env)

        # Send sub-topo to servers
        sub_topo_src_dst_filepaths = {}
        for i, server in enumerate(server_config_list):
            sub_topo_filename = get_sub_topo_filename(topo, i)
            sub_topo_src_filepath = os.path.join(os.path.dirname(full_topo_filepath), sub_topo_filename)
            sub_topo_dst_filepath = os.path.join(server["infraWorkDir"], INFRA_TOPO_DIR, sub_topo_filename)
            sub_topo_src_dst_filepaths[server["ipAddr"]] = \
                (sub_topo_src_filepath, sub_topo_dst_filepath, False)
        send_file_to_multiple_machines(
            remote_machines, sub_topo_src_dst_filepaths)


def get_one_vn_manage_cmd(bin_path, operation, options):
    vn_manage_cmd = f"{bin_path} -o {operation}"
    for k, v in options.items():
        v = f"{v}"
        if " " in v:
            print(f"Warning: an option value of virtual network management command contains space: (\"{k}\" \"{v}\")")
        vn_manage_cmd += f" -{k} {v}"
    return vn_manage_cmd


def generate_bbns_num_test_numbers(topo_args):
    topo_type = topo_args[0]
    topo_data = topo_args[1:]
    link_num = topo_funcs[topo_type]["get_link_num"](*topo_data)
    bbns_nums = list_factors(link_num)
    return bbns_nums


def yield_one_cmd(opts, const_options, server_spec_options, server_config_list):
    var_opts = deepcopy(opts)
    opts.update(const_options)
    topo_args = opts["t"]
    # Prepare setup/clean commands for each server
    setup_commands, clean_commands = {}, {}
    for i, server in enumerate(server_config_list):
        server_i_opts = deepcopy(opts)
        # Add server-specific option (such as server id)
        for server_spec_opt_key, server_spec_opt_value_func in server_spec_options.items():
            server_i_opts.update({
                server_spec_opt_key: server_spec_opt_value_func(i)
            })
        sub_topo_filename = get_sub_topo_filename(topo_args, i)
        local_sub_topo_filepath = os.path.join(LOCAL_TOPO_DIR, sub_topo_filename)
        # Modify topo option
        remote_sub_topo_filepath = os.path.join(
            INFRA_TOPO_DIR, get_sub_topo_filename(topo_args, i))
        server_i_opts.update({
            "t": remote_sub_topo_filepath
        })
        # Generate best bbns number for each server
        if USE_BEST_BBNS_NUM:
            server_i_best_bbns_num = get_server_best_bbns_num(
                local_sub_topo_filepath, i)
            server_i_opts.update({
                "b": server_i_best_bbns_num
            })
        # Generate and cache commands
        setup_command = get_one_vn_manage_cmd(INFRA_BIN_PATH, "setup", server_i_opts)
        setup_commands[server["ipAddr"]] = \
            (setup_command, server["infraWorkDir"], None, True)
        clean_command = get_one_vn_manage_cmd(INFRA_BIN_PATH, "clean", server_i_opts)
        clean_commands[server["ipAddr"]] = \
            (clean_command, server["infraWorkDir"], None, True)
    return var_opts, setup_commands, clean_commands


def exp_cmds_iterator(
        const_options, var_options, server_spec_options,
        server_config_list):
    # Iterate over all possible combiation of options
    var_opt_keys = var_options.keys()
    for var_opt_comb in product(*var_options.values()):
        # Get a combination of options
        opts = dict(zip(var_opt_keys, var_opt_comb))
        if SERVER_BBNS_NUM_TEST:
            bbns_nums = generate_bbns_num_test_numbers(opts["t"])
            for bbns_num in bbns_nums:
                opts_with_b = {**opts, "b": bbns_num}
                yield yield_one_cmd(
                    opts_with_b, const_options, server_spec_options, server_config_list)
        else:
            yield yield_one_cmd(
                opts, const_options, server_spec_options, server_config_list)


def get_one_test_log_name(var_opts):
    var_opts['t'] = '_'.join(var_opts['t'])
    dir_name_elements = [f"{k}--{v}" for k, v in var_opts.items()]
    dir_name = '--'.join(dir_name_elements)
    return dir_name


def reap_one_test_results(remote_machines, server_config_list, cur_test_log_dir):
    server_log_dirs = []
    for i, server in enumerate(server_config_list):
        server_i_log_dir = os.path.join(cur_test_log_dir, f"server{i}")
        os.makedirs(server_i_log_dir, exist_ok=True)
        server_log_dirs.append(server_i_log_dir)

    for remote_result_path in REMOTE_RESULT_PATHS:
        # Define different remote and local directories for each machine
        directories = {
            server["ipAddr"]: (
                os.path.join(server["infraWorkDir"], remote_result_path[1]),
                server_log_dirs[i],
                remote_result_path[0] == "dir"
            )
            for i, server in enumerate(server_config_list)
        }
        receive_file_from_multiple_machines(remote_machines, directories)


################################# Main ##################################

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Execute a batch of experiments')
    args = parser.parse_args()

    # env = os.environ.copy()
    # env["METIS_DLL"]="~/.local/lib/libmetis.so"

    # Read configuration of servers
    with open(SERVER_CONFIG_PATH, 'r') as f:
        server_config = json.load(f)
        server_config_list = server_config["servers"]

    # Connect to remote machine
    remote_machines = connect_remote_machines(server_config_list)

    # Config servers on remote machines
    prepare_env_on_remote_machines(remote_machines, server_config_list)

    # Prepare topologies and distribute them onto servers
    topos = var_options["t"]
    prepare_topology(remote_machines, topos)

    # "./bin/topo_setup_test -o setup -t tmp/topo/grid_10_10.txt -b 1 -a dynamic -d 0 -N cctr -l ntlbr -s server_config.json -i 0"

    # Prepare local repository directory for storing test results
    server_num = len(server_config_list)
    local_result_repo_dir = os.path.join(LOCAL_RESULT_DIR, f"result-{server_num}-servers")
    os.makedirs(local_result_repo_dir, exist_ok=True)
    shutil.copy(SERVER_CONFIG_PATH, local_result_repo_dir)

    # Iterate over all tests with different options. Each loop yields a group of commands executing the test.
    for var_opts, setup_commands, clean_commands in exp_cmds_iterator(
        const_options, var_options, server_spec_options, server_config_list):
        # Check log directory of current test
        final_cur_test_log_dir = get_one_test_log_name(var_opts)
        full_cur_test_log_dir = os.path.join(local_result_repo_dir, final_cur_test_log_dir)
        if os.path.exists(full_cur_test_log_dir) and os.listdir(full_cur_test_log_dir):
            print(f"Test {var_opts} skipped")
            continue # Current test has been completed before, skip current iteration
        os.makedirs(full_cur_test_log_dir, exist_ok=True)

        # Execute test commands
        print(setup_commands)
        execute_command_on_multiple_machines(remote_machines, setup_commands) # Setup virtual network
        time.sleep(15) # Wait for a while
        print(clean_commands)
        execute_command_on_multiple_machines(remote_machines, clean_commands) # Clean virtual network
        time.sleep(20) # Wait for a while

        # Reap results of current test
        reap_one_test_results(remote_machines, server_config_list, full_cur_test_log_dir)

    # Close connection
    for remote_machine in remote_machines:
        remote_machine.close_connection()
