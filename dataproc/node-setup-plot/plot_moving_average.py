import os
import re
import matplotlib.pyplot as plt
import numpy as np
import argparse
import pandas as pd

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Process log files and generate a smoothed plot.")
parser.add_argument("folder_path", type=str, help="Path to the folder containing log files.")
parser.add_argument(
    "-w", "--window", type=int, required=True, help="Window size (W) for sliding window smoothing."
)
args = parser.parse_args()

# Path to the folder containing log files
folder_path = args.folder_path
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

# Function to apply sliding window smoothing
def sliding_window_smooth(x_values, y_values, window_size):
    smoothed_y = np.convolve(y_values, np.ones(window_size) / window_size, mode='same')
    return x_values, smoothed_y

# Apply smoothing to each curve
data["x_misc"], data["misc_time"] = sliding_window_smooth(data["x"], data["misc_time"], window_size)
data["x_fork"], data["fork_time"] = sliding_window_smooth(data["x"], data["fork_time"], window_size)
data["x_mount"], data["mount_time"] = sliding_window_smooth(data["x"], data["mount_time"], window_size)
data["x_unshare"], data["unshare_time"] = sliding_window_smooth(data["x"], data["unshare_time"], window_size)
data["x_total"], data["total_time"] = sliding_window_smooth(data["x"], data["total_time"], window_size)

# Output each curve's data to a separate CSV file
for curve_name in ["misc_time", "fork_time", "mount_time", "unshare_time", "total_time"]:
    x_key = f"x_{curve_name.split('_')[0]}"
    y_key = curve_name
    output_csv_path = os.path.join(folder_path, f"{curve_name}_smoothed_data_w{window_size}.csv")
    df = pd.DataFrame({x_key: data[x_key], y_key: data[y_key]})
    df.to_csv(output_csv_path, index=False)
    print(f"{curve_name} data saved to: {output_csv_path}")

# Plot the smoothed data
plt.figure(figsize=(10, 6))
plt.plot(data["x_misc"], data["misc_time"], label="misc")
plt.plot(data["x_fork"], data["fork_time"], label="fork")
plt.plot(data["x_mount"], data["mount_time"], label="rootfs")
plt.plot(data["x_unshare"], data["unshare_time"], label="unshare")
plt.plot(data["x_total"], data["total_time"], label="total")

# Customize the plot
plt.xlabel("node i")
plt.ylabel("Time (ms)")
plt.title(f"Setup time per node")
plt.legend()
plt.grid(True)

# Save the figure
output_filename = f"setup_time_smoothed_w{window_size}.png"
output_path = os.path.join(folder_path, output_filename)
plt.savefig(output_path)
plt.close()

print(f"Figure saved to: {output_path}")
