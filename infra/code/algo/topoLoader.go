package algo

import (
	"bufio"
	"fmt"
	"os"
	"strconv"
	"strings"
)

// ReadGraphFromFile reads a graph topology from a file
func ReadGraphFromFile(filename string) (*Graph, error) {
	file, err := os.Open(filename)
	if err != nil {
		return nil, err
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	scanner.Buffer(make([]byte, 1024*1024), int(1024*1024))
	graph := NewGraph()

	// Read the first line to get node indices
	if scanner.Scan() {
		nodes := strings.Fields(scanner.Text())
		for _, nodeStr := range nodes {
			node, err := strconv.Atoi(nodeStr)
			if err != nil {
				return nil, fmt.Errorf("invalid node index: %v", nodeStr)
			}
			graph.AdjacencyList[node] = []int{}
		}
	}

	// Read subsequent lines for edges
	for scanner.Scan() {
		line := strings.Fields(scanner.Text())
		if len(line) == 2 && strings.Contains(line[1], "_external") {
			// Handle dangling edges
			nodeIDStr := line[0]
			nodeID, _ := strconv.Atoi(nodeIDStr)
			splitedLine1 := strings.Split(line[1], "_")
			externalNodeStr := splitedLine1[0]
			externalNodeID, _ := strconv.Atoi(externalNodeStr)
			serverIDStr := splitedLine1[2]
			serverID, _ := strconv.Atoi(serverIDStr)
			vxlanIDStr := splitedLine1[3]
			vxlanID, _ := strconv.Atoi(vxlanIDStr)

			graph.DanglingEdgeList[nodeID] = append(
				graph.DanglingEdgeList[nodeID], [3]int{externalNodeID, serverID, vxlanID})
		} else if len(line) == 2 {
			u, _ := strconv.Atoi(line[0]) // Node ID
			v, _ := strconv.Atoi(line[1]) // Neighbor Node ID
			graph.AdjacencyList[u] = append(graph.AdjacencyList[u], v)
			graph.AdjacencyList[v] = append(graph.AdjacencyList[v], u) // Undirected graph
		}
	}

	if err := scanner.Err(); err != nil {
		return nil, err
	}

	return graph, nil
}
