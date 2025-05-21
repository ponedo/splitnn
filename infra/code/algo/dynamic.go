package algo

import "container/heap"

// MaximizeEdgesOrder returns the nodeOrder of nodes to maximize edges incrementally
func (g *Graph) MaximizeEdgesOrderDynamic() ([]int, [][][4]int, []int) {
	pq := make(PriorityQueue, 0)
	heap.Init(&pq)

	// Map to track selected nodes and node contributions
	selectedNodes := make(map[int]bool)
	nodeMap := make(map[int]*Node)

	// Initialize heap with nodes and zero contribution
	for node := range g.AdjacencyList {
		initContribution := len(g.DanglingEdgeList[node])
		n := &Node{id: node, contribution: initContribution}
		heap.Push(&pq, n)
		nodeMap[node] = n
	}

	nodeOrder := []int{}
	edgeOrder := [][][4]int{}
	curEdgeNumSeq := []int{}
	curEdgeNum := 0

	// Select nodes in the nodeOrder that maximizes edges incrementally
	for pq.Len() > 0 {
		node := heap.Pop(&pq).(*Node)

		// Skip already selected nodes
		if selectedNodes[node.id] {
			continue
		}

		// Add node to the selected set
		selectedNodes[node.id] = true
		nodeOrder = append(nodeOrder, node.id)

		// Add internal edges into order, and update contributions of neighbors
		edgeSubset := [][4]int{}
		for _, neighbor := range g.AdjacencyList[node.id] {
			if selectedNodes[neighbor] {
				edgeSubset = append(edgeSubset, [4]int{node.id, neighbor, -1, -1})
				curEdgeNum += 1
				continue
			}

			// Increase the contribution of the neighboring node
			neighborNode := nodeMap[neighbor]
			neighborNode.contribution++
			pq.Update(neighborNode, neighborNode.contribution)
		}

		// Add external edges into order
		for _, neighbor := range g.DanglingEdgeList[node.id] {
			edgeSubset = append(edgeSubset, [4]int{node.id, neighbor[0], neighbor[1], neighbor[2]})
			curEdgeNum += 1
		}

		// Append the current edge count to curEdgeNumSeq
		edgeOrder = append(edgeOrder, edgeSubset)
		curEdgeNumSeq = append(curEdgeNumSeq, curEdgeNum)
	}

	return nodeOrder, edgeOrder, curEdgeNumSeq
}
