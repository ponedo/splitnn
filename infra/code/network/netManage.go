package network

import (
	"fmt"
	"os"
	"time"
	"topo_setup_test/algo"

	"github.com/vishvananda/netlink"
	"github.com/vishvananda/netns"
)

type NodeManager interface {
	Init() error
	Delete() error
	SetupNode(int) error
	GetNodeNetNs(int) (netns.NsHandle, error)
	CleanNode(int) error
	NodeExec(int, []string) error
}

type LinkManager interface {
	Init(NodeManager) error
	Delete() error
	SetupBbNs() (netns.NsHandle, error)
	EnterBbNs(int) (netns.NsHandle, error)
	CleanAllBbNs() error
	SetupLink(int, int, int, int) error
	CleanAllLinks() error
}

func NetworkSetup(
	lm LinkManager, nm NodeManager,
	g *algo.Graph, nodeOrder []int, edgeOrder [][][4]int,
	backBoneNum int) error {
	var err error
	var curLinkNum int
	var hostNs, curBackBoneNs netns.NsHandle
	var threadPool *ThreadPool

	nm.Init()
	lm.Init(nm)

	hostNs, err = netns.Get()
	if err != nil {
		return err
	}
	defer hostNs.Close()

	/* Prepare a thread pool if needed */
	if Parallel > 0 {
		threadPool = NewThreadPool(Parallel)
		threadPool.Run()
	}

	reportTime := 100
	nodeNum := g.GetNodeNum()
	linkNum := g.GetEdgeNum()
	nodeTmpTime := time.Now()
	linkTmpTime := time.Now()
	nodePerReport := nodeNum / reportTime
	linkPerReport := linkNum / reportTime
	linkPerBackBoneNs := (g.GetEdgeNum() + backBoneNum - 1) / backBoneNum

	startNodeTime := time.Now()
	for i, nodeId := range nodeOrder {
		/* Progress reporter */
		if nodePerReport > 0 && i%nodePerReport == 0 {
			progress := 100 * i / nodeNum
			curTime := time.Now()
			fmt.Printf("%d%% nodes are added, time elapsed from last report: %dms\n",
				progress, curTime.Sub(nodeTmpTime).Milliseconds())
			nodeTmpTime = time.Now()
		}

		/* Setup next node and connectable links */
		err = nm.SetupNode(nodeId)
		if err != nil {
			return err
		}

		_, err = LinkLogFile.WriteString(
			fmt.Sprintf("Node %d\n", nodeId))
		if err != nil {
			return err
		}
	}
	nodeTotalTime := time.Since(startNodeTime)

	/* Setup backbone namespaces */
	startBbNsTime := time.Now()
	for i := 0; i < backBoneNum; i += 1 {
		curBackBoneNs, err = lm.SetupBbNs()
		fmt.Printf("Creating bbns %d\n", i)
		if err != nil {
			return err
		}
	}
	bbnsTotalTime := time.Since(startBbNsTime)

	startLinkTime := time.Now()
	for i := range nodeOrder {
		/* Setup connectable links */
		curBbnsIndex := 0
		for _, edge := range edgeOrder[i] {
			curLinkStartTime := time.Now()
			/* Create new backbone network namespace on demand */
			if curLinkNum%linkPerBackBoneNs == 0 {
				curBackBoneNs, err = lm.EnterBbNs(curBbnsIndex)
				curBbnsIndex += 1
				if err != nil {
					return err
				}
			}
			if Parallel > 0 {
				threadPool.AddTask(
					func(args ...interface{}) error {
						var err error
						bbns := args[0].(netns.NsHandle)
						edge := args[1].([4]int)
						err = netns.Set(bbns)
						if err != nil {
							return err
						}
						err = lm.SetupLink(edge[0], edge[1], edge[2], edge[3])
						if err != nil {
							fmt.Printf("SetupLink (%d, %d) failed %v, !\n", edge[0], edge[1], err)
							return err
						}
						return nil
					}, curBackBoneNs, edge)
			} else {
				if linkPerReport > 0 && curLinkNum%linkPerReport == 0 {
					progress := 100 * curLinkNum / linkNum
					curTime := time.Now()
					fmt.Printf("%d%% links are added, time elapsed from last report: %dms\n",
						progress, curTime.Sub(linkTmpTime).Milliseconds())
					linkTmpTime = time.Now()
				}
				err = lm.SetupLink(edge[0], edge[1], edge[2], edge[3])
				if err != nil {
					return err
				}
			}

			curLinkTime := time.Since(curLinkStartTime)
			curLinkTimeInNs := curLinkTime.Nanoseconds()
			_, err = LinkLogFile.WriteString(
				fmt.Sprintf("Link no.%d %dns\n", curLinkNum, curLinkTimeInNs))
			if err != nil {
				return err
			}

			curLinkNum += 1
		}
		if Parallel > 0 && len(edgeOrder[i]) > 0 {
			threadPool.Wait()
			if threadPool.hasError {
				for err := range threadPool.errors {
					return err
				}
			}
		}
	}
	linkTotalTime := time.Since(startLinkTime)

	fmt.Printf("Node setup time: %.2fs\n", nodeTotalTime.Seconds())
	fmt.Printf("Bbns setup time: %.2fs\n", bbnsTotalTime.Seconds())
	fmt.Printf("Link setup time: %.2fs\n", linkTotalTime.Seconds())

	err = netns.Set(hostNs)
	if err != nil {
		return err
	}

	lm.Delete()
	nm.Delete()

	return nil
}

