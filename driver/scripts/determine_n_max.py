import argparse

parser = argparse.ArgumentParser(description='A script to calculate max VM number n_max for multi-VM splitting')
parser.add_argument('-p', '--platform', type=str, required=True, help='Platform type (amd64 or arm64)')
parser.add_argument('-m', '--m-graph', type=int, required=True, help='Memory needed for the graph (GB)')
parser.add_argument('-M', '--m-conf', type=int, required=True, help='Configured memory size (GB)')
parser.add_argument('-S', '--s', type=int, required=True, help='Lower boundary of gain')
args = parser.parse_args()

m_graph = args.m_graph
m_conf = args.m_conf
platform = args.platform # 'amd64' or 'arm64'
S = args.s

if platform not in ["amd64", "arm64"]:
    raise ValueError("Platform must be either 'amd64' or 'arm64'.")

theta_m_conf_table = {
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
}

# def compute_gain(n, theta_m_conf, m_graph):
#     numerator = (n**2 - 1) * m_graph
#     dominator = n**3 * theta_m_conf
#     print(numerator, dominator)
#     gain = numerator / dominator
#     return gain


def compute_gain(n, theta_m_conf, m_graph):
    numerator = (2 * n - 1) * m_graph
    dominator = n**2 * (n - 1)**2 * theta_m_conf
    # print(numerator, dominator)
    gain = numerator / dominator
    return gain

if __name__ == "__main__":
    theta_m_conf = theta_m_conf_table[platform][m_conf]
    # Calculate n_max
    n_max = 0
    for n in range(2, 25):
        gain = compute_gain(n, theta_m_conf, m_graph)
        print(f"n: {n}\tgain: {gain:.4f}")
        if gain > S:
            n_max = n
    print(f"n_max: {n_max}")
