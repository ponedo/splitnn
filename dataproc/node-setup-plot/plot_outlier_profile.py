import os
import re
import matplotlib.pyplot as plt
import numpy as np
import argparse
import pandas as pd

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Process log files and generate a plot.")
parser.add_argument("folder_path", type=str, help="Path to the folder containing log files.")
parser.add_argument(
    "-r", "--outlier-tolerance-offset-ratio", type=float, help="Outlier tolerance offset ratio (P%)."
)
parser.add_argument(
    "-w", "--window", type=int, default=0, help="Window size (W) for outlier detection. Default is 0 (no sliding window)."
)
args = parser.parse_args()

# Path to the folder containing log files
folder_path = args.folder_path
proportion_threshold = args.outlier_tolerance_offset_ratio / 100.0 if args.outlier_tolerance_offset_ratio else None
window_size = args.window

# Regular expressions to extract values from logs
regex_patterns = {
    "run_start_time": r"run_start_time:\s+(\d+)",
    "overlay_time": r"overlay_time:\s+(\d+)",
    "fork1_time": r"fork1_time:\s+(\d+)",
    "unshare_time": r"unshare_time:\s+(\d+)",
    "fork2_time": r"fork2_time:\s+(\d+)",
    # "writepid_time": r"write_pid_time:\s+(\d+)",
    "rootfs_time": r"rootfs_time:\s+(\d+)",
    "setenv_time": r"setenv_time:\s+(\d+)",
    # "execlp_time": r"execlp_time:\s+(\d+)",
    "readerr_time": r"read_err_time:\s+(\d+)",
    "waitchild_time": r"wait_child_time:\s+(\d+)",
    # "readpid_time": r"read_pid_time:\s+(\d+)",
    "run_total_time": r"run_total_time:\s+(\d+)",
}

# Data storage
data = {
    "x": [],  # XXX values
    "overlay_time": [],
    "fork1_time": [],
    "unshare_time": [],
    # "writepid_time": [],
    "fork2_time": [],
    "rootfs_time": [],
    # "setenv_time": [],
    # "execlp_time": [],
    "readerr_time": [],
    "waitchild_time": [],
    # "readpid_time": [],
    "run_total_time": [],
}

# Process each log file
for filename in sorted(os.listdir(folder_path)):
    if filename.startswith("run.log.") and filename.split('.')[-1].isdigit():
        filepath = os.path.join(folder_path, filename)
        with open(filepath, 'r') as file:
            log_content = file.read()

        # Extract XXX value from filename
        xxx_value = int(filename.split('.')[-1])
        data["x"].append(xxx_value)

        # Extract and calculate time values
        log_timestamps = {}
        for re_key, re_value in regex_patterns.items():
            log_timestamps[re_key] = int(re.search(re_value, log_content).group(1))

        # data["overlay_time"].append(log_timestamps["overlay_time"] - log_timestamps["run_start_time"])
        # data["fork1_time"].append(log_timestamps["fork1_time"] - log_timestamps["overlay_time"])
        # data["unshare_time"].append(log_timestamps["unshare_time"] - log_timestamps["fork1_time"])
        # data["writepid_time"].append(log_timestamps["writepid_time"] - log_timestamps["unshare_time"])
        # data["fork2_time"].append(log_timestamps["fork2_time"] - log_timestamps["unshare_time"])
        # data["rootfs_time"].append(log_timestamps["rootfs_time"] - log_timestamps["fork2_time"])
        # data["setenv_time"].append(log_timestamps["setenv_time"] - log_timestamps["rootfs_time"])
        # data["execlp_time"].append(log_timestamps["rootfs_time"] - log_timestamps["setenv_time"])
        # data["readerr_time"].append(log_timestamps["readerr_time"] - log_timestamps["setenv_time"])
        # data["waitchild_time"].append(log_timestamps["waitchild_time"] - log_timestamps["readerr_time"])
        # data["readpid_time"].append(log_timestamps["readpid_time"] - log_timestamps["waitchild_time"])
        # data["run_total_time"].append(log_timestamps["run_total_time"] - log_timestamps["run_start_time"])
        
        data["overlay_time"].append(log_timestamps["overlay_time"] - log_timestamps["run_start_time"])
        data["fork1_time"].append(log_timestamps["fork1_time"] - log_timestamps["run_start_time"])
        data["unshare_time"].append(log_timestamps["unshare_time"] - log_timestamps["run_start_time"])
        # data["writepid_time"].append(log_timestamps["writepid_time"] - log_timestamps["run_start_time"])
        data["fork2_time"].append(log_timestamps["fork2_time"] - log_timestamps["run_start_time"])
        data["rootfs_time"].append(log_timestamps["rootfs_time"] - log_timestamps["run_start_time"])
        # data["setenv_time"].append(log_timestamps["setenv_time"] - log_timestamps["run_start_time"])
        # data["execlp_time"].append(log_timestamps["rootfs_time"] - log_timestamps["run_start_time"])
        data["readerr_time"].append(log_timestamps["readerr_time"] - log_timestamps["run_start_time"])
        data["waitchild_time"].append(log_timestamps["waitchild_time"] - log_timestamps["run_start_time"])
        # data["readpid_time"].append(log_timestamps["readpid_time"] - log_timestamps["run_start_time"])
        data["run_total_time"].append(log_timestamps["run_total_time"] - log_timestamps["run_start_time"])

        # Make results as time-cost percentage
        # for k in data:
        #     if k == "x":
        #         continue
        #     data[k][-1] /= data["run_total_time"][-1]

