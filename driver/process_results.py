import os
import json
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from util.remote import RemoteMachine, \
    receive_files_from_multiple_machines

MAX_RUNTIME=5
server_num=None


def get_topo_info(topo_name):
    topo_args = topo_name.split('_')
    topo_type = topo_args[0]
    if topo_type == "grid":
        x, y = int(topo_args[1]), int(topo_args[2])
        node_num = x * y
        edge_num = 2 * node_num
    elif topo_type == "clos":
        k = int(topo_args[1])
        node_num = (5 / 4) * (k ** 2) + (k ** 3) / 4
        edge_num = 3 * k * (k // 2) * (k // 2)
    else:
        print(f"Invalid topology {topo_type}")
        return None, None
    return topo_type, node_num, edge_num


def read_setup_results(filepath):
    with open(filepath, "r") as f:
        for line in f:
            if line.startswith("Node setup time"):
                node_setup_time = float(line.split(':')[1].strip().strip('s'))
            elif line.startswith("Link setup time"):
                link_setup_time = float(line.split(':')[1].strip().strip('s'))
            elif line.startswith("Network operation time"):
                network_setup_time = float(line.split(':')[1].strip().strip('s'))
    return {
        "node_setup_time": node_setup_time,
        "link_setup_time": link_setup_time,
        "network_setup_time": network_setup_time
    }


def read_destroy_results(filepath):
    with open(filepath, "r") as f:
        for line in f:
            if line.startswith("Node Destroy time"):
                node_destroy_time = float(line.split(':')[1].strip().strip('s'))
            elif line.startswith("Link Destroy time"):
                link_destroy_time = float(line.split(':')[1].strip().strip('s'))
            elif line.startswith("Network operation time"):
                network_destroy_time = float(line.split(':')[1].strip().strip('s'))
    return {
        "node_destroy_time": node_destroy_time,
        "link_destroy_time": link_destroy_time,
        "network_destroy_time": network_destroy_time
    }


def reap_logs(log_dir):
    # Read configuration of servers
    with open('server_config.json', 'r') as f:
        server_config = json.load(f)
        servers = server_config["servers"]

    # Connect to remote machine
    remote_machines = []
    for server in servers:
        remote_machine = RemoteMachine(
            server["ipAddr"], server["user"],
            server["password"], working_dir=server["infraWorkDir"])
        machine = remote_machine.connect()
        remote_machines.append(machine)

    # Define different remote and local directories for each machine
    results_dir = log_dir
    directories = {
        server["ipAddr"]: (
            os.path.join(server["infraWorkDir"], "log"), results_dir) \
        for server in servers
    }

    # Receive all files from remote directories concurrently
    receive_files_from_multiple_machines(remote_machines, directories)

    # Close connection
    for remote_machine in remote_machines:
        remote_machine.close_connection()


def generate_results_data(log_dir):
    # Read configuration of servers
    with open('server_config.json', 'r') as f:
        server_config = json.load(f)
        servers = server_config["servers"]
    server_num = len(servers)

    # Collect raw data in a map
    tmp_map = {}
    for filename in os.listdir(log_dir):
        if not filename.endswith(".txt"):
            continue

        filepath = os.path.join(log_dir, filename)
        nm, algo, op, run_turn, topo_name, sub_i, _ = filename.strip().split('.')
        run_turn = int(run_turn.split('_')[1])
        sub_i = int(sub_i[3:])
        topo_type, node_num, edge_num = get_topo_info(topo_name)
        k = (topo_type, topo_name, nm, algo, op)
        if k not in tmp_map:
            tmp_map[k] = [[{} for _ in range(server_num)] for _ in range(MAX_RUNTIME)]
        if op == "setup":
            time_results = read_setup_results(filepath)
        elif op == "destroy":
            time_results = read_destroy_results(filepath)
        tmp_map[k][run_turn][sub_i].update(time_results)
        tmp_map[k][run_turn][sub_i].update(
            {"node_num": node_num, "edge_num": edge_num})

    # Merge multi-run and multi-server entries into one number in the map
    merged_map = {}
    for k in tmp_map:
        tmp_avg_results = {}
        for run_turn in range(MAX_RUNTIME):
            max_results = {}
            for sub_i in range(server_num):
                results = tmp_map[k][run_turn][sub_i]
                for result_key, result_value in results.items():
                    if result_key not in max_results:
                        max_results[result_key] = result_value
                    else:
                        max_results[result_key] = max(
                            max_results[result_key], result_value
                        )
            for max_result_key, max_result_value in max_results.items():
                if max_result_key not in tmp_avg_results:
                    tmp_avg_results[max_result_key] = [max_result_value]
                else:
                    tmp_avg_results.append(max_result_value)
        merged_map[k] = {result_key: np.average(result_values) for result_key, result_values in tmp_avg_results.items()}

    # Store results into a big dataframe
    data = []
    for k, v in merged_map.items():
        entry = {"topo_type": k[0], "topo_name": k[1], "nm": k[2], "algo": k[3], "op": k[4]}
        entry.update(v)
        data.append(entry)
    df = pd.DataFrame(data)
    return df


def save_csv_files(df, csv_dir):
    # Output all data as a dataframe
    df.to_csv(os.path.join(csv_dir, 'data.csv'), index=False)

    # Output multiple dataframe into csv files as demand
    grouped = df.groupby(['topo_type', 'op'])
    for (topo_type, op), group in grouped:
        csv_filename = f"{topo_type}_{op}.csv"
        csv_filepath = os.path.join(csv_dir, csv_filename)
        sorted_group = group.sort_values(by=['nm', 'algo', 'node_num'], ascending=[True, False, True])
        new_column_order = [
            "topo_type",
            "topo_name",
            "nm",
            "algo",
            "op",
            "node_num",
            "edge_num",
            "node_setup_time",
            "link_setup_time",
            "network_setup_time",
            "node_destroy_time",
            "link_destroy_time",
            "network_destroy_time"
        ]
        sorted_group = sorted_group[new_column_order]
        sorted_group.to_csv(csv_filepath, index=False)
        print(csv_filepath)


def plot_figure(df, x_scale, y_value, y_value_unit, testcase_label, curve_groupby, figure_dir):
    # Check validity of arguments
    if x_scale not in ["node_num", "edge_num"]:
        print(f"Invalid x_scale {x_scale}")
        return
    if y_value not in [
        "node_setup_time",
        "link_setup_time",
        "network_setup_time",
        "node_destroy_time",
        "link_destroy_time",
        "network_destroy_time"
    ]:
        print(f"Invalid y_value {y_value}")
        return

    # Create a figure and axis
    plt.figure(figsize=(10, 6))

    # Iterate through unique (nm, algo) pairs
    for (nm, algo), group in df.groupby(['nm', 'algo']):
        plt.plot(group[x_scale], group[y_value], marker='o', label=f'{nm}-{algo}')

        
    # Iterate through unique curves
    for group_fields, group in df.groupby(curve_groupby):
        if isinstance(group_fields, str):
            label = group_fields
        elif isinstance(group_fields, tuple):
            label = '-'.join([str(f) for f in group_fields])
        else:
            print(f"Invalid group fields \" {group_fields}\" of type {type(group_fields)}")
            exit(1)
        plt.plot(group[x_scale], group[y_value], marker='o', label=label)


    # Draw vertical dashed lines and label them with D values
    labeled_x_values = set()
    # Draw vertical dashed lines and label them at the max E for each unique C value
    for x_value in df[x_scale].unique():
        sub_df = df[df[x_scale] == x_value]
        max_e_row = sub_df[sub_df[y_value] == sub_df[y_value].max()].iloc[0]
        plt.axvline(x=x_value, linestyle='--', color='gray', alpha=0.5)
        plt.text(x_value, max_e_row[y_value], str(max_e_row['topo_name']), verticalalignment='bottom', horizontalalignment='center')

    # for _, row in df.iterrows():
    #     if row[x_scale] not in labeled_x_values:
    #         plt.axvline(x=row[x_scale], linestyle='--', color='gray', alpha=0.5)
    #         plt.text(row[x_scale], row[y_value], str(row['topo_name']), verticalalignment='bottom', horizontalalignment='center')
    #         labeled_x_values.add(row[x_scale])

    # Adding labels and title
    title = f"{testcase_label}_{x_scale} ({y_value_unit})"
    plt.xlabel(x_scale)
    plt.ylabel(y_value)
    plt.title(title)
    plt.legend()
    plt.grid()

    # Save figure
    plt.savefig(
        os.path.join(figure_dir, f'{title}-{x_scale}-{y_value}.png'),
        bbox_inches='tight')  # You can specify a different filename or format
    plt.close()


def plot_csv_file(csv_filepath, figure_dir):
    csv_filename = os.path.basename(csv_filepath)
    if csv_filename == "data.csv":
        return
    print(csv_filename)
    topo_type, op = csv_filename.split('.')[0].split('_')
    df = pd.read_csv(csv_filepath)
    if op == "setup":
        y_values = ["node_setup_time", "link_setup_time", "network_setup_time"]
    elif op == "destroy":
        y_values = ["node_destroy_time", "link_destroy_time", "network_destroy_time"]
    x_scales = ["node_num", "edge_num"]
    testcase_label = f"{topo_type}_{op}"
    y_value_unit = "s"
    curve_groupby = ["nm", "algo"]

    for x_scale in x_scales:
        for y_value in y_values:
            plot_figure(
                df, x_scale, y_value, y_value_unit,
                testcase_label, curve_groupby, figure_dir)


def plot_csv_files(csv_dir, figure_dir):
    for csv_filename in os.listdir(csv_dir):
        csv_filepath = os.path.join(csv_dir, csv_filename)
        plot_csv_file(csv_filepath, figure_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='A script to reap and save results from all servers')
    parser.add_argument('op', type=str, help='Operation [reap|process|plot]')
    parser.add_argument('-D', '--results-dir', type=str, required=False, default="log", help='Directory where results are saved')
    args = parser.parse_args()

    # Make directories
    results_dir = args.results_dir
    log_dir = os.path.join(results_dir, "log")
    csv_dir = os.path.join(results_dir, "csv")
    figure_dir = os.path.join(results_dir, "figures")

    if args.op == "reap":
        os.makedirs(log_dir, exist_ok=True)
        reap_logs(log_dir)

    if args.op == "process":
        os.makedirs(csv_dir, exist_ok=True)
        df = generate_results_data(log_dir)
        save_csv_files(df, csv_dir)

    if args.op == "plot":
        os.makedirs(figure_dir, exist_ok=True)
        plot_csv_files(csv_dir, figure_dir)