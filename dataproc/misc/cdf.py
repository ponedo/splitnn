import numpy as np
import matplotlib.pyplot as plt
import sys

def plot_cdf(input_file, output_file):
    # Read data from the file
    labels = []
    values = []
    with open(input_file, 'r') as file:
        for line in file:
            if line.strip():
                label, value = line.strip().split("\t", 1)
                labels.append(label.replace("\\n", "\n"))  # Allow \n to represent line breaks
                values.append(float(value))

    # Sort the data
    sorted_indices = np.argsort(values)
    sorted_values = np.array(values)[sorted_indices]
    sorted_labels = np.array(labels)[sorted_indices]

    # Compute the CDF
    cdf = np.arange(1, len(sorted_values) + 1) / len(sorted_values)

    # Plot the CDF
    plt.figure(figsize=(10, 6))
    # plt.plot(sorted_values, cdf, linestyle='-', linewidth=2, marker='o', markersize=6, label='CDF Curve')
    plt.plot(sorted_values, cdf, linestyle='-', linewidth=2, marker='o', markersize=6)
    
    # Add data labels near the data points
    for x, y, label in zip(sorted_values, cdf, sorted_labels):
        plt.text(x, y, f'{label}', fontsize=10, ha='center', va='center')

    plt.title('')
    plt.xlabel('Experiment duration')
    plt.ylabel('CDF')
    plt.grid(True)
    # plt.legend()

    # Save the plot to a file
    plt.savefig(output_file)
    print(f"CDF plot saved to {output_file}")

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python plot_cdf.py <input_file> <output_file>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]
    plot_cdf(input_file, output_file)
