package network

import (
	"fmt"
	"io/ioutil"
	"log"
	"net"
	"os"
	"os/exec"
	"strconv"
	"sync"
	"time"

	"github.com/vishvananda/netlink"
	"github.com/vishvananda/netns"
)

type NtlBrLinkManager struct {
	curBackBoneNum     int
	curlinkNum         int
	curlinkNumMutex    sync.Mutex
	curBackBoneNs      netns.NsHandle
	ExternalLinkOpTime time.Duration
	hostNetns          netns.NsHandle
	nm                 NodeManager
}

func (lm *NtlBrLinkManager) Init(nm NodeManager) error {
	var err error

	lm.curBackBoneNum = 0
	lm.curlinkNum = 0
	lm.nm = nm
	lm.curBackBoneNs = -1
	lm.ExternalLinkOpTime = 0
	lm.hostNetns, err = netns.Get()
	if err != nil {
		return err
	}
	return nil
}

func (lm *NtlBrLinkManager) Delete() error {
	lm.hostNetns.Close()
	fmt.Printf("ExternalLinkOp time: %.2fs\n", lm.ExternalLinkOpTime.Seconds())
	return nil
}

func (lm *NtlBrLinkManager) SetupBbNs() (netns.NsHandle, error) {
	bbnsName := "bbns" + strconv.Itoa(lm.curBackBoneNum)
	backboneNsHandle, err := netns.NewNamed(bbnsName)
	if err != nil {
		fmt.Printf("failed to netns.NewNamed %s: %s\n", bbnsName, err)
		return -1, err
	}
	lm.curBackBoneNum += 1
	return backboneNsHandle, nil
}

func (lm *NtlBrLinkManager) EnterBbNs(bbnsIndex int) (netns.NsHandle, error) {
	bbnsName := "bbns" + strconv.Itoa(bbnsIndex)
	backboneNsHandle, err := netns.GetFromName(bbnsName)
	if err != nil {
		fmt.Printf("failed to netns.GetFromName %s: %s\n", bbnsName, err)
		return -1, err
	}

	err = netns.Set(backboneNsHandle)
	if err != nil {
		fmt.Printf("failed to netns.Set for bbns: %s\n", err)
		return -1, err
	}

	if DisableIpv6 == 1 {
		err = disableIpv6ForCurNetns()
		if err != nil {
			fmt.Printf("failed to DisableIpv6 for current Netns: %s\n", err)
			return -1, err
		}
	}

	if lm.curBackBoneNs != -1 {
		lm.curBackBoneNs.Close()
	}
	lm.curBackBoneNs = backboneNsHandle
	return backboneNsHandle, nil
}

func (lm *NtlBrLinkManager) CleanAllBbNs() error {
	// var origNs, bbnsHandle netns.NsHandle
	// var err error

	// origNs, err = netns.Get()
	// if err != nil {
	// 	fmt.Printf("failed to netns.Get of origNs: %s\n", err)
	// 	return err
	// }

	// /* Disable bbns ipv6 */
	// bbnsNames := getAllBbNs()
	// for _, bbnsName := range bbnsNames {
	// 	bbnsHandle, err = netns.GetFromName(bbnsName)
	// 	if err != nil {
	// 		return fmt.Errorf("error when getting bbns handle, %v", err)
	// 	}
	// 	fmt.Printf("Disable ipv6 for bbns: %s\n", bbnsName)
	// 	err = netns.Set(bbnsHandle)
	// 	if err != nil {
	// 		fmt.Printf("failed to netns.Set to bbns: %s\n", err)
	// 		return err
	// 	}
	// 	err = disableIpv6ForCurNetns()
	// 	if err != nil {
	// 		fmt.Printf("failed to disableIpv6ForCurNetns for bbns: %s\n", err)
	// 		return err
	// 	}
	// }
	// err = netns.Set(origNs)
	// if err != nil {
	// 	fmt.Printf("failed to netns.Set to origNs: %s\n", err)
	// 	return err
	// }

	/* Destroy all netns */
	destroyCommand := exec.Command(
		"ip", "-all", "netns", "del")
	destroyCommand.Stdout = os.Stdout
	destroyCommand.Run()
	return nil
}

