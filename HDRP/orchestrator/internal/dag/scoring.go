package dag

import (
	"fmt"
)

// SetNodeRelevance updates the relevance score for a specific node.
// It enforces the range [0.0, 1.0].
func (g *Graph) SetNodeRelevance(nodeID string, score float64) error {
	if score < 0.0 || score > 1.0 {
		return fmt.Errorf("relevance score must be between 0.0 and 1.0, got %f", score)
	}

	for i := range g.Nodes {
		if g.Nodes[i].ID == nodeID {
			g.Nodes[i].RelevanceScore = score
			return nil
		}
	}
	return fmt.Errorf("node %s not found in graph", nodeID)
}

// CalculateGraphRelevance returns the average relevance score of all nodes.
// Useful for pruning or prioritizing low-confidence execution paths.
func (g *Graph) CalculateGraphRelevance() float64 {
	if len(g.Nodes) == 0 {
		return 0.0
	}

	total := 0.0
	for _, n := range g.Nodes {
		total += n.RelevanceScore
	}
	return total / float64(len(g.Nodes))
}
