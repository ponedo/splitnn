package network

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"os"
	"os/exec"
	"path"
	"strconv"
	"strings"
	"syscall"
	"time"
	"topo_setup_test/algo"

	"github.com/vishvananda/netlink"
	"golang.org/x/sys/unix"
)

type Servers struct {
	Servers []Server `json:"servers"`
}

type Server struct {
	IPAddr             string     `json:"ipAddr"`
	WorkDir            string     `json:"infraWorkDir"`
	PhyIntf            string     `json:"phyIntf"`
	DockerImageName    string     `json:"dockerImageName"`
	KernFuncsToMonitor [][]string `json:"kernFuncsToMonitor"`
}

type Mnts struct {
	Mnts []Mnt `json:"mnts"`
}

type Mnt struct {
	NodeId    int    `json:"node_id"`
	VolumeOpt string `json:"volume_opt"`
}

type ExecEntries struct {
	Execs []ExecEntry `json:"exec_entries"`
}

type ExecEntry struct {
	NodeId int  `json:"node_id"`
	Ops    []Op `json:"ops"`
}

type Op struct {
	Op   string   `json:"op"`
	Args []string `json:"args"`
}

var (
	Operation               string
	ServerList              []Server
	VolumeOptMap            map[int]string
	LocalPhyIntf            string
	LocalPhyIntfNl          netlink.Link
	Execs                   ExecEntries
	WorkDir                 string
	TmpDir                  string
	BinDir                  string
	CctrBinPath             string
	CtrLogPath              string
	LinkLogPath             string
	LinkLogFile             *os.File
	KernFuncToolRelPath     string
	KernFuncLogDir          string
	CctrMonitorScriptPath   string
	CctrMonitorOutputPath   string
	CpuMemMonitorScriptPath string
	CpuMemMonitorOutputDir  string
	MonitorCmds             []*exec.Cmd
	ImageRootfsPath         string
	Parallel                int
	DisableIpv6             int
)

func ConfigServers(confFileName string) error {
	// Read the JSON file
	jsonFile, err := os.ReadFile(confFileName)
	if err != nil {
		log.Fatalf("Error reading the JSON file: %v", err)
	}

	var serversData Servers

	// Parse JSON into the struct
	err = json.Unmarshal(jsonFile, &serversData)
	if err != nil {
		return fmt.Errorf("error parsing JSON: %v", err)
	}

	// Assign the parsed data to the global slice
	ServerList = serversData.Servers
	return nil
}

func ConfigEnvs(
	serverID int, operation string,
	mntDir string, execConfigFile string,
	disableIpv6 int, parallel int) error {
	server := ServerList[serverID]
	Operation = operation
	setLocalPhyIntf(server.PhyIntf)
	setEnvPaths(server.WorkDir, server.DockerImageName)
	setMntConfig(mntDir)
	setExecEntries(execConfigFile)
	setDisableIpv6(disableIpv6)
	setParallel(parallel)
	setKernelPtySysctl()
	setRlimits()
	prepareRootfs(server.DockerImageName)
	return nil
}

func CleanEnvs(operation string) {
}

func StartMonitor(serverID int, operation string, nmManagerType string) error {
	var err error

	/* Open link setup log */
	if operation == "setup" {
		openLinkLog()
	}

	/* Start monitoring kernel functions */
	kernFuncs := ServerList[serverID].KernFuncsToMonitor
	for _, funcEntry := range kernFuncs {
		err = startMonitorKernFunc(funcEntry, operation)
		if err != nil {
			return err
		}
	}

	/* Start monitoring cctr */
	if operation == "setup" && nmManagerType == "cctr" {
		err = startMonitorCctr()
		if err != nil {
			return err
		}
	}

	/* Monitor CPU MEM usage */
	err = startMonitorCpuMem(operation)
	if err != nil {
		return err
	}

	time.Sleep(2 * time.Second)

	return nil
}

func StopMonitor(operation string) {
	/* Close link setup log */
	if operation == "setup" {
		closeLinkLog()
	}

	/* stop monitorcmd */
	for _, monitorCmd := range MonitorCmds {
		if monitorCmd != nil && monitorCmd.Process != nil {
			fmt.Printf("Stopping bpftrace script with PID %d\n", monitorCmd.Process.Pid)
			if err := monitorCmd.Process.Signal(syscall.SIGTERM); err != nil {
				fmt.Printf("Error stopping process %d: %v\n", monitorCmd.Process.Pid, err)
			}
			monitorCmd.Wait() // Wait for the process to terminate
		}
	}
}

