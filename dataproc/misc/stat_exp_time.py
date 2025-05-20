import sys
import os
import heapq
import argparse
import concurrent.futures


# Get concurrency from command line or default to 4
parser = argparse.ArgumentParser()
parser.add_argument("exp_result_dir", type=str, help="Path to the experiment result directory")
args, unknown = parser.parse_known_args()

exp_result_dir = args.exp_result_dir

# Check if the provided directory exists
if not os.path.exists(exp_result_dir):
    print(f"Directory {exp_result_dir} does not exist.")
    exit(1)


def inspect_log(log_file_path):
    # Open the log file and find the line starting with "Network operation time:"
    with open(log_file_path, 'r') as log_file:
        for line in log_file:
            if line.startswith("Network operation time:"):
                # Extract the time value from the line
                time_str = line.split(":")[1].strip()
                if time_str.endswith("s"):
                    time_value = float(time_str[:-1])
                else:
                    time_value = float(time_str)
                return time_value


def inspect_one_result_dir(result_dir, subdir_name):
    print(f"Inspecting {subdir_name}")
    setup_time = inspect_log(os.path.join(result_dir, "setup_log.txt"))
    clean_time = inspect_log(os.path.join(result_dir, "clean_log.txt"))
    print(f"Setup time: {setup_time}s, clean time: {clean_time}s\n")
    return setup_time, clean_time


def scan_result_dirs(exp_result_dir):
    if not os.path.exists(exp_result_dir):
        print(f"Directory {exp_result_dir} does not exist.")
        return

    max_setup_time, max_clean_time = 0, 0

    subdirs = [d for d in os.listdir(exp_result_dir) if os.path.isdir(os.path.join(exp_result_dir, d))]
    for subdir in subdirs:
        setup_time, clean_time = inspect_one_result_dir(os.path.join(exp_result_dir, subdir), subdir)
        max_setup_time = max(max_setup_time, setup_time)
        max_clean_time = max(max_clean_time, clean_time)

    return max_setup_time, max_clean_time


# Scan in best-k-model directory
if __name__ == "__main__":
    max_setup_time, max_clean_time = scan_result_dirs(args.exp_result_dir)
    print(f"Max setup time: {max_setup_time}s")
    print(f"Max clean time: {max_clean_time}s")
