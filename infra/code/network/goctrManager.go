package network

/*
#cgo CFLAGS: -g -O2
#include <stdlib.h>

int goctr_run(int argc, char *argv[]);
int goctr_exec(int argc, char *argv[]);
int goctr_kill(int argc, char *argv[]);
*/
import "C"

import (
	"bufio"
	"fmt"
	"os"
	"path"
	"strconv"
	"time"
	"unsafe"

	"github.com/vishvananda/netns"
)

type GoctrNodeManager struct {
	nodeTmpDir string
	nodeId2Pid map[int]int
}

func (nm *GoctrNodeManager) Init() error {
	nm.nodeId2Pid = make(map[int]int)
	var err error
	nm.nodeTmpDir = path.Join(TmpDir, "nodes")
	if Operation == "setup" {
		err = os.RemoveAll(nm.nodeTmpDir)
		if err != nil {
			fmt.Printf("Error RemoveAll: %s\n", err)
			return err
		}
	}
	err = os.MkdirAll(nm.nodeTmpDir, os.ModePerm)
	if err != nil {
		fmt.Printf("Error MkdirAll: %s\n", err)
		return err
	}
	return nil
}

func writeIntToFile(filePath string, number int) error {
	// Create the file, or open it if it exists, with write-only permissions and create if not exist
	file, err := os.Create(filePath)
	if err != nil {
		return fmt.Errorf("error creating or opening file: %v", err)
	}
	defer file.Close()

	// Write the integer to the file
	_, err = fmt.Fprintf(file, "%d", number)
	if err != nil {
		return fmt.Errorf("error writing to file: %v", err)
	}

	return nil
}

func (nm *GoctrNodeManager) Delete() error {
	for nodeId, pid := range nm.nodeId2Pid {
		nodeName := "node" + strconv.Itoa(nodeId)
		baseDir := path.Join(nm.nodeTmpDir, nodeName)
		pidFilePath := path.Join(baseDir, "pid.txt")
		writeIntToFile(pidFilePath, pid)
	}
	time.Sleep(5 * time.Second)
	return nil
}

func (nm *GoctrNodeManager) SetupNode(nodeId int) error {
	var pid int

	nodeName := "node" + strconv.Itoa(nodeId)
	baseDir := path.Join(nm.nodeTmpDir, nodeName)
	err := os.MkdirAll(baseDir, os.ModePerm)
	if err != nil {
		fmt.Printf("Error MkdirAll: %s\n", err)
		return err
	}
	hostName := nodeName
	pidFilePath := path.Join(baseDir, "pid.txt")
	pidFileArg := "--pid-file=" + pidFilePath
	runLogFilePath := path.Join(baseDir, "run.log")
	logFileArg := "--log-file=" + runLogFilePath

	/* Make c function arguments */
	args := []string{baseDir, hostName, ImageRootfsPath, pidFileArg, "-v", logFileArg}
	// args := []string{baseDir, hostName, ImageRootfsPath}
	cArgs := make([]*C.char, len(args))
	for i, arg := range args {
		cArgs[i] = C.CString(arg)
		defer C.free(unsafe.Pointer(cArgs[i])) // Free memory after usage
	}
	argc := C.int(len(cArgs))

	// Setup operation
	cPid := C.goctr_run(argc, &cArgs[0])
	pid = int(cPid)
	if pid < 0 {
		return fmt.Errorf("goctr_run for node %d failed", nodeId)
	}

	// Cache pid of the node
	nm.nodeId2Pid[nodeId] = pid

	return nil
}

func (nm *GoctrNodeManager) GetNodeNetNs(nodeId int) (netns.NsHandle, error) {
	var ok bool
	var pid int
	var err error
	var nodeNetns netns.NsHandle

	pid, ok = nm.nodeId2Pid[nodeId]
	if !ok {
		return nodeNetns, fmt.Errorf("trying to get a non-exist netns (node #%d)", nodeId)
	}
	nodeNetns, err = netns.GetFromPid(pid)
	if err != nil {
		return -1, err
	}
	return nodeNetns, nil
}

func (nm *GoctrNodeManager) CleanNode(nodeId int) error {
	nodeName := "node" + strconv.Itoa(nodeId)
	baseDir := path.Join(nm.nodeTmpDir, nodeName)

	// Get pid
	pid, err := nm.getNodePid(nodeId)
	if err != nil {
		return err
	}

	// Create the kill log file
	killLogFilePath := path.Join(baseDir, "kill.log")
	logFileArg := "--log-file=" + killLogFilePath

	/* Make c function arguments */
	args := []string{strconv.Itoa(pid), "-v", logFileArg}
	cArgs := make([]*C.char, len(args))
	for i, arg := range args {
		cArgs[i] = C.CString(arg)
		defer C.free(unsafe.Pointer(cArgs[i])) // Free memory after usage
	}
	argc := C.int(len(cArgs))

	// Kill operation
	cRet := C.goctr_kill(argc, &cArgs[0])
	ret := int(cRet)
	if ret < 0 {
		return fmt.Errorf("goctr_kill for node %d failed", nodeId)
	}

	return nil
}

func (nm *GoctrNodeManager) NodeExec(nodeId int, args []string) error {
	pid, err := nm.getNodePid(nodeId)
	if err != nil {
		return err
	}

	execArgs := append([]string{"exec", strconv.Itoa(pid)}, args...)
	cArgs := make([]*C.char, len(execArgs))
	for i, arg := range execArgs {
		cArgs[i] = C.CString(arg)
		defer C.free(unsafe.Pointer(cArgs[i])) // Free memory after usage
	}
	argc := C.int(len(execArgs))
	cRet := C.goctr_kill(argc, &cArgs[0])
	ret := int(cRet)
	if ret < 0 {
		return fmt.Errorf("goctr_exec for node %d failed", nodeId)
	}

	return nil
}

func (nm *GoctrNodeManager) getNodePid(nodeId int) (int, error) {
	pid := -1

	nodeName := "node" + strconv.Itoa(nodeId)
	baseDir := path.Join(nm.nodeTmpDir, nodeName)
	pidFilePath := path.Join(baseDir, "pid.txt")
	pidFile, err := os.Open(pidFilePath)
	if err != nil {
		fmt.Printf("Error opening file: %s\n", err)
		return -1, err
	}
	defer pidFile.Close() // Ensure the file is closed after reading

	// Create a scanner to read the file line by line
	scanner := bufio.NewScanner(pidFile)
	if scanner.Scan() {
		line := scanner.Text()
		pid, err = strconv.Atoi(line)
		if err != nil {
			fmt.Printf("Error parsing pid: %s\n", err)
			return -1, err
		}
	} else {
		fmt.Printf("Error reading pid file: %s\n", scanner.Err())
		return -1, err
	}

	return pid, nil
}