func ArchiveCtrLog(operation string,
	g *algo.Graph, nodeOrder []int, edgeOrder [][][4]int) error {
	// var srcLogName string
	var err error
	archiveDirPath := CtrLogPath

	// if operation == "setup" {
	// 	srcLogName = "run.log"
	// 	err = os.RemoveAll(archiveDirPath)
	// 	if err != nil {
	// 		fmt.Printf("Error RemoveAll: %s\n", err)
	// 		return err
	// 	}
	// } else if operation == "clean" {
	// 	srcLogName = "kill.log"
	// } else {
	// 	return fmt.Errorf("invalid operation %s", operation)
	// }

	/* Create node log archive dir */
	err = os.MkdirAll(archiveDirPath, os.ModePerm)
	if err != nil {
		fmt.Printf("Error MkdirAll: %s\n", err)
		return err
	}

	// /* Copy all log */
	// tmpTime := time.Now()
	// nodeNum := g.GetNodeNum()
	// reportTime := 10
	// nodePerReport := nodeNum / reportTime
	// for i, nodeId := range nodeOrder {
	// 	/* Progress reporter */
	// 	if nodePerReport > 0 && i%nodePerReport == 0 {
	// 		progress := 100 * i / nodeNum
	// 		curTime := time.Now()
	// 		fmt.Printf("%d%% nodes' log are archived, time elapsed from last report: %dms\n", progress, curTime.Sub(tmpTime).Milliseconds())
	// 		tmpTime = time.Now()
	// 	}

	// 	/* Copy log */
	// 	nodeTmpDir := path.Join(TmpDir, "nodes")
	// 	nodeBaseDirPath := "node" + strconv.Itoa(nodeId)
	// 	dstLogName := srcLogName + "." + strconv.Itoa(i)
	// 	srcLogPath := path.Join(nodeTmpDir, nodeBaseDirPath, srcLogName)
	// 	dstLogPath := path.Join(archiveDirPath, dstLogName)
	// 	err = copyFile(srcLogPath, dstLogPath)
	// 	if err != nil {
	// 		fmt.Printf("Error copyFile: %s\n", err)
	// 		return err
	// 	}
	// }

	return nil
}

func setLocalPhyIntf(value string) {
	LocalPhyIntf = value
	LocalPhyIntfNl, _ = netlink.LinkByName(LocalPhyIntf)
}

func setEnvPaths(workDir string, dockerImageName string) {
	WorkDir = workDir
	TmpDir = path.Join(WorkDir, "tmp")
	BinDir = path.Join(WorkDir, "bin")
	CctrBinPath = path.Join(BinDir, "cctr")
	CtrLogPath = path.Join(TmpDir, "ctr_log")
	LinkLogPath = path.Join(TmpDir, "link_log.txt")
	KernFuncToolRelPath = path.Join(WorkDir, "scripts", "monitor_kern_func.sh")
	KernFuncLogDir = path.Join(TmpDir, "kern_func")
	CctrMonitorScriptPath = path.Join(WorkDir, "scripts", "monitor_cctr_time.sh")
	CctrMonitorOutputPath = path.Join(TmpDir, "cctr_time.txt")
	CpuMemMonitorScriptPath = path.Join(WorkDir, "scripts", "monitor_cpu_mem_usage.py")
	CpuMemMonitorOutputDir = TmpDir

	splitedImageName := strings.Split(dockerImageName, ":")
	ImageRepo := splitedImageName[0]
	ImageTag := "latest"
	if len(splitedImageName) > 1 {
		ImageTag = splitedImageName[1]
	}
	ImageRootfsPath = path.Join(TmpDir, "img_bundles", ImageRepo, ImageTag, "rootfs")
}