# Sort data by x (XXX values)
sorted_indices = np.argsort(data["x"])
for key in data.keys():
    data[key] = np.array(data[key])[sorted_indices]
    if key == "x":
        continue
    data[key] = data[key] / (10 ** 6)

# Function to remove outliers using sliding window and proportion threshold
def remove_outliers_with_window(x_values, y_values, proportion_threshold, window_size):
    if proportion_threshold is None:
        return x_values, y_values  # No outlier processing
    clean_x, clean_y = [], []
    n = len(y_values)
    for i in range(n):
        start_idx = max(0, i - window_size)
        end_idx = min(n, i + window_size + 1)
        window_avg = np.mean(y_values[start_idx:end_idx])
        if y_values[i] <= (1 + proportion_threshold) * window_avg:
            clean_x.append(x_values[i])
            clean_y.append(y_values[i])
    return np.array(clean_x), np.array(clean_y)

# Remove outliers if a proportion threshold is provided
data_keys = list(data.keys())
data_keys.remove("x")
if proportion_threshold is not None:
    for k in data_keys:
        ktype = k.split('_')[0]
        data[f"x_{ktype}"], data[k] = \
            remove_outliers_with_window(data["x"], data[k], proportion_threshold, window_size)
else:
    for k in data_keys:
        ktype = k.split('_')[0]
        data[f"x_{ktype}"] = data["x"]

# Output each curve's data to a separate CSV file
for curve_name in data_keys:
    x_key = f"x_{curve_name.split('_')[0]}"
    y_key = curve_name
    if proportion_threshold is not None:
        output_csv_path = os.path.join(folder_path, f"{curve_name}_outliers_removed_w{window_size}_r{int(args.outlier_tolerance_offset_ratio)}.csv")
    else:
        output_csv_path = os.path.join(folder_path, f"{curve_name}_original.csv")
    df = pd.DataFrame({x_key: data[x_key], y_key: data[y_key]})
    df.to_csv(output_csv_path, index=False)
    print(f"{curve_name} data saved to: {output_csv_path}")

# Plot the data
plt.figure(figsize=(10, 6))

for k in data_keys:
    ktype = k.split('_')[0]
    plt.plot(data[f"x_{ktype}"], data[k], label=ktype)

# Customize the plot
plt.xlabel("node i")
plt.ylabel("Time (ms)")
plt.title(f"Setup time per node")
plt.legend()
plt.grid(True)

# Save the figure
if proportion_threshold is not None:
    output_filename = f"setup_time_outlier_w{window_size}_r{int(args.outlier_tolerance_offset_ratio)}.png"
else:
    output_filename = "setup_time_original.png"
output_path = os.path.join(folder_path, output_filename)
plt.savefig(output_path)
plt.close()

print(f"Figure saved to: {output_path}")