func (lm *NtlBrLinkManager) CleanAllLinks() error {
	var origNs, bbnsHandle netns.NsHandle
	var err error

	origNs, err = netns.Get()
	if err != nil {
		fmt.Printf("failed to netns.Get of origNs: %s\n", err)
		return err
	}

	/* Clean links in all bbns'es */
	bbnsNames := getAllBbNs()
	for _, bbnsName := range bbnsNames {
		bbnsHandle, err = netns.GetFromName(bbnsName)
		if err != nil {
			return fmt.Errorf("error when getting bbns handle, %v", err)
		}
		err = netns.Set(bbnsHandle)
		if err != nil {
			fmt.Printf("failed to netns.Set to bbns: %s\n", err)
			return err
		}
		delCommand := exec.Command(
			"ip", "link", "del", "group", "1")
		delCommand.Run()
	}

	err = netns.Set(origNs)
	if err != nil {
		fmt.Printf("failed to netns.Set to origNs: %s\n", err)
		return err
	}

	return nil
}

/* Before calling SetupLink, current network namespace must be backbone namespace */
func (lm *NtlBrLinkManager) SetupLink(nodeIdi int, nodeIdj int, serverID int, vxlanID int) error {
	var err error
	if vxlanID == -1 {
		err = lm.SetupInternalLink(nodeIdi, nodeIdj, serverID, vxlanID)
	} else {
		err = lm.SetupExternalLink(nodeIdi, nodeIdj, serverID, vxlanID)
	}
	return err
}

/* Before calling SetupInternalLink, current network namespace must be backbone namespace */
func (lm *NtlBrLinkManager) SetupInternalLink(nodeIdi int, nodeIdj int, serverID int, vxlanID int) error {
	var err error
	var backboneNs, nodeiNetNs, nodejNetNs netns.NsHandle
	var brName, vethNamei, vethNamej, insideVethNamei, insideVethNamej string

	/* Prepare network namespace handles */
	backboneNs = lm.curBackBoneNs
	nodeiNetNs, err = lm.nm.GetNodeNetNs(nodeIdi)
	if err != nil {
		return fmt.Errorf("failed to GetNodeNetNs: %s", err)
	}
	defer nodeiNetNs.Close()
	nodejNetNs, err = lm.nm.GetNodeNetNs(nodeIdj)
	if err != nil {
		return fmt.Errorf("failed to GetNodeNetNs: %s", err)
	}
	defer nodejNetNs.Close()

	/* Prepare other data structure */
	if Parallel > 0 {
		lm.curlinkNumMutex.Lock()
	}
	lm.curlinkNum += 1

	insideVethNamei = strconv.Itoa(nodeIdi) + "-" + strconv.Itoa(nodeIdj)
	insideVethNamej = strconv.Itoa(nodeIdj) + "-" + strconv.Itoa(nodeIdi)
	if nodeIdi < nodeIdj {
		brName = strconv.Itoa(nodeIdi) + "-" + strconv.Itoa(nodeIdj)
		vethNamei = strconv.Itoa(nodeIdi) + "-" + strconv.Itoa(nodeIdj) + "-i"
		vethNamej = strconv.Itoa(nodeIdi) + "-" + strconv.Itoa(nodeIdj) + "-j"
	} else {
		brName = strconv.Itoa(nodeIdj) + "-" + strconv.Itoa(nodeIdi)
		vethNamei = strconv.Itoa(nodeIdj) + "-" + strconv.Itoa(nodeIdi) + "-i"
		vethNamej = strconv.Itoa(nodeIdj) + "-" + strconv.Itoa(nodeIdi) + "-j"
	}

	if Parallel > 0 {
		lm.curlinkNumMutex.Unlock()
	}
	br := &netlink.Bridge{
		LinkAttrs: netlink.LinkAttrs{
			Name:  brName,
			MTU:   1450,
			Flags: net.FlagUp,
			Group: 1,
		},
	}
	vethOuti := &netlink.Veth{
		LinkAttrs: netlink.LinkAttrs{
			Name:  vethNamei,
			MTU:   1450,
			Flags: net.FlagUp,
			Group: 1,
			// MasterIndex: br.Index,
		},
		PeerName:      insideVethNamei,
		PeerNamespace: netlink.NsFd(nodeiNetNs),
	}
	vethOutj := &netlink.Veth{
		LinkAttrs: netlink.LinkAttrs{
			Name:  vethNamej,
			MTU:   1450,
			Flags: net.FlagUp,
			Group: 1,
			// MasterIndex: br.Index,
		},
		PeerName:      insideVethNamej,
		PeerNamespace: netlink.NsFd(nodejNetNs),
	}
	vethIni := &netlink.Veth{
		LinkAttrs: netlink.LinkAttrs{
			Name:  insideVethNamei,
			Group: 1,
		},
	}
	vethInj := &netlink.Veth{
		LinkAttrs: netlink.LinkAttrs{
			Name:  insideVethNamej,
			Group: 1,
		},
	}

	/* Create a bridge and two veth pairs */
	if err := netlink.LinkAdd(br); err != nil {
		return fmt.Errorf("failed to create bridge: %s", err)
	}
	vethOuti.Attrs().MasterIndex = br.Index
	err = netlink.LinkAdd(vethOuti)
	if err != nil {
		return fmt.Errorf("failed to create veth: %s", err)
	}
	vethOutj.Attrs().MasterIndex = br.Index
	err = netlink.LinkAdd(vethOutj)
	if err != nil {
		return fmt.Errorf("failed to create veth: %s", err)
	}

	/* Set the other sides of veths up */
	err = netns.Set(nodeiNetNs)
	if err != nil {
		return fmt.Errorf("failed to netns.Set: %s", err)
	}
	err = netlink.LinkSetUp(vethIni)
	if err != nil {
		return fmt.Errorf("failed to LinkSetUp: %s", err)
	}
	err = netns.Set(nodejNetNs)
	if err != nil {
		return fmt.Errorf("failed to netns.Set: %s", err)
	}
	err = netlink.LinkSetUp(vethInj)
	if err != nil {
		return fmt.Errorf("failed to LinkSetUp: %s", err)
	}

	/* Set NetNs Back */
	err = netns.Set(backboneNs)
	if err != nil {
		return fmt.Errorf("failed to netns.Set: %s", err)
	}
	return err
}