func setMntConfig(mntDir string) error {
	VolumeOptMap = make(map[int]string)
	if mntDir == "" {
		return nil
	}

	mntConfFileName := path.Join(mntDir, "mnt_config.json")

	// Read the JSON file
	jsonFile, err := os.ReadFile(mntConfFileName)
	if err != nil {
		log.Fatalf("Error reading the JSON file: %v", err)
	}

	var mntConfig Mnts

	// Parse JSON into the struct
	err = json.Unmarshal(jsonFile, &mntConfig)
	if err != nil {
		return fmt.Errorf("error parsing JSON: %v", err)
	}

	// Register volume info
	for _, mnt := range mntConfig.Mnts {
		nodeId := mnt.NodeId
		splitedVolumeOpt := strings.Split(mnt.VolumeOpt, ":")
		srcDir := splitedVolumeOpt[0]
		dstDir := splitedVolumeOpt[1]
		srcDir = path.Join(mntDir, "node"+strconv.Itoa(nodeId), srcDir)
		newVolumeOpt := srcDir + ":" + dstDir
		VolumeOptMap[mnt.NodeId] = newVolumeOpt
	}
	return nil
}

func setExecEntries(execConfigFile string) error {
	if execConfigFile == "" {
		return nil
	}

	// Read the JSON file
	jsonFile, err := os.ReadFile(execConfigFile)
	if err != nil {
		log.Fatalf("Error reading the JSON file: %v", err)
	}

	// Parse JSON into the struct
	err = json.Unmarshal(jsonFile, &Execs)
	if err != nil {
		return fmt.Errorf("error parsing JSON: %v", err)
	}

	return nil
}

func setDisableIpv6(disableIpv6 int) {
	DisableIpv6 = disableIpv6
}

func setParallel(parallel int) {
	Parallel = parallel
}

func SetSysctlValue(path string, value string) error {
	file, err := os.OpenFile(path, os.O_WRONLY, 0644)
	if err != nil {
		return fmt.Errorf("failed to open file %s: %w", path, err)
	}
	defer file.Close()

	_, err = file.WriteString(value)
	if err != nil {
		return fmt.Errorf("failed to write value to file %s: %w", path, err)
	}

	return nil
}

