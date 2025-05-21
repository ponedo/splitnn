import os
import sys
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

def parse_log(log_file, start_second, end_second):
    time_stamps = []
    cpu_user = []
    cpu_kernel = []
    cpu_total = []
    mem_used = []
    mem_total = []

    with open(log_file, 'r') as file:
        for line in file:
            if line.startswith("CPU"):
                parts = line.split("|")
                user_usage = float(parts[0].split(":")[1].strip()[:-1])  # Remove %
                kernel_usage = float(parts[1].split(":")[1].strip()[:-1])  # Remove %
                total_usage = float(parts[2].split(":")[1].strip()[:-1])  # Remove %
                cpu_user.append(user_usage)
                cpu_kernel.append(kernel_usage)
                cpu_total.append(total_usage)

            elif line.startswith("Memory"):
                parts = line.split("|")
                total_mem = float(parts[0].split(":")[1].strip().split()[0])  # MB
                used_mem = float(parts[1].split(":")[1].strip().split()[0])  # MB
                mem_total.append(total_mem)
                mem_used.append(used_mem)
                time_stamps.append(len(cpu_user) - 1)

    # Filter data by time range
    filtered_data = [
        [t, u, k, tot, mu, mt]
        for t, u, k, tot, mu, mt in zip(
            time_stamps, cpu_user, cpu_kernel, cpu_total, mem_used, mem_total
        )
        if start_second <= t <= end_second
    ]

    for i, _ in enumerate(filtered_data):
        filtered_data[i][0] = i

    return zip(*filtered_data)

def smooth_outliers(data, lower_percentile, upper_percentile, window_size=5):
    data = np.array(data)
    smoothed_data = data.copy()
    half_window = window_size // 2

    # Compute global percentiles
    global_lower_threshold = np.percentile(data, lower_percentile)
    global_upper_threshold = np.percentile(data, upper_percentile)

    for i in range(len(data)):
        # Check if the current value is an outlier
        if data[i] < global_lower_threshold or data[i] > global_upper_threshold:
            # Define the window boundaries
            start = max(0, i - half_window)
            end = min(len(data), i + half_window + 1)

            # Extract the window and filter points below the upper threshold
            window = data[start:end]
            filter_index = np.logical_and(window <= global_upper_threshold, window >= global_lower_threshold)
            filtered_window = window[filter_index]

            # Compute the average of the valid points in the window
            if len(filtered_window) > 0:
                smoothed_data[i] = np.mean(filtered_window)
            else:
                # If no valid points, leave the original value
                smoothed_data[i] = data[i]

    print(f"\tglobal_lower_threshold: {global_lower_threshold}")
    print(f"\tglobal_upper_threshold: {global_upper_threshold}")
    print(f"\traw_mean: {np.mean(data)}")
    print(f"\tsmoothed_mean: {np.mean(smoothed_data)}")
    return smoothed_data

def plot_usage(time_stamps, cpu_user, cpu_kernel, cpu_total, mem_used, mem_total, output_dir):
    file_suffix = "_".join(sys.argv[3:])

    # Plot CPU Usage
    plt.figure()
    plt.plot(time_stamps, cpu_user, label="User CPU Usage", linestyle="-", alpha=0.8)
    plt.plot(time_stamps, cpu_kernel, label="Kernel CPU Usage", linestyle="-.", alpha=0.8)
    plt.plot(time_stamps, cpu_total, label="Total CPU Usage", linestyle=":", alpha=0.8)
    plt.xlabel("Time (s)")
    plt.ylabel("CPU Usage (%)")
    plt.title("CPU Usage Over Time")
    plt.legend()
    plt.grid(True)
    plt.savefig(os.path.join(output_dir, f"cpu_usage_{file_suffix}.png"))
    plt.close()

    # Plot Memory Usage
    plt.figure()
    plt.plot(time_stamps, mem_used, label="Used Memory", linestyle="-", alpha=0.8)
    # plt.plot(time_stamps, mem_total, label="Total Memory", linestyle="--", alpha=0.8)
    plt.xlabel("Time (s)")
    plt.ylabel("Memory Usage (MB)")
    plt.title("Memory Usage Over Time")
    plt.legend()
    plt.grid(True)
    plt.savefig(os.path.join(output_dir, f"memory_usage_{file_suffix}.png"))
    plt.close()

def output_csv(time_stamps, cpu_user, cpu_kernel, cpu_total, mem_used, mem_total, output_dir):
    file_suffix = "_".join(sys.argv[3:])
    df = pd.DataFrame({
        "Timestamp": time_stamps,
        "User CPU": cpu_user,
        "Kernel CPU": cpu_kernel,
        "Total CPU": cpu_total,
        "Used Mem": mem_used,
        "Total Mem": mem_total,
    })
    df.to_csv(os.path.join(output_dir, f"cpu_mem_usage_{file_suffix}.csv"), index=False)
    
def main():
    if len(sys.argv) != 8:
        print("Usage: python3 plot_usage.py <log_file_path> <output_dir> <start_second> <end_second> <window_size> <lower_percentile> <upper_percentile>")
        sys.exit(1)

    log_file = sys.argv[1]
    output_dir = sys.argv[2]
    start_second = int(sys.argv[3])
    end_second = int(sys.argv[4])
    window_size = int(sys.argv[5])
    lower_percentile = float(sys.argv[6])
    upper_percentile = float(sys.argv[7])

    time_stamps, cpu_user, cpu_kernel, cpu_total, mem_used, mem_total = parse_log(
        log_file, start_second, end_second
    )

    # Smooth outliers with global percentiles
    print(f"Reading CPU User data")
    cpu_user = smooth_outliers(cpu_user, lower_percentile, upper_percentile, window_size)
    print(f"Reading CPU Kernel data")
    cpu_kernel = smooth_outliers(cpu_kernel, lower_percentile, upper_percentile, window_size)
    print(f"Reading CPU Total data")
    cpu_total = smooth_outliers(cpu_total, lower_percentile, upper_percentile, window_size)
    print(f"Reading Memory Used data")
    # mem_used = smooth_outliers(mem_used, lower_percentile, upper_percentile, window_size)
    output_csv(time_stamps, cpu_user, cpu_kernel, cpu_total, mem_used, mem_total, output_dir)
    plot_usage(time_stamps, cpu_user, cpu_kernel, cpu_total, mem_used, mem_total, output_dir)

if __name__ == "__main__":
    main()
