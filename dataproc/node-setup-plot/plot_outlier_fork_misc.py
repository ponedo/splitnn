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
    "mkdir_time": r"mkdir time:\s+(\d+)",
    "fork1_time": r"fork 1 time:\s+(\d+)",
    "fork2_time": r"fork 2 time:\s+(\d+)",
    "unshare_time": r"unshare time:\s+(\d+)",
    "mount_time": r"rootfs time:\s+(\d+)",
    "misc_time": r"miscellaneous time:\s+(\d+)",
    "total_time": r"total run time:\s+(\d+)",
}

# Data storage
data = {
    "x": [],  # XXX values
    "misc_time": [],
    "fork_time": [],
    "mount_time": [],
    "unshare_time": [],
    "total_time": [],
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
        mkdir_time = int(re.search(regex_patterns["mkdir_time"], log_content).group(1))
        fork1_time = int(re.search(regex_patterns["fork1_time"], log_content).group(1))
        fork2_time = int(re.search(regex_patterns["fork2_time"], log_content).group(1))
        unshare_time = int(re.search(regex_patterns["unshare_time"], log_content).group(1))
        mount_time = int(re.search(regex_patterns["mount_time"], log_content).group(1))
        misc_time = int(re.search(regex_patterns["misc_time"], log_content).group(1))
        total_time = int(re.search(regex_patterns["total_time"], log_content).group(1))

        data["misc_time"].append(mkdir_time + misc_time)
        data["fork_time"].append(fork1_time + fork2_time)
        data["mount_time"].append(mount_time)
        data["unshare_time"].append(unshare_time)
        data["total_time"].append(total_time)

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
if proportion_threshold is not None:
    data["x_misc"], data["misc_time"] = remove_outliers_with_window(data["x"], data["misc_time"], proportion_threshold, window_size)
    data["x_fork"], data["fork_time"] = remove_outliers_with_window(data["x"], data["fork_time"], proportion_threshold, window_size)
    data["x_mount"], data["mount_time"] = remove_outliers_with_window(data["x"], data["mount_time"], proportion_threshold, window_size)
    data["x_unshare"], data["unshare_time"] = remove_outliers_with_window(data["x"], data["unshare_time"], proportion_threshold, window_size)
    data["x_total"], data["total_time"] = remove_outliers_with_window(data["x"], data["total_time"], proportion_threshold, window_size)
else:
    data["x_misc"] = data["x"]
    data["x_fork"] = data["x"]
    data["x_mount"] = data["x"]
    data["x_unshare"] = data["x"]
    data["x_total"] = data["x"]

# Plot the data
plt.figure(figsize=(10, 6))
plt.plot(data["x_misc"], data["misc_time"], label="misc")
plt.plot(data["x_fork"], data["fork_time"], label="fork")
# plt.plot(data["x_mount"], data["mount_time"], label="rootfs")
# plt.plot(data["x_unshare"], data["unshare_time"], label="unshare")
# plt.plot(data["x_total"], data["total_time"], label="total")

# Customize the plot
plt.xlabel("node i")
plt.ylabel("Time (ms)")
plt.title(f"Setup time per node")
plt.legend()
plt.grid(True)

# Save the figure
if proportion_threshold is not None:
    output_filename = f"tiny_setup_time_analysis_outlier_w{window_size}_r{int(args.outlier_tolerance_offset_ratio)}.png"
else:
    output_filename = "tiny_setup_time_analysis_original.png"
output_path = os.path.join(folder_path, output_filename)
plt.savefig(output_path)
plt.close()

print(f"Figure saved to: {output_path}")
