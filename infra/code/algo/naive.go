package algo

// MaximizeEdgesOrder returns the nodeOrder of nodes to maximize edges incrementally
func (g *Graph) NaiveOrder() ([]int, [][][4]int, []int) {
	nodeOrder := []int{}
	edgeOrder := [][][4]int{}
	curEdgeNumSeq := []int{}

	/* Setup nodes in default order */
	for nodeId := range g.AdjacencyList {
		nodeOrder = append(nodeOrder, nodeId)
	}

	/* Before setupping the last node, do not setup any links */
	for i := 0; i < len(g.AdjacencyList)-1; i += 1 {
		edgeOrder = append(edgeOrder, [][4]int{})
		curEdgeNumSeq = append(curEdgeNumSeq, 0)
	}

	/* After setting up the last node, setup all links */
	allInternalEdges := [][4]int{}
	for i := range g.AdjacencyList {
		for _, j := range g.AdjacencyList[i] {
			if i < j {
				allInternalEdges = append(allInternalEdges, [4]int{i, j, -1, -1})
			}
		}
	}
	allDanglingEdges := [][4]int{}
	for i := range g.DanglingEdgeList {
		for _, neighbor := range g.DanglingEdgeList[i] {
			j := neighbor[0]
			serverID := neighbor[1]
			vxlanID := neighbor[2]
			// if i < j {
			allDanglingEdges = append(allDanglingEdges, [4]int{i, j, serverID, vxlanID})
			// }
		}
	}
	allEdges := append(allInternalEdges, allDanglingEdges...)
	edgeOrder = append(edgeOrder, allEdges)
	curEdgeNumSeq = append(curEdgeNumSeq, len(allEdges))

	return nodeOrder, edgeOrder, curEdgeNumSeq
}
