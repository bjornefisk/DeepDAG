package dag

import (
	"testing"
)

func TestRelevanceScoring(t *testing.T) {
	g := &Graph{
		ID: "test-graph",
		Nodes: []Node{
			{ID: "A", RelevanceScore: 0.5},
			{ID: "B", RelevanceScore: 0.0},
		},
	}

	t.Run("Set Valid Score", func(t *testing.T) {
		err := g.SetNodeRelevance("B", 0.8)
		if err != nil {
			t.Errorf("Unexpected error: %v", err)
		}
		if g.Nodes[1].RelevanceScore != 0.8 {
			t.Errorf("Expected 0.8, got %f", g.Nodes[1].RelevanceScore)
		}
	})

	t.Run("Set Invalid Score Low", func(t *testing.T) {
		err := g.SetNodeRelevance("A", -0.1)
		if err == nil {
			t.Error("Expected error for negative score, got nil")
		}
	})

	t.Run("Set Invalid Score High", func(t *testing.T) {
		err := g.SetNodeRelevance("A", 1.1)
		if err == nil {
			t.Error("Expected error for score > 1.0, got nil")
		}
	})

	t.Run("Calculate Average", func(t *testing.T) {
		// A is 0.5, B is 0.8
		avg := g.CalculateGraphRelevance()
		expected := (0.5 + 0.8) / 2.0
		if avg != expected {
			t.Errorf("Expected average %f, got %f", expected, avg)
		}
	})

	t.Run("Calculate Empty Graph", func(t *testing.T) {
		emptyG := &Graph{}
		avg := emptyG.CalculateGraphRelevance()
		if avg != 0.0 {
			t.Errorf("Expected 0.0 for empty graph, got %f", avg)
		}
	})
	
	t.Run("Node Not Found", func(t *testing.T) {
		err := g.SetNodeRelevance("MISSING", 0.5)
		if err == nil {
			t.Error("Expected error for missing node")
		}
	})
}
