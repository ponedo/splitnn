package network

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"os"
	"os/exec"
	"path"
	"strings"
	"syscall"
	"time"
	"topo_setup_test/algo"

	"github.com/vishvananda/netlink"
)

type Server struct {
	IPAddr             string     `json:"ipAddr"`
	WorkDir            string     `json:"infraWorkDir"`
	PhyIntf            string     `json:"phyIntf"`
	DockerImageName    string     `json:"dockerImageName"`
	KernFuncsToMonitor [][]string `json:"kernFuncsToMonitor"`
}

type Servers struct {
	Servers []Server `json:"servers"`
}

var (
	Operation               string
	ServerList              []Server
	LocalPhyIntf            string
	LocalPhyIntfNl          netlink.Link
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

func ConfigEnvs(serverID int, operation string, disableIpv6 int, parallel int) error {
	server := ServerList[serverID]
	Operation = operation
	setLocalPhyIntf(server.PhyIntf)
	setEnvPaths(server.WorkDir, server.DockerImageName)
	setDisableIpv6(disableIpv6)
	setParallel(parallel)
	setKernelPtySysctl()
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

func setDisableIpv6(disableIpv6 int) {
	DisableIpv6 = disableIpv6
}

func setParallel(parallel int) {
	Parallel = parallel
}

func setSysctlValue(path string, value string) error {
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

	// Desired values
	newMaxValue := "262144"
	newReserveValue := "65536"

	if err := setSysctlValue(ptyMaxPath, newMaxValue); err != nil {
		log.Fatalf("Error setting kernel.pty.max: %v", err)
	} else {
		fmt.Printf("Successfully set kernel.pty.max to %s\n", newMaxValue)
	}

	// Modify kernel.pty.reserve
	if err := setSysctlValue(ptyReservePath, newReserveValue); err != nil {
		log.Fatalf("Error setting kernel.pty.reserve: %v", err)
	} else {
		fmt.Printf("Successfully set kernel.pty.reserve to %s\n", newReserveValue)
	}
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
