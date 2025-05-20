package network

import (
	"fmt"
	"net"
	"strconv"
	"strings"
	"time"

	"github.com/vishvananda/netlink"
	"github.com/vishvananda/netns"
)

func NetworkExec(lm LinkManager, nm NodeManager) error {
	var err error

	nm.Init()
	lm.Init(nm)

	reportTime := 100
	execNum := len(Execs.Execs)
	execTmpTime := time.Now()
	execPerReport := execNum / reportTime
	fmt.Printf("NetworkExec\n")
	for i, execEntry := range Execs.Execs {

		/* Progress reporter */
		if execPerReport > 0 && i%execPerReport == 0 {
			progress := 100 * i / execNum
			curTime := time.Now()
			fmt.Printf("%d%% entries executed, time elapsed from last report: %dms\n",
				progress, curTime.Sub(execTmpTime).Milliseconds())
			execTmpTime = time.Now()
		}

		nodeId := execEntry.NodeId
		for _, op := range execEntry.Ops {
			// fmt.Printf("OP: %v\n", op)
			opType := op.Op
			opArgs := op.Args
			if opType == "set_netsysctl" {
				setNetSysctl(nm, nodeId, opArgs[0], opArgs[1])
			} else if opType == "linkup" {
				err = linkUp(nm, nodeId, opArgs[0])
				if err != nil {
					return err
				}
			} else if opType == "ipaddr" {
				err = setIPAddrInNode(nm, nodeId, opArgs[0], opArgs[1])
				if err != nil {
					return err
				}
			} else if opType == "cmd" {
				nm.NodeExec(nodeId, opArgs)
			}
		}
	}

	lm.Delete()
	nm.Delete()

	return nil
}

func setIPAddrInNode(nm NodeManager, nodeId int, ipaddrStr string, devName string) error {
	var err error
	var origNs, nodeNetns netns.NsHandle

	origNs, err = netns.Get()
	if err != nil {
		fmt.Printf("failed to netns.Get of origNs: %s\n", err)
		return err
	}
	defer netns.Set(origNs)

	// Switch into node's netns
	nodeNetns, err = nm.GetNodeNetNs(nodeId)
	if err != nil {
		return err
	}
	err = netns.Set(nodeNetns)
	if err != nil {
		return fmt.Errorf("failed to netns.Set: %s", err)
	}

	// Set ip address
	parts := strings.Split(ipaddrStr, "/")
	if len(parts) != 2 {
		fmt.Printf("Invalid IPv6 address format. Expected X::Y/Z.")
	}
	address := parts[0]
	prefixLength := parts[1]
	prefixLen, err := strconv.Atoi(prefixLength)
	if err != nil {
		fmt.Printf("Invalid prefix length: %v", err)
	}
	ip := net.ParseIP(address)
	if ip == nil {
		fmt.Printf("Invalid IPv6 address: %v", address)
	}
	netlinkAddr := &netlink.Addr{
		IPNet: &net.IPNet{
			IP:   ip,
			Mask: net.CIDRMask(prefixLen, 128), // Generate the correct CIDR mask
		},
		Label: "",
	}
	link, err := netlink.LinkByName(devName)
	if err != nil {
		fmt.Printf("Find Link By Name %s Error: %s", devName, err.Error())
		return err
	}

	err = netlink.AddrAdd(link, netlinkAddr)
	if err != nil {
		fmt.Printf("Set Link %s IPv6 Addr error: %s", devName, err.Error())
		return err
	}
	return nil
}

func linkUp(nm NodeManager, nodeId int, devName string) error {
	var err error
	var origNs, nodeNetns netns.NsHandle

	origNs, err = netns.Get()
	if err != nil {
		fmt.Printf("failed to netns.Get of origNs: %s\n", err)
		return err
	}
	defer netns.Set(origNs)

	// Switch into node's netns
	nodeNetns, err = nm.GetNodeNetNs(nodeId)
	if err != nil {
		return err
	}
	err = netns.Set(nodeNetns)
	if err != nil {
		return fmt.Errorf("failed to netns.Set: %s", err)
	}

	// Linkup
	link, err := netlink.LinkByName(devName)
	if err != nil {
		fmt.Printf("Find Link By Name %s Error: %s", devName, err.Error())
		return err
	}
	err = netlink.LinkSetUp(link)
	if err != nil {
		return err
	}
	return nil
}

func setNetSysctl(nm NodeManager, nodeId int, path string, value string) error {
	var err error
	var origNs, nodeNetns netns.NsHandle

	origNs, err = netns.Get()
	if err != nil {
		fmt.Printf("failed to netns.Get of origNs: %s\n", err)
		return err
	}
	defer netns.Set(origNs)

	// Switch into node's netns
	nodeNetns, err = nm.GetNodeNetNs(nodeId)
	if err != nil {
		return err
	}
	err = netns.Set(nodeNetns)
	if err != nil {
		return fmt.Errorf("failed to netns.Set: %s", err)
	}

	if err := SetSysctlValue(path, value); err != nil {
		return fmt.Errorf("error setting kernel.pty.max: %v", err)
	}

	return nil
}
