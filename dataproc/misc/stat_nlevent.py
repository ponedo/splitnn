import sys
import os
import heapq
import argparse
import concurrent.futures


# Get concurrency from command line or default to 4
parser = argparse.ArgumentParser()
parser.add_argument("k_model_result_dir")
parser.add_argument("--concurrency", type=int, default=4, help="Number of concurrent threads")
args, unknown = parser.parse_known_args()
concurrency = args.concurrency
k_model_result_dir = args.k_model_result_dir

if concurrency < 1:
    print(f"Concurrency must be at least 1, got {concurrency}. Setting to 1.")
    concurrency = 1
# Check if the provided directory exists
if not os.path.exists(k_model_result_dir):
    print(f"Directory {k_model_result_dir} does not exist.")
    exit(1)


# Calculate 25/50/75 percentiles of fib6_clean_tree and wireless_nlevent_flush time
def analyze_log(log_path):
    def streaming_percentiles(file_path, percentiles=[0.25, 0.5, 0.75]):
        # Use P^2 algorithm for streaming percentiles (approximate)
        class P2Quantile:
            def __init__(self, prob):
                self.prob = prob
                self.n = 0
                self.q = []
                self.np = [0]*5
                self.ni = [0]*5
                self.dn = [0, prob/2, prob, (1+prob)/2, 1]
            def insert(self, x):
                if self.n < 5:
                    self.q.append(x)
                    self.n += 1
                    if self.n == 5:
                        self.q.sort()
                        for i in range(5):
                            self.ni[i] = i
                        self.np = [0, self.prob, 2*self.prob, 3*self.prob, 1]
                else:
                    k = 0
                    if x < self.q[0]:
                        self.q[0] = x
                        k = 0
                    elif x < self.q[1]:
                        k = 0
                    elif x < self.q[2]:
                        k = 1
                    elif x < self.q[3]:
                        k = 2
                    elif x < self.q[4]:
                        k = 3
                    else:
                        self.q[4] = x
                        k = 3
                    for i in range(k+1, 5):
                        self.ni[i] += 1
                    for i in range(5):
                        self.np[i] += self.dn[i]
                    for i in range(1, 4):
                        d = self.np[i] - self.ni[i]
                        if (d >= 1 and self.ni[i+1] - self.ni[i] > 1) or (d <= -1 and self.ni[i-1] - self.ni[i] < -1):
                            d = int(d/abs(d))
                            qs = self.q[i] + d * (self.q[i+d] - self.q[i-1+d]) / (self.ni[i+d] - self.ni[i-1+d])
                            if self.q[i-1] < qs < self.q[i+1]:
                                self.q[i] = qs
                            else:
                                self.q[i] += d * (self.q[i+d] - self.q[i]) / (self.ni[i+d] - self.ni[i])
                            self.ni[i] += d
            def result(self):
                if self.n < 5:
                    self.q.sort()
                    idx = int(self.prob * (self.n - 1))
                    return self.q[idx]
                return self.q[2]
        quantiles = [P2Quantile(p) for p in percentiles]
        total = 0
        count = 0
        with open(file_path) as f:
            for line in f:
                line = line.strip()
                if line.isdigit():
                    v = int(line)
                    total += v
                    count += 1
                    for q in quantiles:
                        q.insert(v)
        for p, q in zip(percentiles, quantiles):
            print(f"{int(p*100)}th percentile: {q.result()}")
        if count > 0:
            print(f"Average: {total / count:.2f}")
        else:
            print("No valid integer values found.")
        avg = total / count if count > 0 else 0
        q25 = quantiles[0].result()
        q50 = quantiles[1].result()
        q75 = quantiles[2].result()
        return avg, q25, q50, q75

    return streaming_percentiles(log_path)


def inspect_one_result_dir(result_dir):
    print(f"Inspecting walk results")
    walk_results = analyze_log(os.path.join(
        result_dir, "server0", "kern_func",
        "topo_setup_test--fib6_clean_tree.txt"))
    print(f"Inspecting flush results")
    flush_results = analyze_log(os.path.join(
        result_dir, "server0", "kern_func",
        "topo_setup_test--wireless_nlevent_flush.txt"))
    return walk_results, flush_results


def scan_result_dirs(k_model_result_dir, concurrency):
    if not os.path.exists(k_model_result_dir):
        print(f"Directory {k_model_result_dir} does not exist.")
        return

    topo2results = {}
    subdirs = [d for d in os.listdir(k_model_result_dir) if os.path.isdir(os.path.join(k_model_result_dir, d))]
    tasks = []
    for subdir in subdirs:
        dir_elements = subdir.split("--")
        entry_key = None
        topo_name = None
        bbns_num = None
        disabled = False
        for i, element in enumerate(dir_elements):
            if i % 2 == 0:
                entry_key = element
            elif entry_key == "t":
                topo_name = element
            elif entry_key == "b":
                bbns_num = int(element)
            elif entry_key == "d":
                disabled = True if element == "1" else False
                if disabled:
                    print(f"Skipping disabled topology: {topo_name}, BBNS num: {bbns_num}")
                    break
        if disabled:
            continue

        if topo_name is not None and bbns_num is not None:
            tasks.append((topo_name, bbns_num, os.path.join(k_model_result_dir, subdir)))

    def process_task(task):
        topo_name, bbns_num, path = task
        walk_results, flush_results = inspect_one_result_dir(path)
        return topo_name, [bbns_num, *walk_results, *flush_results]

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        for topo_name, result in executor.map(process_task, tasks):
            if topo_name not in topo2results:
                topo2results[topo_name] = []
            topo2results[topo_name].append(result)

    # topo2results = {}
    # for subdir in os.listdir(k_model_result_dir):
    #     dir_elements = subdir.split("--")
    #     entry_key = None
    #     topo_name = None
    #     bbns_num = None
    #     for i, element in enumerate(dir_elements):
    #         if i % 2 == 0:
    #             entry_key = element
    #         elif entry_key == "t":
    #             topo_name = element
    #         elif entry_key == "b":
    #             bbns_num = int(element)
    #     print(f"Inspecting results for topology: {topo_name}, BBNS num: {bbns_num}")
    #     walk_results, flush_results = inspect_one_result_dir(os.path.join(k_model_result_dir, subdir))
    #     if topo_name not in topo2results:
    #         topo2results[topo_name] = []
    #     topo2results[topo_name].append([bbns_num, *walk_results, *flush_results])

    return topo2results


def output_results_to_csv(topo_name, results, output_file):
    # Sort results by BBNS number
    results.sort(key=lambda x: x[0])  # Sort by BBNS number
    # Write results to a CSV file
    with open(output_file, 'w') as f:
        f.write("BBNS_num,walk_avg,walk_25,walk_50,walk_75,flush_avg,flush_25,flush_50,flush_75\n")
        for result in results:
            bbns_num = result[0]
            walk_avg = result[1]
            walk_25 = result[2]
            walk_50 = result[3]
            walk_75 = result[4]
            flush_avg = result[5]
            flush_25 = result[6]
            flush_50 = result[7]
            flush_75 = result[8]
            f.write(f"{bbns_num},{walk_avg},{walk_25},{walk_50},{walk_75},{flush_avg},{flush_25},{flush_50},{flush_75}\n")


# Scan in best-k-model directory
if __name__ == "__main__":
    topo2results = scan_result_dirs(args.k_model_result_dir, args.concurrency)
    for topo_name, results in topo2results.items():
        print(f"Outputing results for topology: {topo_name}")
        output_results_to_csv(topo_name, results, f"{topo_name}_walk_flush_results.csv")
