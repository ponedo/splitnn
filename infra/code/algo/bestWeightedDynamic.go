package algo

import (
	"fmt"
	"time"
)

// MaximizeEdgesOrderWeightedDynamic initializes contributions with node degrees and updates dynamically
func (g *Graph) MaximizeEdgesOrderBestWeightedDynamic() ([]int, [][][4]int, []int) {
	var nodeOrder, curEdgeNumSeq []int
	var edgeOrder [][][4]int
	var start, end time.Time
	var i int

	start = time.Now()
	i = 0
	for nodeId := range g.AdjacencyList {
		nodeOrder, edgeOrder, curEdgeNumSeq = g.MaximizeEdgesOrderInitDynamic(nodeId)
		if i%100 == 0 {
			end = time.Now()
			fmt.Printf("[Best greedy search] 100 plans were run. Time cost: %vs\n", end.Sub(start).Seconds())
			start = time.Now()
		}
		i += 1
	}
	return nodeOrder, edgeOrder, curEdgeNumSeq
}