func NetworkClean(
	lm LinkManager, nm NodeManager,
	g *algo.Graph, nodeOrder []int, edgeOrder [][][4]int,
	backBoneNum int) error {

	var startTime time.Time

	nm.Init()
	lm.Init(nm)

	// edgeNum := g.GetEdgeNum()
	// extraTestTime := edgeNum / 50

	startTime = time.Now()
	lm.CleanAllLinks()
	syncNtlk(0)
	fmt.Printf("Clean link time: %.2fs\n", time.Since(startTime).Seconds())

	startTime = time.Now()
	lm.CleanAllBbNs()
	syncNtlk(0)
	fmt.Printf("Clean bbns time: %.2fs\n", time.Since(startTime).Seconds())

	startTime = time.Now()
	for nodeId := range g.AdjacencyList {
		// fmt.Printf("nodeId: %d\n", nodeId)
		nm.CleanNode(nodeId)
	}
	syncNtlk(0)
	fmt.Printf("Clean node time: %.2fs\n", time.Since(startTime).Seconds())

	lm.Delete()
	nm.Delete()

	return nil
}

func disableIpv6ForCurNetns() error {
	// Set disable_ipv6 for the namespace
	path := "/proc/sys/net/ipv6/conf/all/disable_ipv6"
	disableIPv6 := "1"

	f, err := os.OpenFile(path, os.O_WRONLY, 0644)
	if err != nil {
		return fmt.Errorf("failed to open sysctl file: %v", err)
	}
	defer f.Close()

	_, err = f.WriteString(disableIPv6)
	if err != nil {
		return fmt.Errorf("failed to write to sysctl file: %v", err)
	}

	return nil
}

var probeLink *netlink.Dummy

func probeNtlk() error {
	var err error
	err = netlink.LinkAdd(probeLink)
	if err != nil {
		fmt.Printf("failed to LinkAdd at : %s", err)
		return err
	}
	err = netlink.LinkDel(probeLink)
	if err != nil {
		fmt.Printf("failed to LinkDel: %s", err)
		return err
	}
	return err
}

func syncNtlk(extraTestTime int) error {
	var err error
	var start, end time.Time

	/* Use multiple "ip link add test-link" to probe whether rtnl_lock is released by netns deletion */
	extraTurnNum := (extraTestTime + 99) / 100
	testTime := 20
	probeLink = &netlink.Dummy{
		LinkAttrs: netlink.LinkAttrs{
			Name: "probe-dummy",
		},
	}
	time.Sleep(2 * time.Second)
	fmt.Printf("Probing for %d (%d x %d) times...",
		(1+extraTurnNum)*testTime, 1+extraTurnNum, testTime)
	start = time.Now()
	for i := 0; i < 1+extraTurnNum; i += 1 {
		for j := 0; j < testTime; j += 1 {
			err = probeNtlk()
			if err != nil {
				fmt.Printf("failed to probNtlk: %s", err)
				return err
			}
			fmt.Printf(" %d", j)
		}
		time.Sleep(2 * time.Second)
	}
	end = time.Now()
	fmt.Printf("\n")
	fmt.Printf("Probe time: %dms\n", end.Sub(start).Milliseconds())

	return nil
}
