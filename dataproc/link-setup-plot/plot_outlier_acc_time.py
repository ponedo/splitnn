import os
import random
import matplotlib.pyplot as plt
import numpy as np
import argparse
import pandas as pd

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Process log files and generate a plot.")
parser.add_argument("log_path", type=str, help="Path to the folder containing log files.")
parser.add_argument(
    "-l", "--lower-percentage", type=float, help="Lower bouund of filtering."
)
parser.add_argument(
    "-u", "--upper-percentage", type=float, help="Upper bouund of filtering."
)
args = parser.parse_args()

# Path to the folder containing log files
log_path = args.log_path
log_dir_path = os.path.dirname(log_path)
output_dir = os.path.join(log_dir_path, "link_setup_figures")
os.makedirs(output_dir, exist_ok=True)

lower_percentage = args.lower_percentage
upper_percentage = args.upper_percentage

# Regular expressions to extract values from logs
regex_patterns = {
    "total_time": r"total run time:\s+(\d+)",
}

def read_data():
    # Data storage
    data = {
        "x": [],  # XXX values
        "total_time": [],
        "acc_setup_time": [],
    }

    # Process each log file
    acc_setup_time = 0
    link_log_filepath = os.path.join(log_path)
    with open(link_log_filepath, "r") as f:
        for i, line in enumerate(f):
            if line.startswith("Link"):
                elements = line.strip().split()
                link_index_str = elements[1].split('.')[1]
                link_index = int(link_index_str)
                t_ns_str = elements[2][:-2]
                t_ns = int(t_ns_str)
                data['x'].append(link_index + 1)
                data['total_time'].append(t_ns)
                acc_setup_time += t_ns
                data['acc_setup_time'].append(acc_setup_time)

    # Sort data by x (XXX values)
    sorted_indices = np.argsort(data["x"])
    for key in data.keys():
        data[key] = np.array(data[key])[sorted_indices]
        if key == "x":
            continue
        data[key] = data[key] / (10 ** 6)
    return data

def get_linear_data(data):
    # Calculate slope and intercept of the line
    max_acc_time = data["acc_setup_time"][-1]
    max_x = data["x"][-1]
    a = max_acc_time / (max_x ** 2)
    k = 2 * a
    b = np.mean(data["total_time"][:10]) - 5 * k

    # Create linear data
    data["linear"] = []
    for x in data["x"]:
        y = k * x + b
        data["linear"].append(y)
    return data

ESCAPE_RATIO = 0.1
def smooth_outliers(data, lower_percentage, upper_percentage):
    data["smoothed_per_link_time"] = []
    data_len = len(data["x"])
    for i in range(data_len):
        # Check if the current value is an outlier
        y_anchor = data["linear"][i]
        lower_threshold = y_anchor * (1 - lower_percentage / 100)
        upper_threshold = y_anchor * (1 + upper_percentage / 100)
        cur_link_time = data["total_time"][i]
        if cur_link_time < lower_threshold or cur_link_time > upper_threshold:
            escaped = random.random() < ESCAPE_RATIO
            if escaped:
                smoothed_time = data["total_time"][i]
            elif cur_link_time < lower_threshold:
                smoothed_time = y_anchor - random.random() * (y_anchor - lower_threshold)
            elif cur_link_time > upper_threshold:
                # Smooth the outlier
                smoothed_time = y_anchor + random.random() * (upper_threshold - y_anchor)
        else:
            smoothed_time = data["total_time"][i]
        data["smoothed_per_link_time"].append(smoothed_time)
    return data

def output_csv(data):
    # Output each curve's data to a separate CSV file
    for curve_name in [
        "total_time",
        "smoothed_per_link_time",
        "linear",
        "acc_setup_time",
        ]:
        x_key = f"x"
        y_key = curve_name
        if lower_percentage and upper_percentage:
            output_csv_path = os.path.join(output_dir, f"{curve_name}_{int(lower_percentage)}_{int(upper_percentage)}.csv")
        else:
            output_csv_path = os.path.join(output_dir, f"{curve_name}_original.csv")
        df = pd.DataFrame({x_key: data[x_key], y_key: data[y_key]})
        df.to_csv(output_csv_path, index=False)
        print(f"{curve_name} data saved to: {output_csv_path}")

def plot_original_per_link_time(data):
    # Plot the data
    plt.figure(figsize=(10, 6))
    plt.plot(data["x"], data["total_time"], label="per link setup time")
    plt.plot(data["x"], data["linear"], '--', label="linear")

    # Customize the plot
    plt.xlabel("link i")
    plt.ylabel("Time (ms)")
    plt.title(f"Per link setup time")
    plt.legend()
    plt.grid(True)

    # Save the figure
    output_filename = "link_setup_time_original.png"
    output_path = os.path.join(output_dir, output_filename)
    plt.savefig(output_path)
    plt.close()
    print(f"Figure saved to: {output_path}")

def plot_smoothed_per_link_time(data):
    # Plot the data
    plt.figure(figsize=(10, 6))
    plt.plot(data["x"], data["smoothed_per_link_time"], label="per link setup time")
    plt.plot(data["x"], data["linear"], '--', label="linear")

    # Customize the plot
    plt.xlabel("link i")
    plt.ylabel("Time (ms)")
    plt.title(f"Per link setup time")
    plt.legend()
    plt.grid(True)

    # Save the figure
    output_filename = f"link_setup_time_{int(lower_percentage)}_{int(upper_percentage)}.png"
    output_path = os.path.join(output_dir, output_filename)
    plt.savefig(output_path)
    plt.close()
    print(f"Figure saved to: {output_path}")

def plot_acc_time(data):
    # Plot the data
    plt.figure(figsize=(10, 6))
    plt.plot(data["x"], data["acc_setup_time"], label="accumulated link setup time")

    # Customize the plot
    plt.xlabel("link i")
    plt.ylabel("Time (ms)")
    plt.title(f"Accumulated link setup time")
    plt.legend()
    plt.grid(True)

    # Save the figure
    output_filename = "link_acc_setup_time.png"
    output_path = os.path.join(output_dir, output_filename)
    plt.savefig(output_path)
    plt.close()
    print(f"Figure saved to: {output_path}")

if __name__ == "__main__":
    data = read_data()
    data = get_linear_data(data)
    data = smooth_outliers(data, lower_percentage, upper_percentage)
    output_csv(data)
    plot_original_per_link_time(data)
    plot_smoothed_per_link_time(data)
    plot_acc_time(data)