func setKernelPtySysctl() {
	ptyMaxPath := "/proc/sys/kernel/pty/max"
	ptyReservePath := "/proc/sys/kernel/pty/reserve"
	maxUserInstancesPath := "/proc/sys/fs/inotify/max_user_instances"
	neighGcThresh1Path := "/proc/sys/net/ipv6/neigh/default/gc_thresh1"
	neighGcThresh2Path := "/proc/sys/net/ipv6/neigh/default/gc_thresh2"
	neighGcThresh3Path := "/proc/sys/net/ipv6/neigh/default/gc_thresh3"
	ipv6RouteMaxSizePath := "/proc/sys/net/ipv6/route/max_size"
	ipv6RouteGcThreshPath := "/proc/sys/net/ipv6/route/gc_thresh"
	ipv4HopLimitPath := "/proc/sys/net/ipv4/ip_default_ttl"
	ipv6HopLimitPath := "/proc/sys/net/ipv6/conf/all/hop_limit"
	netdevMaxBacklogPath := "/proc/sys/net/core/netdev_max_backlog"
	soMaxConnPath := "/proc/sys/net/core/somaxconn"
	rmemMaxPath := "/proc/sys/net/core/rmem_max"

	// Desired values
	newMaxValue := "262144"
	newReserveValue := "65536"
	newMaxUserInstanceValue := "65536"
	// newNeighGcThresh1Value := "262144"
	// newNeighGcThresh2Value := "524288"
	// newNeighGcThresh3Value := "1048576"
	newNeighGcThresh1Value := "128"
	newNeighGcThresh2Value := "512"
	newNeighGcThresh3Value := "1024"
	newIpv6RouteMaxSizeValue := "2147483647"
	// newIpv6RouteGcThreshValue := "33554432"
	newIpv6RouteGcThreshValue := "1024"
	newipv4HopLimitValue := "255"
	newipv6HopLimitValue := "255"
	netdevMaxBacklogValue := "2000"
	soMaxConnValue := "8192"
	rmemMaxValue := "425984"

	if err := SetSysctlValue(ptyMaxPath, newMaxValue); err != nil {
		log.Fatalf("Error setting kernel.pty.max: %v", err)
	} else {
		fmt.Printf("Successfully set kernel.pty.max to %s\n", newMaxValue)
	}
	if err := SetSysctlValue(ptyReservePath, newReserveValue); err != nil {
		log.Fatalf("Error setting kernel.pty.reserve: %v", err)
	} else {
		fmt.Printf("Successfully set kernel.pty.reserve to %s\n", newReserveValue)
	}
	if err := SetSysctlValue(maxUserInstancesPath, newMaxUserInstanceValue); err != nil {
		log.Fatalf("Error setting fs.inotify.max_user_instances: %v", err)
	} else {
		fmt.Printf("Successfully set fs.inotify.max_user_instances to %s\n", newMaxUserInstanceValue)
	}
	if err := SetSysctlValue(neighGcThresh1Path, newNeighGcThresh1Value); err != nil {
		log.Fatalf("Error setting net.ipv4.neigh.default.gc_thresh1: %v", err)
	} else {
		fmt.Printf("Successfully set net.ipv4.neigh.default.gc_thresh1 to %s\n", newNeighGcThresh1Value)
	}
	if err := SetSysctlValue(neighGcThresh2Path, newNeighGcThresh2Value); err != nil {
		log.Fatalf("Error setting net.ipv4.neigh.default.gc_thresh2: %v", err)
	} else {
		fmt.Printf("Successfully set net.ipv4.neigh.default.gc_thresh2 to %s\n", newNeighGcThresh2Value)
	}
	if err := SetSysctlValue(neighGcThresh3Path, newNeighGcThresh3Value); err != nil {
		log.Fatalf("Error setting net.ipv4.neigh.default.gc_thresh3: %v", err)
	} else {
		fmt.Printf("Successfully set net.ipv4.neigh.default.gc_thresh3 to %s\n", newNeighGcThresh3Value)
	}
	if err := SetSysctlValue(ipv6RouteMaxSizePath, newIpv6RouteMaxSizeValue); err != nil {
		log.Fatalf("Error setting net.ipv6.route.max_size: %v", err)
	} else {
		fmt.Printf("Successfully set net.ipv6.route.max_size to %s\n", newIpv6RouteMaxSizeValue)
	}
	if err := SetSysctlValue(ipv6RouteGcThreshPath, newIpv6RouteGcThreshValue); err != nil {
		log.Fatalf("Error setting net.ipv6.route.gc_thresh: %v", err)
	} else {
		fmt.Printf("Successfully set net.ipv6.route.gc_thresh to %s\n", newIpv6RouteGcThreshValue)
	}
	if err := SetSysctlValue(ipv4HopLimitPath, newipv4HopLimitValue); err != nil {
		log.Fatalf("Error setting net.ipv6.route.gc_thresh: %v", err)
	} else {
		fmt.Printf("Successfully set net.ipv6.route.gc_thresh to %s\n", newipv4HopLimitValue)
	}
	if err := SetSysctlValue(ipv6HopLimitPath, newipv6HopLimitValue); err != nil {
		log.Fatalf("Error setting net.ipv6.route.gc_thresh: %v", err)
	} else {
		fmt.Printf("Successfully set net.ipv6.route.gc_thresh to %s\n", newipv6HopLimitValue)
	}
	if err := SetSysctlValue(netdevMaxBacklogPath, netdevMaxBacklogValue); err != nil {
		log.Fatalf("Error setting net.core.netdev_max_backlog: %v", err)
	} else {
		fmt.Printf("Successfully set net.core.netdev_max_backlog to %s\n", netdevMaxBacklogValue)
	}
	if err := SetSysctlValue(soMaxConnPath, soMaxConnValue); err != nil {
		log.Fatalf("Error setting net.core.somaxconn: %v", err)
	} else {
		fmt.Printf("Successfully set net.core.somaxconn to %s\n", soMaxConnValue)
	}
	if err := SetSysctlValue(rmemMaxPath, rmemMaxValue); err != nil {
		log.Fatalf("Error setting net.core.rmem_max: %v", err)
	} else {
		fmt.Printf("Successfully set net.core.rmem_max to %s\n", rmemMaxValue)
	}
}

func setRlimit(resource int, name string) {
	limit := &unix.Rlimit{
		Cur: unix.RLIM_INFINITY,
		Max: unix.RLIM_INFINITY,
	}
	if err := unix.Setrlimit(resource, limit); err != nil {
		log.Fatalf("Failed to set %s: %v", name, err)
	}
	fmt.Printf("Set %s to unlimited\n", name)
}

