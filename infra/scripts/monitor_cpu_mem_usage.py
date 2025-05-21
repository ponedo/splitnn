import os
import time
import sys

def read_cpu_stats():
    with open('/proc/stat', 'r') as file:
        # Read the first line (cpu stats)
        line = file.readline()
        stats = line.split()
        
        user = int(stats[1])
        nice = int(stats[2])
        system = int(stats[3])
        idle = int(stats[4])
        iowait = int(stats[5])
        irq = int(stats[6])
        softirq = int(stats[7])
        steal = int(stats[8])
        guest = int(stats[9])
        guest_nice = int(stats[10])

        kernel = system + iowait + irq + softirq + steal
        user_mode = user + nice
        total = user_mode + kernel + idle + guest + guest_nice

        return user_mode, kernel, total, idle

def read_memory_stats():
    with open('/proc/meminfo', 'r') as file:
        lines = file.readlines()
        mem_total = int(lines[0].split()[1])  # Total memory in kB
        mem_free = int(lines[1].split()[1])   # Free memory in kB
        mem_available = int(lines[2].split()[1])  # Available memory in kB
        return mem_total, mem_free, mem_available

def get_cpu_core_count():
    return os.cpu_count()

def log_usage(log_file):
    core_count = get_cpu_core_count()

    with open(log_file, 'w') as log:
        prev_user, prev_kernel, prev_total, prev_idle = read_cpu_stats()

        while True:
            time.sleep(1)
            curr_user, curr_kernel, curr_total, curr_idle = read_cpu_stats()

            user_usage = (curr_user - prev_user) / (curr_total - prev_total) * 100 * core_count
            kernel_usage = (curr_kernel - prev_kernel) / (curr_total - prev_total) * 100 * core_count
            total_usage = (curr_total - prev_total - (curr_idle - prev_idle)) / (curr_total - prev_total) * 100 * core_count

            mem_total, mem_free, mem_available = read_memory_stats()
            mem_used = mem_total - mem_available  # Used memory in kB

            log.write(
                f"CPU -> User: {user_usage:.2f}% | Kernel: {kernel_usage:.2f}% | Total: {total_usage:.2f}%\n"
                f"Memory -> Total: {mem_total / 1024:.2f} MB | Used: {mem_used / 1024:.2f} MB | Free: {mem_free / 1024:.2f} MB\n"
            )
            log.flush()

            prev_user, prev_kernel, prev_total, prev_idle = curr_user, curr_kernel, curr_total, curr_idle

if __name__ == "__main__":
    # log_file = "cpu_usage.log"
    log_file = sys.argv[1]
    log_usage(log_file)
