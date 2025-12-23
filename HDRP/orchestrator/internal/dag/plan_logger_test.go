package dag

import (
	"context"
	"testing"
)

func TestLogGraphPlan(t *testing.T) {
	// Construct a sample graph
	g := &Graph{
		ID:     "log-test-graph",
		Status: StatusCreated,
		Nodes: []Node{
			{ID: "A", Type: "researcher", Status: StatusCreated, RelevanceScore: 0.9},
			{ID: "B", Type: "critic", Status: StatusBlocked, RelevanceScore: 0.8},
		},
		Edges: []Edge{
			{From: "A", To: "B"},
		},
	}

	// This test primarily ensures no panics occur during logging and payload construction.
	// Since the logger writes to stdout/file, we rely on the absence of errors.
	// In a real integration test, we would mock the logger or check the file output.
	
	ctx := context.Background()
	runID := "test-run-123"

	// Should not panic
	LogGraphPlan(ctx, runID, g)
	
	// Test Nil Graph
	LogGraphPlan(ctx, runID, nil)
}

func TestEstimateParallelism(t *testing.T) {
	g := &Graph{
		Nodes: []Node{{ID: "A"}, {ID: "B"}, {ID: "C"}},
		Edges: []Edge{
			{From: "A", To: "B"},
			// C is disconnected
		},
	}
	
	// A has 0 in-degree. C has 0 in-degree. B has 1.
	// Parallelism should be 2.
	p := estimateParallelism(g)
	if p != 2 {
		t.Errorf("Expected parallelism 2, got %d", p)
	}
}
