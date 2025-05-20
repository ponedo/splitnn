package algo

import (
	"container/heap"
)

// Node represents a node in the graph
type Node struct {
	id           int
	contribution int
	index        int
}

// PriorityQueue implements a max-heap
type PriorityQueue []*Node

func (pq PriorityQueue) Len() int { return len(pq) }

func (pq PriorityQueue) Less(i, j int) bool {
	// Max-heap: node with higher contribution comes first
	return pq[i].contribution > pq[j].contribution
}

func (pq PriorityQueue) Swap(i, j int) {
	pq[i], pq[j] = pq[j], pq[i]
	pq[i].index = i
	pq[j].index = j
}

func (pq *PriorityQueue) Push(x interface{}) {
	n := len(*pq)
	node := x.(*Node)
	node.index = n
	*pq = append(*pq, node)
}

func (pq *PriorityQueue) Pop() interface{} {
	old := *pq
	n := len(old)
	node := old[n-1]
	node.index = -1
	*pq = old[0 : n-1]
	return node
}

// Update modifies the contribution of a node in the heap and reorders the heap
func (pq *PriorityQueue) Update(node *Node, newContribution int) {
	node.contribution = newContribution
	heap.Fix(pq, node.index)
}

// Graph represents a graph using an adjacency list
type Graph struct {
	AdjacencyList    map[int][]int
	DanglingEdgeList map[int][][3]int // externalNodeID, serverID, vxlanID
}

// NewGraph initializes a new graph
func NewGraph() *Graph {
	return &Graph{
		AdjacencyList:    make(map[int][]int),
		DanglingEdgeList: make(map[int][][3]int),
	}
}

// AddEdge adds an edge to the graph
func (g *Graph) GetNodeNum() int {
	return len(g.AdjacencyList)
}

func (g *Graph) GetEdgeNum() int {
	edgeNum := 0
	for _, adjList := range g.AdjacencyList {
		edgeNum += len(adjList)
	}
	edgeNum /= 2
	for _, danglingList := range g.DanglingEdgeList {
		edgeNum += len(danglingList)
	}
	return edgeNum
}
