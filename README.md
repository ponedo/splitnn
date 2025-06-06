# Code of SplitNN (APNet '25 Paper)

## Overview
This repository provides code of experiments in our APNet '25 paper--[SplitNN: Single-Machine Network Emulation at Scale with Minute-Level Construction of 10K-Node Virtual Networks]().


SplitNN is a new methodological framework that enables fast construction of large-scale virtual networks (VNs) for network emulation. SplitNN leverages two "splitting" methods on a physical machine to accelerate VN construction:

1. *Multi-VM splitting*: to address the serialization bottleneck, SplitNN creates multiple VMs on a single machine and distributes the VN across them, allowing independent kernel instances to handle vlink operations in parallel.

2. *Multi-netns splitting*: to reduce the notifier chain overhead, SplitNN further distributes vlinks of each sub-VN into multiple backbone network namespaces within each VM, reducing the number of devices a BBNS carries, thereby lowering the device traversal overhead during vlink construction.

With multi-VM splitting and multi-netns splitting architecture, construction of 10K-node VNs can be done within minute-level time-cost.

## Project Structure

The project contains following directories:

1. infra: a Golang project that construct/destruct virtual networks on a slave VM. 

2. driver: a python program run by the master VM that (1) distribute topology infomation and reap VN construction/destruction time-costs from slave VMs; (2) manage experiment workflow.

3. dataproc: a python program that output tables and figures with experimental results (just ignore it if you feel it hard to use).

## Setting up Your VM Cluster

Before running the experiments, please setup a VM cluster including a master VM and some slave VMs (the master can also be a slave). In future we are looking forward to providing an script for setup automation. But currently, please CAREFULLY with following steps to setup your environment:

1. Git clone this repo on all VMs.

2. Configure VM infomation in [driver/server_config.json](driver/server_config.json). Example:

    ```json
    "ipAddr": "10.10.30.144", // IP address of the slave VM
    "user": "cnic",
    "password": "XXXXXXXXXXX",
    "phyIntf": "enp1s0", // The network interface where ipAddr is bounded
    "infraWorkDir": "/home/cnic/split-nn/infra", // The path to the "infra" directory in this project on your VM
    "dockerImageName": "ponedo/bird-ubuntu22", // The image name of vnodes, can be arbitrary image on dockerhub or your own hub
    "kernFuncsToMonitor":  [
        ["setup", "cctr", "chroot_fs_refs"],
        ["setup", "topo_setup_test", "wireless_nlevent_flush"],
        ["setup", "topo_setup_test", "fib6_clean_tree"],
        ["clean", "", "br_vlan_flush"]
    ], // Used for recording kernel function time-cost. Just keep them as are.
    "server_best_bbns_factor": 2.353, // The measured k_opt argument, which influences the number of backbone namespaces when constructing a VN (see "Measuring platform-specific parameters" subsection below and check the paper for more details).
    "phyicalMachineId": 0 // If you're using multiple physical machines, use this ID to indicate which physical machine this VM is on. !!! IMPORTANT !!!: Currently, phsicalMachineId of all VMs should be SAME. To run experiments across multiple machines, the Gurobi optimizer with a license should be installed (Future work).
    ```

3. **(Important)** Setup an SSH key on master VM, and copy the public key to all slave VMs. Since SplitNN is a distributive solution spanning many VMs, this step enables automatic communication between VMs. Once configured SSH keys, please execute the following commnand on master VM for all slave VMs to check whether password-free communication is enabled:

    ```bash
    # When executing this command on the master, an interactive prompt requesting password should NOT come out!
    ssh ${USER}@${SLAVE_VM_IP} 'echo hello'
    ```

4. Pull the docker image configured in server_config.json on all slave VMs.

5. Setup a python virtual enviroment and install python dependencies on the master VM with following commands:
    ```bash
    cd /path/to/repository
    python -m venv tstenv
    source tstenv/bin/activate
    pip install -r requirements.txt
    ```
    Operations on the master VM should be executed in this virtual environment

