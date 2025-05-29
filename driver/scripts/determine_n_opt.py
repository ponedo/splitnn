# Determine the best VM number for multi-VM splitting based on modeling data
import argparse

########################### Arguments ###########################
parser = argparse.ArgumentParser(description='A script to calculate optimal VM number n_opt for multi-VM splitting')
parser.add_argument('-p', '--platform', type=str, required=True, help='Platform type (amd64 or arm64)')
parser.add_argument('-E', '--E-max-filepath', type=str, required=True, help='Path to the E_max data file')
parser.add_argument('-m', '--m-req', type=int, required=True, help='Total memory required for the emulation')
args = parser.parse_args()

platform = args.platform # 'amd64' or 'arm64'
E_max_filepath = args.E_max_filepath
m_req = args.m_req

if platform not in ["amd64", "arm64"]:
    raise ValueError("Platform must be either 'amd64' or 'arm64'.")

############################# Parameters Table ###########################

para_table = {
    "theta_m_conf": { # Unit: GB
        "amd64": {
            8: 2.814,
            25: 3.190,
            50: 3.746,
            100: 4.820,
            200: 7.009,
            300: 8.857,
            400: 10.590,
            500: 10.942,
        },
        "arm64": {
            8: 1.642,
            25: 1.934,
            50: 2.360,
            100: 3.251,
            200: 5.118,
            300: 6.890,
            400: 8.722,
            500: 10.535,
        }
    },
    "X": {
        "amd64": 0.00329,  # Example value, adjust as needed
        "arm64": 0.00931,  # Example value, adjust as needed
    },
    "Y": {
        "amd64": 0.03918,  # Example value, adjust as needed
        "arm64": 0.02624,  # Example value, adjust as needed
    },
    "Z": {
        "amd64": 0.0127,  # Example value, adjust as needed
        "arm64": 0.0037,  # Example value, adjust as needed
    }
}

V_exp = (10000 + 9472 + 12817) / 3
X = para_table["X"][platform]
Y = para_table["Y"][platform]
Z = para_table["Z"][platform]
search_n_range = range(2, 129)  # Range of n to search for optimal value
search_m_conf_range = [8, 25, 50, 100, 200, 300, 400, 500]  # Range of m_conf to search for optimal value

############################## Functions to Compute Gain ###########################

def read_E_max_data():
    # This function should read the E_max modeling data from a file or database
    # For now, we will just return a placeholder value
    with open(E_max_filepath, 'r') as f:
        # Find the line starting with the hint "Results averaged across runs and topos: "
        # After the hint there should be a list of E_max values, wrapped with square brackets,
        # e.g., "Results averaged across runs and topos: [10000, 9998, 9996, ...]"
        for line in f:
            if line.startswith("Results averaged across runs and topos: "):
                # Extract the string after the hint
                e_max_str = line.split("Results averaged across runs and topos: ")[1].strip()
                # Convert the string to a list of integers
                e_max_data = eval(e_max_str)
                return e_max_data
    # If the file does not contain the expected line, return a default value
    return [10000-2*i for i in range(1, 129)]

E_max_data = read_E_max_data()  # Placeholder function to read E_max data

def E_max(n):
    return E_max_data[n-1] if 1 <= n <= len(E_max_data) else None

def compute_T_vm(n):
    # Compute T_vm based on E_max
    E_max_n = E_max(n)
    T_vm_n = E_max_n * V_exp / n * (X + Z) + E_max_n ** 2 * Y
    return T_vm_n
T_vm = lambda n: compute_T_vm(n)

def compute_M_vm(n, m_conf):
    theta_m_conf = para_table["theta_m_conf"][platform][m_conf]
    return n * theta_m_conf
M_vm = lambda n, m_conf: compute_M_vm(n, m_conf)

def compute_gain1(n, m_conf):
    numerator = (T_vm(1) - T_vm(n)) / T_vm(1)
    dominator = M_vm(n, m_conf) / m_req
    gain1 = numerator / dominator
    return gain1
Gain1 = lambda n, m_conf: compute_gain1(n, m_conf)

def compute_gain2(n, m_conf):
    pass
Gain2 = lambda n, m_conf: compute_gain2(n, m_conf)

def search_n_opt_and_m_conf():
    # Search for the optimal n and m_conf value that maximizes Gain1
    # Constraint: n * m_conf >= m_req
    n_opt = 1
    m_conf_opt = 8
    m_extra_opt = n_opt * para_table["theta_m_conf"][platform][m_conf_opt]
    max_gain1 = Gain1(1, 8)
    # Store all search results
    search_results = []
    for n in search_n_range:
        for m_conf in search_m_conf_range:
            if n * m_conf < m_req:
                continue
            gain1 = Gain1(n, m_conf)
            theta_m_conf = para_table["theta_m_conf"][platform][m_conf]
            m_extra = n * theta_m_conf
            if gain1 > max_gain1:
                max_gain1 = gain1
                n_opt = n
                m_conf_opt = m_conf
                m_extra_opt = m_extra
            search_results.append((n, m_conf, m_extra, gain1))
    optimal_result = (n_opt, m_conf_opt, m_extra_opt, max_gain1)
    return search_results, optimal_result

############################## Functions to Compute Gain ###########################

if __name__ == "__main__":
    # Read E_max modeling data
    E_max_data = read_E_max_data()

    # Compute the optimal n
    search_results, (n_opt, m_conf_opt, m_extra_opt, max_gain1) = search_n_opt_and_m_conf()

    # Print the search results, sorted by Gain1
    search_results.sort(key=lambda x: x[3], reverse=True)
    print("\nSearch Results (sorted by Gain1):")
    for n, m_conf, m_extra, gain1 in search_results:
        print(f"n: {n}\tm_conf: {m_conf}\tm_extra: {m_extra:.2f}\tGain1: {gain1:.4f}")

    # Print the optimal n and m_conf
    print(f"Optimal n: {n_opt}\tOptimal m_conf: {m_conf_opt}\tm_extra: {m_extra_opt}\tMaximum Gain1: {max_gain1:.4f}")