/* Before calling SetupExternalLink, current network namespace must be backbone namespace */
func (lm *NtlBrLinkManager) SetupExternalLink(nodeIdi int, nodeIdj int, serverID int, vxlanID int) error {
	var err error
	var backboneNs, nodeiNetNs netns.NsHandle
	var brName, vxlanName, vethNamei, insideVethNamei string

	startTime := time.Now()
	/* Prepare network namespace handles */
	backboneNs = lm.curBackBoneNs
	nodeiNetNs, err = lm.nm.GetNodeNetNs(nodeIdi)
	if err != nil {
		return fmt.Errorf("failed to GetNodeNetNs: %s", err)
	}
	defer nodeiNetNs.Close()

	/* Create Vxlan */
	if Parallel > 0 {
		lm.curlinkNumMutex.Lock()
	}

	insideVethNamei = strconv.Itoa(nodeIdi) + "-" + strconv.Itoa(nodeIdj)
	if nodeIdi < nodeIdj {
		brName = strconv.Itoa(nodeIdi) + "-" + strconv.Itoa(nodeIdj)
		vxlanName = strconv.Itoa(nodeIdi) + "-" + strconv.Itoa(nodeIdj) + "-v"
		vethNamei = strconv.Itoa(nodeIdi) + "-" + strconv.Itoa(nodeIdj) + "-i"
	} else {
		brName = strconv.Itoa(nodeIdj) + "-" + strconv.Itoa(nodeIdi)
		vxlanName = strconv.Itoa(nodeIdj) + "-" + strconv.Itoa(nodeIdi) + "-v"
		vethNamei = strconv.Itoa(nodeIdj) + "-" + strconv.Itoa(nodeIdi) + "-i"
	}

	if Parallel > 0 {
		lm.curlinkNumMutex.Unlock()
	}
	br := &netlink.Bridge{
		LinkAttrs: netlink.LinkAttrs{
			Name:  brName,
			MTU:   1450,
			Flags: net.FlagUp,
			Group: 1,
		},
	}
	vxlanOut := &netlink.Vxlan{
		LinkAttrs: netlink.LinkAttrs{
			Name:  vxlanName,
			Group: 1,
		},
		VxlanId:      vxlanID,
		VtepDevIndex: LocalPhyIntfNl.Attrs().Index,
		Port:         4789,
		Group:        net.ParseIP(ServerList[serverID].IPAddr),
		Learning:     true,
	}
	// vxlanIn := &netlink.Vxlan{
	// 	LinkAttrs: netlink.LinkAttrs{
	// 		Name: vxlanName,
	// 	},
	// }
	vethOuti := &netlink.Veth{
		LinkAttrs: netlink.LinkAttrs{
			Name:  vethNamei,
			MTU:   1450,
			Flags: net.FlagUp,
			Group: 1,
			// MasterIndex: br.Index,
		},
		PeerName:      insideVethNamei,
		PeerNamespace: netlink.NsFd(nodeiNetNs),
	}
	vethIni := &netlink.Veth{
		LinkAttrs: netlink.LinkAttrs{
			Name:  insideVethNamei,
			Group: 1,
		},
	}

	/* Create network devices */
	err = netns.Set(lm.hostNetns)
	if err != nil {
		return fmt.Errorf("failed to netns.Set: %s", err)
	}
	if err = netlink.LinkAdd(vxlanOut); err != nil {
		return fmt.Errorf("failed to create vxlan interface: %s", err)
	}
	err = netlink.LinkSetNsFd(vxlanOut, int(backboneNs))
	if err != nil {
		return fmt.Errorf("failed to link set nsfd: %s", err)
	}
	err = netns.Set(backboneNs)
	if err != nil {
		return fmt.Errorf("failed to netns.Set: %s", err)
	}
	if err := netlink.LinkAdd(br); err != nil {
		return fmt.Errorf("failed to create bridge: %s", err)
	}
	vethOuti.Attrs().MasterIndex = br.Index
	err = netlink.LinkAdd(vethOuti)
	if err != nil {
		return fmt.Errorf("failed to create VethPeer in nodeiNetNs: %s", err)
	}

	/* Set Vxlan master and set Vxlan up */
	var newVxlan netlink.Link
	newVxlan, err = netlink.LinkByName(vxlanName)
	if err != nil {
		return fmt.Errorf("failed to LinkByName (%d, %d, %d, %s, %v): %s", nodeIdi, nodeIdj, vxlanID, brName, br, err)
	}
	err = netlink.LinkSetGroup(newVxlan, 1)
	if err != nil {
		return fmt.Errorf("failed to LinkSetGroup (%d, %d, %d, %s, %v): %s", nodeIdi, nodeIdj, vxlanID, brName, br, err)
	}
	err = netlink.LinkSetMaster(newVxlan, br)
	if err != nil {
		return fmt.Errorf("failed to LinkSetMaster (%d, %d, %d, %s, %v): %s", nodeIdi, nodeIdj, vxlanID, brName, br, err)
	}
	err = netlink.LinkSetUp(newVxlan)
	if err != nil {
		return fmt.Errorf("failed to LinkSetUp: %s", err)
	}
	err = netns.Set(nodeiNetNs)
	if err != nil {
		return fmt.Errorf("failed to netns.Set: %s", err)
	}
	err = netlink.LinkSetUp(vethIni)
	if err != nil {
		return fmt.Errorf("failed to LinkSetUp: %s", err)
	}

	/* Set NetNs Back */
	err = netns.Set(backboneNs)
	if err != nil {
		return fmt.Errorf("failed to netns.Set: %s", err)
	}
	lm.ExternalLinkOpTime += time.Since(startTime)

	return err
}

func getAllBbNs() []string {
	// Directory where ip netns namespaces are stored
	netnsDir := "/var/run/netns"

	// Read the contents of the netns directory
	files, err := ioutil.ReadDir(netnsDir)
	if err != nil {
		if os.IsNotExist(err) {
			log.Fatalf("Network namespace directory does not exist: %v", err)
		}
		log.Fatalf("Error reading %s: %v", netnsDir, err)
	}

	// Collect namespace names
	var namespaces []string
	for _, file := range files {
		if !file.IsDir() {
			namespaces = append(namespaces, file.Name())
		}
	}

	return namespaces
}
