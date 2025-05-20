package main

import (
	"flag"
	"fmt"
	"log"
	"os"
	"path"
	"runtime"
	"syscall"
	"time"
	"topo_setup_test/algo"
	"topo_setup_test/network"
	"unsafe"

	"golang.org/x/sys/unix"
)

var args struct {
	Operation        string
	BackboneNsNum    int
	Algorithm        string
	Topofile         string
	MntDir           string
	ExecConfigFile   string
	LinkManagerType  string
	NodeManagerType  string
	DisableIpv6      int
	Parallel         int
	ServerConfigFile string
	ServerID         int
	S                int
	P                int
	Q                int
}

func parseArgs() {
	/* Parse arguments */
	// flag.StringVar(
	// 	&args.Operation, "operation", "",
	// 	"Operation [setup|clean|exec|node-measure|link-measure]")
	flag.StringVar(
		&args.Operation, "o", "",
		"Operation [setup|clean|exec|node-measure|link-measure]")
	// flag.IntVar(
	// 	&args.BackboneNsNum, "bb-ns-num", 1,
	// 	"# of backbone network namespaces")
	flag.IntVar(
		&args.BackboneNsNum, "b", 1,
		"# of backbone network namespaces")
	// flag.StringVar(
	// 	&args.Algorithm, "algo", "",
	// 	"Interleave algorithm [naive|degree|dynamic|weighted_dynamic|best_weighted_dynamic]")
	flag.StringVar(
		&args.Algorithm, "a", "naive",
		"Interleave algorithm [naive|degree|dynamic|weighted_dynamic|best_weighted_dynamic]")
	// flag.StringVar(
	// 	&args.Topofile, "topofile", "",
	// 	"Name of topology file")
	flag.StringVar(
		&args.Topofile, "t", "",
		"Name of topology file")
	// flag.StringVar(
	// 	&args.MntDir, "mntdir", "",
	// 	"Path of volumes to be mounted")
	flag.StringVar(
		&args.MntDir, "m", "",
		"Path of volumes to be mounted")
	// flag.StringVar(
	// 	&args.ExecConfigFile, "exec", "",
	// 	"Path of exec_config.json (only useful with \"-o exec\")")
	flag.StringVar(
		&args.ExecConfigFile, "e", "",
		"Path of exec_config.json (only useful with \"-o exec\")")
	// flag.StringVar(
	// 	&args.LinkManagerType, "link-manager", "ntlbr",
	// 	"Type of link manager [ntlbr]")
	flag.StringVar(
		&args.LinkManagerType, "l", "ntlbr",
		"Type of link manager [ntlbr]")
	// flag.StringVar(
	// 	&args.NodeManagerType, "node-mamager", "cctr",
	// 	"Type of node manager [cctr]")
	flag.StringVar(
		&args.NodeManagerType, "N", "cctr",
		"Type of node manager [cctr]")
	// flag.IntVar(
	// 	&args.DisableIpv6, "disable-ipv6", 0,
	// 	"Value of sysctl disable_ipv6")
	flag.IntVar(
		&args.DisableIpv6, "d", 0,
		"Value of sysctl disable_ipv6")
	// flag.IntVar(
	// 	&args.Parallel, "parallel", 0,
	// 	"Whether use parallel link setup")
	flag.IntVar(
		&args.Parallel, "p", 0,
		"Whether use parallel link setup")
	// flag.StringVar(
	// 	&args.ServerConfigFile, "server-file", "server_config.json",
	// 	"Name of server config file")
	flag.StringVar(
		&args.ServerConfigFile, "s", "server_config.json",
		"Name of server config file")
	// flag.IntVar(
	// 	&args.ServerID, "server-id", 0,
	// 	"ID of current server in server-file")
	flag.IntVar(
		&args.ServerID, "i", 0,
		"ID of current server in server-file")

	flag.Parse()

	/* Check whether args are valid */
	if args.Operation == "setup" || args.Operation == "clean" || args.Operation == "exec" {
		if args.Algorithm == "" {
			fmt.Println("Please notify ALGORITHM")
			os.Exit(1)
		}
		if args.Topofile == "" {
			fmt.Println("Please notify TOPOFILE")
			os.Exit(1)
		}
	} else {
		fmt.Printf("Invalid OPERATION %s\n", args.Operation)
		os.Exit(1)
	}

	if args.LinkManagerType == "" {
		fmt.Println("Please notify LINK_MANAGER")
		os.Exit(1)
	}
	if args.NodeManagerType == "" {
		fmt.Println("Please notify NODE_MANAGER")
		os.Exit(1)
	}
}

