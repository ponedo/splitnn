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

	"github.com/vishvananda/netlink"
	"github.com/vishvananda/netns"
)

type NtlBrLinkManager struct {
	curBackBoneNum  int
	curlinkNum      int
	curlinkNumMutex sync.Mutex
	curBackBoneNs   netns.NsHandle
	hostNetns       netns.NsHandle
	nm              NodeManager
}

func (lm *NtlBrLinkManager) Init(nm NodeManager) error {
	var err error

	lm.curBackBoneNum = 0
	lm.curlinkNum = 0
	lm.nm = nm
	lm.curBackBoneNs = -1
	lm.hostNetns, err = netns.Get()
	if err != nil {
		return err
	}
	return nil
}

func (lm *NtlBrLinkManager) Delete() error {
	lm.hostNetns.Close()
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
		fmt.Printf("failed to netns.NewNamed %s: %s\n", bbnsName, err)
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

func (lm *NtlBrLinkManager) CleanAllLinks(groupID int) error {
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
			"ip", "link", "del", "group", strconv.Itoa(groupID))
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
func (lm *NtlBrLinkManager) SetupLink(nodeIdi int, nodeIdj int, serverID int, vxlanID int, groupID int) error {
	var err error
	if vxlanID == -1 {
		err = lm.SetupInternalLink(nodeIdi, nodeIdj, serverID, vxlanID, groupID)
	} else {
		err = lm.SetupExternalLink(nodeIdi, nodeIdj, serverID, vxlanID, groupID)
	}
	return err
}

/* Before calling SetupInternalLink, current network namespace must be backbone namespace */
func (lm *NtlBrLinkManager) SetupInternalLink(nodeIdi int, nodeIdj int, serverID int, vxlanID int, groupID int) error {
	var err error
	var backboneNs, nodeiNetNs, nodejNetNs netns.NsHandle
	var brName string

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
	brName = "br-" + strconv.Itoa(lm.curlinkNum)
	vethNamei := "eth-" + strconv.Itoa(lm.curlinkNum) + "-i"
	vethNamej := "eth-" + strconv.Itoa(lm.curlinkNum) + "-j"
	if Parallel > 0 {
		lm.curlinkNumMutex.Unlock()
	}
	br := &netlink.Bridge{
		LinkAttrs: netlink.LinkAttrs{
			Name:  brName,
			MTU:   1450,
			Flags: net.FlagUp,
			Group: uint32(groupID),
		},
	}
	vethOuti := &netlink.Veth{
		LinkAttrs: netlink.LinkAttrs{
			Name:  vethNamei,
			MTU:   1450,
			Flags: net.FlagUp,
			Group: uint32(groupID),
			// MasterIndex: br.Index,
		},
		PeerName:      vethNamei,
		PeerNamespace: netlink.NsFd(nodeiNetNs),
	}
	vethOutj := &netlink.Veth{
		LinkAttrs: netlink.LinkAttrs{
			Name:  vethNamej,
			MTU:   1450,
			Flags: net.FlagUp,
			Group: uint32(groupID),
			// MasterIndex: br.Index,
		},
		PeerName:      vethNamej,
		PeerNamespace: netlink.NsFd(nodejNetNs),
	}
	vethIni := &netlink.Veth{
		LinkAttrs: netlink.LinkAttrs{
			Name:  vethNamei,
			Group: uint32(groupID),
		},
	}
	vethInj := &netlink.Veth{
		LinkAttrs: netlink.LinkAttrs{
			Name:  vethNamej,
			Group: uint32(groupID),
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
func (lm *NtlBrLinkManager) SetupExternalLink(nodeIdi int, nodeIdj int, serverID int, vxlanID int, groupID int) error {
	var err error
	var backboneNs, nodeiNetNs netns.NsHandle

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
	brName := "br-" + strconv.Itoa(lm.curlinkNum)
	vxlanName := "eth-" + strconv.Itoa(lm.curlinkNum) + "-v"
	vethNamei := "vxl-" + strconv.Itoa(lm.curlinkNum)
	if Parallel > 0 {
		lm.curlinkNumMutex.Unlock()
	}
	br := &netlink.Bridge{
		LinkAttrs: netlink.LinkAttrs{
			Name:  brName,
			MTU:   1450,
			Flags: net.FlagUp,
			Group: uint32(groupID),
		},
	}
	vxlanOut := &netlink.Vxlan{
		LinkAttrs: netlink.LinkAttrs{
			Name:  vxlanName,
			Group: uint32(groupID),
		},
		VxlanId:      vxlanID,
		VtepDevIndex: LocalPhyIntfNl.Attrs().Index,
		Port:         4789,
		Group:        net.ParseIP(ServerList[serverID].IPAddr),
		Learning:     true,
	}
	vxlanIn := &netlink.Vxlan{
		LinkAttrs: netlink.LinkAttrs{
			Name:  vxlanName,
			Group: uint32(groupID),
		},
	}
	vethOuti := &netlink.Veth{
		LinkAttrs: netlink.LinkAttrs{
			Name:  vethNamei,
			MTU:   1450,
			Flags: net.FlagUp,
			Group: uint32(groupID),
			// MasterIndex: br.Index,
		},
		PeerName:      vethNamei,
		PeerNamespace: netlink.NsFd(nodeiNetNs),
	}
	vethIni := &netlink.Veth{
		LinkAttrs: netlink.LinkAttrs{
			Name:  vethNamei,
			Group: uint32(groupID),
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
	err = netlink.LinkSetMaster(vxlanIn, br)
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
