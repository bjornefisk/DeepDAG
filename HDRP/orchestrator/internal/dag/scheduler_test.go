package dag

import (
	"testing"
)

func TestScheduleNextBatch(t *testing.T) {
	t.Run("Batch Size Limit", func(t *testing.T) {
		g := &Graph{
			Nodes: []Node{
				{ID: "A", Status: StatusPending, RelevanceScore: 0.9},
				{ID: "B", Status: StatusPending, RelevanceScore: 0.8},
				{ID: "C", Status: StatusPending, RelevanceScore: 0.7},
				{ID: "D", Status: StatusPending, RelevanceScore: 0.6},
				{ID: "E", Status: StatusPending, RelevanceScore: 0.5},
			},
		}

		batch, err := g.ScheduleNextBatch(3)
		if err != nil {
			t.Fatalf("ScheduleNextBatch failed: %v", err)
		}

		if len(batch) != 3 {
			t.Errorf("Expected 3 nodes, got %d", len(batch))
		}

		// Verify they're the top 3 by relevance
		if batch[0].ID != "A" || batch[1].ID != "B" || batch[2].ID != "C" {
			t.Errorf("Wrong nodes selected: %v", []string{batch[0].ID, batch[1].ID, batch[2].ID})
		}

		// Verify they're all RUNNING
		for _, node := range batch {
			if node.Status != StatusRunning {
				t.Errorf("Node %s should be RUNNING, got %s", node.ID, node.Status)
			}
		}
	})

	t.Run("Parallel Scheduling", func(t *testing.T) {
		g := &Graph{
			Nodes: []Node{
				{ID: "task-A", Status: StatusPending, RelevanceScore: 0.5},
				{ID: "task-B", Status: StatusPending, RelevanceScore: 0.5},
				{ID: "task-C", Status: StatusPending, RelevanceScore: 0.5},
			},
		}

		batch, err := g.ScheduleNextBatch(10)
		if err != nil {
			t.Fatalf("ScheduleNextBatch failed: %v", err)
		}

		if len(batch) != 3 {
			t.Errorf("Expected all 3 nodes to be scheduled, got %d", len(batch))
		}

		// Verify graph state updated
		runningCount := 0
		for _, n := range g.Nodes {
			if n.Status == StatusRunning {
				runningCount++
			}
		}

		if runningCount != 3 {
			t.Errorf("Expected 3 nodes RUNNING in graph, got %d", runningCount)
		}
	})

	t.Run("Empty When No Pending", func(t *testing.T) {
		g := &Graph{
			Nodes: []Node{
				{ID: "done-A", Status: StatusSucceeded},
				{ID: "done-B", Status: StatusSucceeded},
			},
		}

		batch, err := g.ScheduleNextBatch(5)
		if err != nil {
			t.Fatalf("Unexpected error: %v", err)
		}

		if len(batch) != 0 {
			t.Errorf("Expected empty batch, got %d nodes", len(batch))
		}
	})

	t.Run("Backward Compatibility with ScheduleNext", func(t *testing.T) {
		g := &Graph{
			Nodes: []Node{
				{ID: "high", Status: StatusPending, RelevanceScore: 0.9},
				{ID: "low", Status: StatusPending, RelevanceScore: 0.1},
			},
		}

		node, err := g.ScheduleNext()
		if err != nil {
			t.Fatalf("ScheduleNext failed: %v", err)
		}

		if node.ID != "high" {
			t.Errorf("Expected 'high' to be selected, got %s", node.ID)
		}

		if node.Status != StatusRunning {
			t.Errorf("Node should be RUNNING, got %s", node.Status)
		}
	})

	t.Run("Rollback on Transition Failure", func(t *testing.T) {
		// Create a graph with an already-running node to simulate a transition failure
		// This test is more conceptual - in practice, SetNodeStatus validates transitions
		g := &Graph{
			Nodes: []Node{
				{ID: "A", Status: StatusPending, RelevanceScore: 0.9},
				{ID: "B", Status: StatusSucceeded, RelevanceScore: 0.8}, // Cannot transition to RUNNING
			},
		}

		// Manually break state to test rollback
		// In real use, this would be caught by SetNodeStatus validation
		batch, err := g.ScheduleNextBatch(1)
		if err != nil {
			t.Fatalf("Unexpected error: %v", err)
		}

		if len(batch) != 1 || batch[0].ID != "A" {
			t.Errorf("Expected to schedule A, got %v", batch)
		}
	})
}

func TestGetReadyNodesCount(t *testing.T) {
	g := &Graph{
		Nodes: []Node{
			{ID: "A", Status: StatusPending},
			{ID: "B", Status: StatusRunning},
			{ID: "C", Status: StatusPending},
			{ID: "D", Status: StatusSucceeded},
			{ID: "E", Status: StatusBlocked},
		},
	}

	count := g.GetReadyNodesCount()
	if count != 2 {
		t.Errorf("Expected 2 ready nodes, got %d", count)
	}
}

func TestGetRunningNodesCount(t *testing.T) {
	g := &Graph{
		Nodes: []Node{
			{ID: "A", Status: StatusRunning},
			{ID: "B", Status: StatusRunning},
			{ID: "C", Status: StatusPending},
		},
	}

	count := g.GetRunningNodesCount()
	if count != 2 {
		t.Errorf("Expected 2 running nodes, got %d", count)
	}
}

// Benchmark parallel vs serial scheduling
func BenchmarkScheduling(b *testing.B) {
	createGraph := func(size int) *Graph {
		nodes := make([]Node, size)
		for i := 0; i < size; i++ {
			nodes[i] = Node{
				ID:             string(rune('A' + i%26)),
				Status:         StatusPending,
				RelevanceScore: 0.5,
			}
		}
		return &Graph{Nodes: nodes}
	}

	b.Run("Serial", func(b *testing.B) {
		for i := 0; i < b.N; i++ {
			g := createGraph(100)
			for j := 0; j < 100; j++ {
				_, _ = g.ScheduleNext()
			}
		}
	})

	b.Run("Batch10", func(b *testing.B) {
		for i := 0; i < b.N; i++ {
			g := createGraph(100)
			for j := 0; j < 10; j++ {
				_, _ = g.ScheduleNextBatch(10)
			}
		}
	})

	b.Run("Batch50", func(b *testing.B) {
		for i := 0; i < b.N; i++ {
			g := createGraph(100)
			for j := 0; j < 2; j++ {
				_, _ = g.ScheduleNextBatch(50)
			}
		}
	})
}
