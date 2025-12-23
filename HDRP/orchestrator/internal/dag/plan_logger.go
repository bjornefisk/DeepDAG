package dag

import (
	"context"

	"hdrp/internal/logger"
)

// LogGraphPlan captures the current state of the graph and logs it as a structured event.
// This corresponds to the "Pull Plan" phase where the execution strategy is finalized.
func LogGraphPlan(ctx context.Context, runID string, g *Graph) {
	if g == nil {
		logger.LogEvent(ctx, runID, "orchestrator", "plan_generation_failed", map[string]string{
			"error": "graph is nil",
		})
		return
	}

	payload := map[string]interface{}{
		"graph_id": g.ID,
		"status":   g.Status,
		"nodes":    summarizeNodes(g.Nodes),
		"edges":    g.Edges,
		"metrics": map[string]interface{}{
			"node_count":      len(g.Nodes),
			"edge_count":      len(g.Edges),
			"avg_relevance":   g.CalculateGraphRelevance(),
			"est_parallelism": estimateParallelism(g),
		},
	}

	logger.LogEvent(ctx, runID, "orchestrator", "plan_generated", payload)
}

func summarizeNodes(nodes []Node) []map[string]interface{} {
	summary := make([]map[string]interface{}, len(nodes))
	for i, n := range nodes {
		summary[i] = map[string]interface{}{
			"id":        n.ID,
			"type":      n.Type,
			"status":    n.Status,
			"relevance": n.RelevanceScore,
			// Config omitted to reduce log noise, can be added if debug level needed
		}
	}
	return summary
}

// estimateParallelism provides a heuristic on how many nodes can run concurrently.
// It's a simple count of nodes with 0 in-degree in the current ready state.
func estimateParallelism(g *Graph) int {
	inDegree := make(map[string]int)
	for _, e := range g.Edges {
		inDegree[e.To]++
	}

	count := 0
	for _, n := range g.Nodes {
		if inDegree[n.ID] == 0 {
			count++
		}
	}
	return count
}