var logFile *os.File

func redirectOutput(workDir string, operation string) {
	var err error
	logPath := path.Join(workDir, "tmp", operation+"_log.txt")
	logFile, err = os.OpenFile(logPath, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0644)
	if err != nil {
		log.Fatalf("Failed to open file: %v", err)
	}
	os.Stdout = logFile
	os.Stderr = logFile
}

func pinToCPU(cpuID int) error {
	var mask unix.CPUSet
	mask.Zero()     // Clear the CPU set
	mask.Set(cpuID) // Add the desired CPU to the set

	// Apply the CPU affinity to the current thread (PID 0 means current thread)
	err := unix.SchedSetaffinity(0, &mask)
	if err != nil {
		return fmt.Errorf("failed to set CPU affinity: %w", err)
	}
	return nil
}

func setRealtimePriority(pid int, priority int) error {
	const (
		SCHED_FIFO = 1 // Real-time scheduling policy
	)

	// Define the sched_param structure
	param := struct {
		SchedPriority int32
	}{
		SchedPriority: int32(priority),
	}

	// Call sched_setscheduler (syscall)
	_, _, errno := syscall.RawSyscall(syscall.SYS_SCHED_SETSCHEDULER,
		uintptr(pid),                    // Target PID (0 for current process)
		uintptr(SCHED_FIFO),             // Scheduling policy
		uintptr(unsafe.Pointer(&param)), // Pointer to sched_param
	)

	if errno != 0 {
		return fmt.Errorf("sched_setscheduler failed: %v", errno)
	}
	return nil
}

// Manually define constants and types
const (
	SCHED_OTHER = 0 // Scheduling policy for normal processes
)

type SchedParam struct {
	SchedPriority int32
}

// Manually define SchedSetScheduler using syscall
func SchedSetScheduler(pid int, policy int, param *SchedParam) error {
	_, _, errno := syscall.Syscall(syscall.SYS_SCHED_SETSCHEDULER, uintptr(pid), uintptr(policy), uintptr(unsafe.Pointer(param)))
	if errno != 0 {
		return errno
	}
	return nil
}

func SetSchedAndNice(niceValue int) error {
	// Set scheduling policy to SCHED_OTHER
	param := SchedParam{SchedPriority: 0} // Priority is ignored for SCHED_OTHER
	err := SchedSetScheduler(0, SCHED_OTHER, &param)
	if err != nil {
		return fmt.Errorf("sched_setscheduler failed: %v", err)
	}

	// Set the nice value
	err = unix.Setpriority(unix.PRIO_PROCESS, 0, niceValue)
	if err != nil {
		return fmt.Errorf("setpriority failed: %v", err)
	}

	return nil
}