func setRlimits() {
	var rlim unix.Rlimit
	_ = unix.Getrlimit(unix.RLIMIT_MEMLOCK, &rlim)
	fmt.Printf("Before rlimit setting: RLIMIT_MEMLOCK = Cur=%d Max=%d\n", rlim.Cur, rlim.Max)

	setRlimit(unix.RLIMIT_MEMLOCK, "RLIMIT_MEMLOCK") // ulimit -l
	setRlimit(unix.RLIMIT_DATA, "RLIMIT_DATA")       // ulimit -m

	_ = unix.Getrlimit(unix.RLIMIT_MEMLOCK, &rlim)
	fmt.Printf("After rlimit setting: RLIMIT_MEMLOCK = Cur=%d Max=%d\n", rlim.Cur, rlim.Max)
}

func prepareRootfs(dockerImageName string) {
	splitedImageName := strings.Split(dockerImageName, ":")
	ImageRepo := splitedImageName[0]
	ImageTag := "latest"
	if len(splitedImageName) > 1 {
		ImageTag = splitedImageName[1]
	}
	dockerImageName = ImageRepo + ":" + ImageTag

	prepareScriptPath := path.Join(WorkDir, "scripts", "prepare_rootfs.sh")
	fmt.Printf("prepareScriptPath: %s\n", prepareScriptPath)
	fmt.Printf("dockerImageName: %s\n", dockerImageName)
	prepareCommand := exec.Command(
		"bash", prepareScriptPath, dockerImageName)
	prepareCommand.Run()
}

func openLinkLog() error {
	var err error
	LinkLogFile, err = os.OpenFile(LinkLogPath, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, 0644)
	if err != nil {
		LinkLogFile.Close()
		return fmt.Errorf("failed to open link log file: %v", err)
	}
	return nil
}

func closeLinkLog() {
	LinkLogFile.Close()
}

func copyFile(src, dst string) error {
	sourceFile, err := os.Open(src)
	if err != nil {
		return fmt.Errorf("error opening source file: %w", err)
	}
	defer sourceFile.Close()

	destinationFile, err := os.Create(dst)
	if err != nil {
		return fmt.Errorf("error creating destination file: %w", err)
	}
	defer destinationFile.Close()

	_, err = io.Copy(destinationFile, sourceFile)
	if err != nil {
		return fmt.Errorf("error copying file contents: %w", err)
	}

	err = destinationFile.Sync()
	if err != nil {
		return fmt.Errorf("error syncing destination file: %w", err)
	}

	return nil
}

func startMonitorKernFunc(funcEntry []string, operation string) error {
	op := funcEntry[0]
	if op != operation {
		return nil
	}
	comm := funcEntry[1]
	kernFunc := funcEntry[2]
	outputFileName := fmt.Sprintf("%s--%s.txt", comm, kernFunc)
	outputFilePath := path.Join(KernFuncLogDir, outputFileName)
	monitorCmd := exec.Command(KernFuncToolRelPath, comm, kernFunc, outputFilePath)

	//start monitorcmd
	if err := monitorCmd.Start(); err != nil {
		return fmt.Errorf("error starting bpftrace: %v", err)
	}
	fmt.Printf("Started kernel function monitoring with PID %d\n", monitorCmd.Process.Pid)

	MonitorCmds = append(MonitorCmds, monitorCmd)
	return nil
}

func startMonitorCctr() error {
	monitorCmd := exec.Command(CctrMonitorScriptPath, CctrMonitorOutputPath)
	if err := monitorCmd.Start(); err != nil {
		return fmt.Errorf("error starting bpftrace: %v", err)
	}
	fmt.Printf("Started cctr monitoring with PID %d\n", monitorCmd.Process.Pid)

	MonitorCmds = append(MonitorCmds, monitorCmd)
	return nil
}

func startMonitorCpuMem(operation string) error {
	CpuMemMonitorOutputPath := path.Join(CpuMemMonitorOutputDir, operation+"_cpu_mem_usage.txt")
	monitorCmd := exec.Command(
		"python3", "-u", CpuMemMonitorScriptPath, CpuMemMonitorOutputPath)
	if err := monitorCmd.Start(); err != nil {
		return fmt.Errorf("error starting bpftrace: %v", err)
	}
	fmt.Printf("Started cctr monitoring with PID %d\n", monitorCmd.Process.Pid)

	MonitorCmds = append(MonitorCmds, monitorCmd)
	return nil
}