6. Install dependencies of topology partitioning for multi-VM splitting on the master VM:

    6.1 Install [GKlib](https://github.com/KarypisLab/GKlib):

    ```bash
    git clone https://github.com/KarypisLab/GKlib.git
    cd GKlib
    # For x86 platform
    make config prefix=~/local CONFIG_FLAGS='-D BUILD_SHARED_LIBS=ON'
    # For ARM platform
    make config prefix=~/local CONFIG_FLAGS='-D BUILD_SHARED_LIBS=ON -D NO_X86=1'
    make
    make install
    ```

    6.2 Install [METIS](https://github.com/KarypisLab/METIS):

    ```bash
    git clone https://github.com/KarypisLab/METIS.git
    cd METIS
    sed -i '/add_library(metis ${METIS_LIBRARY_TYPE} ${metis_sources})/ s/$/\ntarget_link_libraries(metis GKlib)/' libmetis/CMakeLists.txt
    sed -i '/^CONFIG_FLAGS \?= / s,$, -DCMAKE_BUILD_RPATH=/usr/local/lib -DCMAKE_INSTALL_RPATH_USE_LINK_PATH=ON,' Makefile
    make config shared=1 cc=gcc prefix=~/local gklib_path=/usr/local
    make install
    echo 'export METIS_DLL=~/local/lib/libmetis.so' >> ~/.bashrc
    source ~/.bashrc
    ```

7. Install dependencies of multi-machine topology partitioning on the master VM:

    7.1 Clone and compile a modified version of [TBR-TBS](https://github.com/ponedo/tbs):
    ```bash
    git clone git@github.com:ponedo/tbs.git
    cd tbs
    mkdir build
    cd build
    cmake .. && make
    ```

    7.2 Set global variable TBS_BIN_DIR in [driver/scripts/partition/partition_topo_pm.py](driver/scripts/partition/partition_topo_pm.py) to the build path of your TBR-TBS repository:
    ```python
    TBS_BIN_DIR = "/path/to/tbs/build"
    ```

    7.3 Install Gurobi optimizer, which is a necessary dependency of [TBR-TBS](https://github.com/tbs2022/tbs) topoology partitioning algorithm. Please install a *full-licensed* Gurobi optimizer (Please find help at [How do I install Gurobi Optimizer?](https://support.gurobi.com/hc/en-us/articles/4534161999889-How-do-I-install-Gurobi-Optimizer)).

## Usage

### Run VN construction/destruction experiements

1. On the master VM (1) change into "driver" directory; (2) switch into "tstenv" python virtual environment.

2. **(Important)** Switch into "rigid" branch (dedicated branch for experiments) of this repository:

    ```bash
    git checkout rigid
    ```

3. Modify the "driver/batch_test.py" script on demand:

    3.1. For uni-BBNS experiments, set USE_BEST_BBNS_NUM to False, and set BBNS number to 1.

    ```python
    SERVER_BBNS_NUM_TEST = False
    USE_BEST_BBNS_NUM = False
    ```

    ```python
    "b": [
        1 # Use only one backbone namespace
    ],
    ```

    3.2. For multi-BBNS experiments: if you want to test VN construction/destruction time-cost under different BBNS number (factors of vlink number), set like below:
    ```python
    SERVER_BBNS_NUM_TEST = True
    USE_BEST_BBNS_NUM = False
    ```

    if you want to test with optimal BBNS number, set like below:
    ```python
    SERVER_BBNS_NUM_TEST = False
    USE_BEST_BBNS_NUM = True
    ```
    
    if you want to test with some specific BBNS number, set like below:
    ```python
    SERVER_BBNS_NUM_TEST = False
    USE_BEST_BBNS_NUM = False
    
    "b": [
        1,
        2,
        4,
        #...
    ],
    ```

    3.3. ***Uncomment*** lines of topologies you want to test, where "grid", "clos", and "as" represents "+Grid", "Fattree", and "BGP AS" topologies in our paper:
    ```python
    # ["grid", "10", "10"],
    # ["grid", "20", "20"],
    # ["grid", "30", "30"],
    # ["grid", "40", "40"],
    # ["grid", "50", "50"],
    # ["grid", "60", "60"],
    # ["grid", "70", "70"],
    # ["grid", "75", "75"],
    # ["grid", "80", "80"],
    # ["grid", "85", "85"],
    # ["grid", "90", "90"],
    # ["grid", "95", "95"],
    # ["grid", "100", "100"],

    # ["clos", "8"],
    # ["clos", "12"],
    # ["clos", "16"],
    # ["clos", "20"],
    # ["clos", "24"],
    # ["clos", "28"],
    # ["clos", "32"],
    
    # ["as", "small"],
    # ["as", "medium"],
    # ["as", "large"],
    ```

4. Run the batch_test.py script:
    ```bash
    cd /path/to/repository
    source tstenv/bin/activate
    cd driver
    python -u batch_test.py > batch_test_log
    ```
    Results will be placed at the directory "driver/raw_results/result-XX-servers", in which VN construction/destruction time will be shown in setup_log.txt/clean_log.txt with "Operation time" entry.

### Measuring platform-specific parameters

1. Prepare code and executable files for measurement:

    ```bash
    cd /path/to/repository
    git checkout measure
    cd infra
    make
    ```

2. Modify infra/server_config. Set only one slave VM (recommend using master VM as the slave for measurement)

3. Execute measurement for parameter *X* (increasing rate of vlink construction time w.r.t. the number of system-wide netns’es):
    ```bash
    bin/topo_setup_test -o node-measure -P 10000 -Q 1250 -S 9 -N cctr -l ntlbr -s server_config.json
    ```
    the results will be written in infra/tmp/node-measure_log.txt.

4. Execute measurement for parameter *Y* (ncreasing rate of per-vlink construction time with respect to the pre-existing vlink number in the BBNS that carries the vlink.):
    ```bash
    bin/topo_setup_test -o link-measure -P 10000 -Q 1250 -S 9 -N cctr -l ntlbr -s server_config.json
    ```
    the results will be written in infra/tmp/link-measure_log.txt.