func main() {
	// if err := pinToCPU(0); err != nil {
	// 	log.Fatalf("Error pinning to CPU: %v", err)
	// }
	// if err := setRealtimePriority(0, 85); err != nil {
	// 	log.Fatalf("Error setting real-time priority: %v", err)
	// }
	// if err := SetSchedAndNice(19); err != nil {
	// 	log.Fatalf("Error setting nice priority: %v", err)
	// }

	parseArgs()

	var err error
	var graph *algo.Graph
	var edgeSum, accNodeNum int
	var nodeOrder, curEdgeNumSeq []int
	var edgeOrder [][][4]int
	var linkManager network.LinkManager
	var nodeManager network.NodeManager
	var start, end time.Time

	/* Initialize network-related global variables */
	err = network.ConfigServers(args.ServerConfigFile)
	if err != nil {
		goto clean
	}
	redirectOutput(network.ServerList[args.ServerID].WorkDir, args.Operation)
	err = network.ConfigEnvs(
		args.ServerID, args.Operation,
		args.MntDir, args.ExecConfigFile,
		args.DisableIpv6, args.Parallel)
	if err != nil {
		goto clean
	}
	err = network.StartMonitor(args.ServerID, args.Operation, args.NodeManagerType)
	if err != nil {
		goto clean
	}

	/* Initialize graph file */
	if args.Operation == "setup" || args.Operation == "clean" {
		graph, err = algo.ReadGraphFromFile(args.Topofile)
		if err != nil {
			fmt.Printf("Error reading graph: %v\n", err)
			return
		}

		/* Compute interleaving node/link setup order */
		start = time.Now()
		switch args.Algorithm {
		case "naive":
			nodeOrder, edgeOrder, curEdgeNumSeq = graph.NaiveOrder()
		case "degree":
			nodeOrder, edgeOrder, curEdgeNumSeq = graph.MaximizeEdgesOrderDegree()
		case "dynamic":
			nodeOrder, edgeOrder, curEdgeNumSeq = graph.MaximizeEdgesOrderDynamic()
		case "weighted_dynamic":
			nodeOrder, edgeOrder, curEdgeNumSeq = graph.MaximizeEdgesOrderWeightedDynamic()
		case "best_weighted_dynamic":
			nodeOrder, edgeOrder, curEdgeNumSeq = graph.MaximizeEdgesOrderBestWeightedDynamic()
		default:
			fmt.Printf("Invalid network algorithm: %v.\n", args.Algorithm)
			return
		}
		if args.Operation == "clean" {
			// Reverse the order slices along the first dimension
			left, right := 0, len(nodeOrder)-1
			for left < right {
				nodeOrder[left], nodeOrder[right] = nodeOrder[right], nodeOrder[left]
				edgeOrder[left], edgeOrder[right] = edgeOrder[right], edgeOrder[left]
				left++
				right--
			}
		}

		/* Calculate accumulation of nodes */
		accNodeNum = 0
		for nodeNum := range curEdgeNumSeq {
			if nodeNum == 0 {
				continue
			}
			accNodeNum += nodeNum * (curEdgeNumSeq[nodeNum] - curEdgeNumSeq[nodeNum-1])
		}
		fmt.Println("Node Order:", nodeOrder)
		fmt.Println("Edge Order:", edgeOrder)
		fmt.Println("curEdgeNumSeq:", curEdgeNumSeq)
		fmt.Println("accNodeNum:", accNodeNum)
		end = time.Now()
		fmt.Printf("Plan time: %.2fs\n", end.Sub(start).Seconds())
		edgeSum = 0
		for _, edgeOrderElement := range edgeOrder {
			edgeSum += len(edgeOrderElement)
		}
		fmt.Println("edgeSum:", edgeSum)
	}

	/* Prepare link and node managers */
	switch args.LinkManagerType {
	case "ntlbr":
		linkManager = &network.NtlBrLinkManager{}
	default:
		fmt.Printf("Invalid link manager: %v.\n", args.LinkManagerType)
		return
	}
	switch args.NodeManagerType {
	case "cctr":
		nodeManager = &network.CctrNodeManager{}
	case "goctr":
		nodeManager = &network.GoctrNodeManager{}
	default:
		fmt.Printf("Invalid node manager: %v.\n", args.NodeManagerType)
		return
	}

	/* Execute operation */
	runtime.LockOSThread()
	defer runtime.UnlockOSThread()

	start = time.Now()
	switch args.Operation {
	case "setup":
		err = network.NetworkSetup(
			linkManager, nodeManager,
			graph, nodeOrder, edgeOrder,
			args.BackboneNsNum)
	case "clean":
		err = network.NetworkClean(
			linkManager, nodeManager,
			graph, nodeOrder, edgeOrder,
			args.BackboneNsNum)
	case "exec":
		err = network.NetworkExec(
			linkManager, nodeManager)
	}
	if err != nil {
		fmt.Printf("Error: %v.\n", err)
	}
	end = time.Now()
	fmt.Printf("Network operation time: %.2fs\n", end.Sub(start).Seconds())

	/* Archive node runtime logs */
	err = network.ArchiveCtrLog(args.Operation,
		graph, nodeOrder, edgeOrder)
	if err != nil {
		fmt.Printf("ArchiveLog error: %v.\n", err)
	}

clean:
	/* Clean env */
	network.StopMonitor(args.Operation)
	network.CleanEnvs(args.Operation)
	logFile.Close()
}
