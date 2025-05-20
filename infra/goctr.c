#ifndef _GNU_SOURCE
# define _GNU_SOURCE
#endif

#include <unistd.h>
#include <sched.h>
#include <syscall.h>
#include <fcntl.h>
#include <sys/mount.h>
#include <sys/wait.h>
#include <sys/eventfd.h>
#include <sys/stat.h>

#include <time.h>
#include <limits.h>
#include <signal.h>
#include <errno.h>
#include <string.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>

const int NS_ALL = CLONE_NEWNS|CLONE_NEWPID|CLONE_NEWNET|CLONE_NEWIPC|CLONE_NEWUTS;
const int NS_EXCEPT_NET = CLONE_NEWNS | CLONE_NEWPID | CLONE_NEWIPC | CLONE_NEWUTS;
int verbose_mode = 0;

// ======================== Helper functions ========================

#define VERBOSE_OUTPUT(fmt, ...) \
    do { \
        if (verbose_mode) { \
            fprintf(stderr, fmt, ##__VA_ARGS__); \
            fflush(stderr); /* Ensure output is flushed immediately */ \
        } \
    } while (0)

static void verbose_output_ts(const char *ts_name) {
    struct timespec ts;
    uint64_t ts_value;
    if (verbose_mode) {
        clock_gettime(CLOCK_MONOTONIC, &ts); // end_time
        ts_value = ts.tv_sec * 1e9 + ts.tv_nsec;
        VERBOSE_OUTPUT("%s: %lu ns\n", ts_name, ts_value);
    }
}

void set_realtime_priority(int priority) {
    struct sched_param param;
    param.sched_priority = priority;

    if (sched_setscheduler(0, SCHED_FIFO, &param) == -1) {
        perror("sched_setscheduler failed");
    } else {
        printf("Successfully set real-time priority\n");
    }
}

void pin_to_cpu(int cpu) {
    cpu_set_t cpuset;
    CPU_ZERO(&cpuset);
    CPU_SET(cpu, &cpuset);

    if (sched_setaffinity(0, sizeof(cpu_set_t), &cpuset) == -1) {
        perror("sched_setaffinity failed");
    }
}

int mkdir_p(const char *path, mode_t mode) {
    char *temp = strdup(path);
    char *pos = temp;
    int ret = 0;

    // Handle edge cases
    if (path == NULL || path[0] == '\0') {
        free(temp);
        return -1;
    }

    // Iterate through the path, creating directories as needed
    while ((pos = strchr(pos, '/')) != NULL) {
        *pos = '\0';
        fprintf(stderr, "mkdir_p target 2: %s, temp: %s, ret: %d\n", path, temp, ret);
        if (*temp != '\0' && mkdir(temp, mode) != 0 && errno != EEXIST) {
            ret = -1;
            break;
        }
        *pos = '/';
        pos++;
    }

    // Create the final directory (after the last '/')
    if (ret == 0 && mkdir(temp, mode) != 0 && errno != EEXIST) {
        ret = -1;
    }

    free(temp);
    return ret;
}

void redirect_stdout_stderr(const char *log_file_path) {
    // Redirect stderr to the file (overwrite mode)
    if (freopen(log_file_path, "w", stderr) == NULL) {
        fprintf(stderr, "Error: Could not redirect stderr to %s.\n", log_file_path);
    }
    if (freopen(log_file_path, "w", stderr) == NULL) {
        fprintf(stderr, "Error: Could not redirect stderr to %s.\n", log_file_path);
    }
}

void print_usage(const char *prog_name) {
    fprintf(stderr, "Usage:\n");
    fprintf(stderr, "  %s run <base_dir> <hostname> <img_rootfs_dir> [--netns=<netns_path>] [--pid-file=<pid_file_path>] [-V]\n", prog_name);
    fprintf(stderr, "  %s exec <pid> <cmdline...>\n", prog_name);
    fprintf(stderr, "  %s kill <pid>\n", prog_name);
    exit(EXIT_FAILURE);
}

static int child_err(const char *prefix, int write_fd) {
    int err = errno, n;
    const char *error_msg = strerror(err);
    n = write(write_fd, prefix, strlen(prefix));
    n = write(write_fd, error_msg, strlen(error_msg));
    close(write_fd);
    return err;
}

int write_pid_to_file(const char *pid_file_path, int pid) {
    // Open the file for writing, overwrite if it exists
    FILE *file = fopen(pid_file_path, "w");
    if (!file) {
        fprintf(stderr, "Failed to open PID file\n");
        return -1;
    }

    // Write the PID to the file
    if (fprintf(file, "%d\n", pid) < 0) {
        fprintf(stderr, "Failed to write to PID file.\n");
        fclose(file);
        return -1;
    }

    // Close the file
    fclose(file);
    return 0;
}

// ======================== Operation executors ========================

// in child process with new namespace
static int container_init(
    const char* newroot,
    const char* overlay_opt,
    const char* volume_src,
    const char* volume_tgt,
    const char* hostname,
    int err_fd
    ) {
    close(STDIN_FILENO);
    close(STDOUT_FILENO);
    // close(STDERR_FILENO);
    int flags = fcntl(err_fd, F_GETFD);
    flags |= FD_CLOEXEC;
    fcntl(err_fd, F_SETFD, flags);

    if(mount("none", "/", NULL, MS_PRIVATE|MS_REC, NULL) != 0) {
        return child_err("mount rprivate / failed: ", err_fd);
    }
    // mount overlay
    if(mount("overlay", newroot, "overlay", 0, overlay_opt) != 0) {
        return child_err("mount overlay failed: ", err_fd);
    }
    if(mount("none", newroot, NULL, MS_PRIVATE|MS_REC, NULL) != 0) {
        return child_err("mount rprivate newroot failed: ", err_fd);
    }

    char abs_volume_src[4096]; 
    if (volume_src != NULL && volume_tgt != NULL) {
        // Get absolute path of volume source directory
        if (realpath(volume_src, abs_volume_src) == NULL) {
            return child_err("non-existent volume_src: ", err_fd);
        }
    }

    if(chdir(newroot) != 0) {
        return child_err("chdir failed: ", err_fd);
    }

    // change into newroot directory
    if (volume_src != NULL && volume_tgt != NULL) {
        // Check validity of volume target directory
        if (volume_tgt[0] != '/' || strlen(volume_tgt) < 1) {
            return child_err("Invalid volume_tgt (%s), should start with \'/\' and len >- 1", err_fd);
        }
        const char *rel_volume_tgt = volume_tgt + 1;

        // Check if the mount target directory exists in the container's filesystem
        struct stat st;
        if (stat(rel_volume_tgt, &st) != 0) {
            // Target directory doesn't exist, create it
            if (mkdir_p(rel_volume_tgt, 0755) != 0) {
                return child_err("mkdir failed: ", err_fd);
            }
        }

        // mount the volume inside the container's filesystem
        if (mount(abs_volume_src, rel_volume_tgt, NULL, MS_PRIVATE|MS_BIND|MS_REC, NULL) != 0) {
            return child_err("mount volume failed: ", err_fd);
        }
        // fprintf(stderr, "mount abs_volume_src: %s\n", abs_volume_src);
        // fprintf(stderr, "mount rel_volume_tgt: %s\n", rel_volume_tgt);
    }

    // pivot root
    // https://unix.stackexchange.com/questions/456620/how-to-perform-chroot-with-linux-namespaces
    if(syscall(SYS_pivot_root, ".", ".") != 0) {
        return child_err("pivot_root failed: ", err_fd);
    }
    if(chroot(".") != 0) {
        return child_err("chroot failed: ", err_fd);
    }
    if(umount2 (".", MNT_DETACH) != 0) {
        return child_err("umount2 failed: ", err_fd);
    }
    // mount proc
    if(mount("proc", "/proc", "proc", MS_NOSUID|MS_NOEXEC|MS_NODEV, NULL) != 0) {
        return child_err("mount /proc failed: ", err_fd);
    }
    // mount sysfs
    if (mount("sysfs", "/sys", "sysfs", MS_NOSUID|MS_NOEXEC, NULL) != 0) {
        return child_err("mount /sys failed: ", err_fd);
    }
    // mount dev
    if (mount("devtmpfs", "/dev", "devtmpfs", MS_NOSUID|MS_NOEXEC, NULL) != 0) {
        return child_err("mount /dev failed: ", err_fd);
    }
    verbose_output_ts("rootfs_time");

    // new session, detach to become a daemon process 
    if(setsid() < 0) {
        return child_err("setsid failed: ", err_fd);
    }

    // other miscellaneous configuration, maybe warning is better choice
    if(signal(SIGCLD, SIG_IGN) < 0) {
        return child_err("ignore SIGCLD failed: ", err_fd);
    }
    if(sethostname(hostname, strlen(hostname))) {
        return child_err("sethostname failed: ", err_fd);
    }
    if(clearenv() != 0) {
        return child_err("clearenv failed: ", err_fd);
    }
    if(putenv("HOME=/root")
    || putenv("PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")) {
        return child_err("putenv failed: ", err_fd);
    }
    verbose_output_ts("setenv_time");

    close(STDERR_FILENO);

    // sleep infinity, need a process with low resource requirement
    execlp("sleep", "sleep", "inf", NULL);
    // close(err_fd);
    // while (1) {
    //     pause(); // Blocks the process indefinitely
    // }
    // should not be executed here
    verbose_output_ts("execlp_time");
    return child_err("execlp failed: ", err_fd);
}

// in child process
int container_enter(pid_t ctr_pid, char *const* argv, int err_fd) {
    int flags = fcntl(err_fd, F_GETFD);
    if(flags < 0)
        return child_err("failed to fcntl F_GETFD: ", err_fd);
    flags |= FD_CLOEXEC;
    if(fcntl(err_fd, F_SETFD, flags) < 0)
        return child_err("failed to fcntl F_SETFD: ", err_fd);

    int pid_fd = syscall(SYS_pidfd_open, ctr_pid, 0);
    // int pid_fd = pidfd_open(ctr_pid, 0);
    if(pid_fd < 0)
        return child_err("failed to pidfd_open: ", err_fd);

    fprintf(stderr, "pid_fd: %d\n", pid_fd);
    int ret = setns(pid_fd, NS_ALL);
    close(pid_fd);
    if(ret != 0)
        return child_err("failed to setns: ", err_fd);

    execvp(argv[0], &argv[0]);
    return child_err("failed to execvp: ", err_fd);
}

// in parent process
// on success, ret > 0 means child pid.
// ret < 0 for parent err, ret == 0 for child err
int container_run_inner(
    const char *base_dir,
    const char *hostname,
    const char *img_rootfs_dir,
    const char *volume_src,
    const char *volume_tgt,
    const char *netns_path,
    char *chd_err, size_t max_len) {
    // 0755
    const mode_t MODE = S_IRWXU | (S_IRGRP|S_IXGRP) | (S_IROTH|S_IXOTH);
    const char* UPPER_DIR = "upper";
    const char* WORK_DIR = "work";
    const char* NEWROOT = "merged";
    int n;
    int netns_fd = -1;

    if(access(base_dir, F_OK) && mkdir(base_dir, MODE)) return -1;

    int dir_fd = open(base_dir, O_RDONLY);
    if(dir_fd < 0) return -1;
    if((faccessat(dir_fd, UPPER_DIR, F_OK, 0) && mkdirat(dir_fd, UPPER_DIR, MODE))
    || (faccessat(dir_fd, WORK_DIR, F_OK, 0) && mkdirat(dir_fd, WORK_DIR, MODE))
    || (faccessat(dir_fd, NEWROOT, F_OK, 0) && mkdirat(dir_fd, NEWROOT, MODE))) {
        close(dir_fd);
        return -1;
    }
    if(close(dir_fd) != 0) return -1;

    char overlay_opt[PATH_MAX * 3];
    char new_root[PATH_MAX];
    snprintf(overlay_opt, sizeof(overlay_opt),
        "lowerdir=%s,upperdir=%s/%s,workdir=%s/%s",
        img_rootfs_dir, base_dir, UPPER_DIR, base_dir, WORK_DIR);
    snprintf(new_root, sizeof(new_root), "%s/%s", base_dir, NEWROOT);

    int err_fds[2], event_fd;
    if(pipe(err_fds) != 0 || (event_fd = eventfd(0, 0)) < 0) return -1;

    // Open the existing network namespace file if provided
    if (netns_path) {
        netns_fd = open(netns_path, O_RDONLY);
        if (netns_fd < 0) {
            snprintf(chd_err, max_len, "open netns_fd failed: %s", strerror(errno));
            return -1;
        }
    }
    verbose_output_ts("overlay_time");

    pid_t pid = fork();
    if (pid < 0) {
        close(err_fds[0]), close(err_fds[1]), close(event_fd);
        return -1;  
    } else if(pid == 0) {
        verbose_output_ts("fork1_time");
        close(err_fds[0]);
        if (netns_path) {
            // If a network namespace is provided, unshare all namespaces except network
            if (unshare(NS_EXCEPT_NET) != 0) {
                close(event_fd);
                exit(child_err("unshare failed: ", err_fds[1]));
            }

            // Join the provided network namespace
            if (setns(netns_fd, CLONE_NEWNET) < 0) {
                close(event_fd);
                exit(child_err("setns failed: ", err_fds[1]));
            }
            close(netns_fd);
        } else {
            if(unshare(NS_ALL) != 0) {
                close(event_fd);
                exit(child_err("unshare failed: ", err_fds[1]));
            }
        }
        verbose_output_ts("unshare_time");

        pid = fork();
        if(pid < 0) {
            close(event_fd);
            exit(child_err("second fork failed: ", err_fds[1]));
        } else if(pid == 0) {
            verbose_output_ts("fork2_time");
            close(event_fd);
            exit(container_init(new_root, overlay_opt,
                volume_src, volume_tgt, hostname, err_fds[1]));
            // should not execute here
        }
        close(err_fds[1]);
        uint64_t pid_u64 = pid;
        n = write(event_fd, &pid_u64, sizeof(pid_u64));
        close(event_fd);
        verbose_output_ts("write_pid_time");
        exit(0);
        // should not execute here
    }

    close(err_fds[1]);
    if (netns_fd >= 0) close(netns_fd);

    ssize_t len = read(err_fds[0], chd_err, max_len);
    verbose_output_ts("read_err_time");
    // anyway, child should exit immediately 
    waitpid(pid, NULL, 0);
    if(len > 0) {
        chd_err[len] = '\0';
        close(err_fds[0]), close(event_fd);
        return 0;
    }
    verbose_output_ts("wait_child_time");

    // receive grandchild pid from child
    uint64_t pid_u64;
    if(read(event_fd, &pid_u64, sizeof(pid_u64)) == sizeof(pid_u64))
        pid = pid_u64;
    else
        pid = -1;

    verbose_output_ts("read_pid_time");
    close(err_fds[0]), close(event_fd);
    return pid;
}

// in parent process
// on success, ret > 0 means child pid, need to be waited and recycled
// ret < 0 for parent err, ret == 0 for child err
static int container_exec_inner(
    pid_t ctr_pid, char *const* argv, char *chd_err, size_t max_len) {
    int err_fds[2];
    pid_t ret;
    ssize_t err_len;

    if(pipe(err_fds) != 0) return -1;

    ret = fork();
    if(ret < 0) {
        close(err_fds[0]), close(err_fds[1]);
        return -1;
    } else if(ret == 0) {
        close(err_fds[0]);
        exit(container_enter(ctr_pid, argv, err_fds[1]));
        // should not be executed
    }
    close(err_fds[1]);

    err_len = read(err_fds[0], chd_err, max_len);
    if(err_len > 0) {
        chd_err[err_len] = '\0';
        waitpid(ret, NULL, 0);
        ret = 0;
    }
    close(err_fds[0]);
    return ret;
}

// ======================== Operation wrappers ========================

int container_run(
    const char *base_dir,
    const char *hostname,
    const char *img_rootfs_dir,
    const char *volume_src,
    const char *volume_tgt,
    const char *netns_path) {
    char chd_err[256];
    int pid;

    if ((base_dir == NULL) || (hostname == NULL) || (img_rootfs_dir == NULL)) {
        fprintf(stderr, "Empty base_dir or hostname\n");
        return -1;
    }

    pid = container_run_inner(
        base_dir, hostname, img_rootfs_dir,
        volume_src, volume_tgt, netns_path,
        chd_err, sizeof(chd_err) - 1);
    if (pid < 0) {
        fprintf(stderr, "Parent error: %s\n", chd_err);
        return -1;
    } else if (pid == 0) {
        fprintf(stderr, "Child error: %s\n", chd_err);
        return -1;
    } else { // normal case
        return pid;
    }
}

int container_exec(int pid, char **cmdline) {
    int argc;
    char **argv;
    char chd_err[256];
    int ret;

    argv = cmdline;

    ret = container_exec_inner(pid, argv, chd_err, sizeof(chd_err) - 1);
    if(ret < 0) {
        fprintf(stderr, "Parent error: %s\n", chd_err);
    } else if (ret == 0) {
        fprintf(stderr, "Child error: %s\n", chd_err);
    } else {
        int status;
        waitpid(ret, &status, 0);
        if(!WIFEXITED(status)) {
            fprintf(stderr, "Child error: %s\n", chd_err);
        } else {
            // free(argv);
            return WEXITSTATUS(status);
        }
    }
    // free(argv);
    return 0;
}

int container_kill(int pid) {
    char chd_err[256];
    if (pid <= 0) {
        fprintf(stderr, "Error: Invalid PID '%d'.\n", pid);
        return -1;
    }

    if (kill(pid, SIGKILL) != 0) {
        fprintf(stderr, "Error: Invalid PID '%d'.\n", pid);
        return -1;
    }
    return 0;
}

// ======================== Command wrappers ========================

int goctr_run(int argc, char *argv[]) {
    const char *base_dir = NULL;
    const char *hostname = NULL;
    const char *img_rootfs_dir = NULL;
    const char *volume_opt = NULL;
    const char *volume_src = NULL;
    const char *volume_tgt = NULL;
    const char *netns_path = NULL;
    const char *pid_file_path = NULL;
    const char *log_file_path = NULL;
    int pid;

    for (int i = 0; i < argc; i++) {
        if (strncmp(argv[i], "--netns=", 8) == 0) {
            netns_path = argv[i] + 8; // Extract the namespace path
        } else if (strncmp(argv[i], "--pid-file=", 11) == 0) {
            pid_file_path = argv[i] + 11; // Extract the pid file path
        } else if (strncmp(argv[i], "--volume=", 9) == 0) {
            volume_opt = argv[i] + 9; // volume configuration
            char *colon_pos = strchr(volume_opt, ':');
            if (colon_pos != NULL) {
                *colon_pos = '\0';
                volume_src = volume_opt;
                volume_tgt = colon_pos + 1;
            } else {
                fprintf(stderr, "Invalid volume option format. Expected 'src:tgt'\n");
            }
        } else if (strncmp(argv[i], "-V", 2) == 0) {
            verbose_mode = 1; // verbose mode, print time statistic
        } else if (strncmp(argv[i], "--log-file=", 11) == 0) {
            log_file_path = argv[i] + 11; // Extract the pid file path
            redirect_stdout_stderr(log_file_path);
        } else if (!base_dir) {
            base_dir = argv[i];
        } else if (!hostname) {
            hostname = argv[i];
        } else if (!img_rootfs_dir) {
            img_rootfs_dir = argv[i];
        } else {
            fprintf(stderr, "Error: Too many arguments for 'run' operation.\n");
        }
    }

    verbose_output_ts("run_start_time");
    pid = container_run(
        base_dir, hostname, img_rootfs_dir,
        volume_src, volume_tgt, netns_path);
    if (pid_file_path != NULL) {
        write_pid_to_file(pid_file_path, pid);
    }
    verbose_output_ts("run_total_time");
    return pid;
}

int goctr_exec(int argc, char *argv[]) {
    int status;

    // "exec" requires at least 2 additional arguments
    if (argc < 0) {
        fprintf(stderr, "Error: 'exec' operation requires at least 2 arguments: <pid> <cmdline...>\n");
        return -1;
    }

    // Parse the "pid" argument as an integer
    char *endptr;
    pid_t pid = strtol(argv[0], &endptr, 10);
    if (*endptr != '\0') {
        fprintf(stderr, "Error: 'pid' must be an integer.\n");
        print_usage(argv[0]);
    }

    // Check for a valid "cmdline" array
    char **cmdline = &argv[1];
    int cmdline_len = argc - 1;
    if (cmdline_len == 0) {
        fprintf(stderr, "Error: 'cmdline' cannot be empty.\n");
        return -1;
    }

    fprintf(stderr, "Operation: exec\n");
    fprintf(stderr, "PID: %d\n", pid);
    fprintf(stderr, "Command Line:\n");
    for (int i = 0; i < cmdline_len; i++) {
        fprintf(stderr, "  %s\n", cmdline[i]);
    }

    status = container_exec(pid, cmdline);
    return status;
}

int goctr_kill(int argc, char *argv[]) {
    int ret, pid = 0;
    const char *log_file_path = NULL;

    // "kill" requires 1 additional positional argument
    for (int i = 0; i < argc; i++) {
        if (pid == 0) {
            pid = atoi(argv[i]);
        } else if (strncmp(argv[i], "-V", 2) == 0) {
            verbose_mode = 1; // verbose mode, print time statistic
        } else if (strncmp(argv[i], "--log-file=", 11) == 0) {
            log_file_path = argv[i] + 11; // Extract the pid file path
            redirect_stdout_stderr(log_file_path);
        } else {
            fprintf(stderr, "Error: Too many arguments for 'run' operation %s.\n", argv[i]);
        }
    }
    verbose_output_ts("kill_start_time");
    ret = container_kill(pid);
    verbose_output_ts("kill_total_time");
    
    return ret;
}

// ======================== Main ========================

int main(int argc, char *argv[]) {

    pin_to_cpu(3); // Pin to CPU 3en 1-99
    set_realtime_priority(90); // Priority betwe

    // Check for the minimum required arguments
    if (argc < 2) {
        fprintf(stderr, "Error: Missing mandatory 'op' argument.\n");
        print_usage(argv[0]);
    }

    // Parse the "op" argument
    const char *op = argv[1];

    if (strcmp(op, "run") == 0) {
        goctr_run(argc - 2, argv + 2);
    } else if (strcmp(op, "exec") == 0) {
        goctr_exec(argc - 2, argv + 2);
    } else if (strcmp(op, "kill") == 0) {
        goctr_kill(argc - 2 , argv + 2);
    } else {
        fprintf(stderr, "Error: Invalid 'op' argument. Must be 'run', 'exec', or 'kill'.\n");
        print_usage(argv[0]);
    }

    return EXIT_SUCCESS;
}
