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
    "kill_time": r"kill time:\s+(\d+)",
}

# Data storage
data = {
    "x": [],  # XXX values
    "clean_time": [],
}

# Process each log file
for filename in sorted(os.listdir(folder_path)):
    if filename.startswith("kill.log.") and filename.split('.')[-1].isdigit():
        filepath = os.path.join(folder_path, filename)
        with open(filepath, 'r') as file:
            log_content = file.read()

        # Extract XXX value from filename
        xxx_value = int(filename.split('.')[-1])
        data["x"].append(xxx_value)

        # Extract and calculate time values
        kill_time = int(re.search(regex_patterns["kill_time"], log_content).group(1))

        data["clean_time"].append(kill_time)

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
    data["x_clean"], data["clean_time"] = remove_outliers_with_window(data["x"], data["clean_time"], proportion_threshold, window_size)
else:
    data["x_clean"] = data["x"]

# Output each curve's data to a separate CSV file
for curve_name in ["clean_time"]:
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
plt.plot(data["x_clean"], data["clean_time"], label="Clean Time")

# Customize the plot
plt.xlabel("node i")
plt.ylabel("Time (ms)")
plt.title(f"Clean time per node")
plt.legend()
plt.grid(True)

# Save the figure
if proportion_threshold is not None:
    output_filename = f"kill_time_outlier_w{window_size}_r{int(args.outlier_tolerance_offset_ratio)}.png"
else:
    output_filename = "kill_time_original.png"
output_path = os.path.join(folder_path, output_filename)
plt.savefig(output_path)
plt.close()

print(f"Figure saved to: {output_path}")
