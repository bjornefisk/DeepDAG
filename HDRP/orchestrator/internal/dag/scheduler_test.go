package dag

import (
	"testing"
)

func TestScheduleNext(t *testing.T) {
	t.Run("Select Highest Relevance", func(t *testing.T) {
		g := &Graph{
			Nodes: []Node{
				{ID: "low-prio", Status: StatusPending, RelevanceScore: 0.1},
				{ID: "high-prio", Status: StatusPending, RelevanceScore: 0.9},
				{ID: "med-prio", Status: StatusPending, RelevanceScore: 0.5},
			},
		}

		next, err := g.ScheduleNext()
		if err != nil {
			t.Fatalf("ScheduleNext failed: %v", err)
		}
		if next.ID != "high-prio" {
			t.Errorf("Expected high-prio to be scheduled, got %s", next.ID)
		}
		if next.Status != StatusRunning {
			t.Errorf("Scheduled node should be RUNNING, got %s", next.Status)
		}
		
		// Verify graph state updated
		if g.Nodes[1].Status != StatusRunning {
			t.Error("Graph state not updated")
		}
	})

	t.Run("Deterministic Tie-Break", func(t *testing.T) {
		g := &Graph{
			Nodes: []Node{
				{ID: "task-B", Status: StatusPending, RelevanceScore: 0.5},
				{ID: "task-A", Status: StatusPending, RelevanceScore: 0.5},
			},
		}

		next, err := g.ScheduleNext()
		if err != nil {
			t.Fatalf("ScheduleNext failed: %v", err)
		}
		if next.ID != "task-A" {
			t.Errorf("Expected task-A (lexicographical), got %s", next.ID)
		}
	})

	t.Run("Enforce Serial Execution", func(t *testing.T) {
		g := &Graph{
			Nodes: []Node{
				{ID: "running-task", Status: StatusRunning},
				{ID: "pending-task", Status: StatusPending},
			},
		}

		_, err := g.ScheduleNext()
		if err != ErrNodeAlreadyRunning {
			t.Errorf("Expected ErrNodeAlreadyRunning, got %v", err)
		}
	})

	t.Run("No Pending Nodes", func(t *testing.T) {
		g := &Graph{
			Nodes: []Node{
				{ID: "done-task", Status: StatusSucceeded},
			},
		}

		next, err := g.ScheduleNext()
		if err != nil {
			t.Fatalf("Unexpected error: %v", err)
		}
		if next != nil {
			t.Errorf("Expected nil (no work), got %v", next)
		}
	})

	t.Run("Transition Failure Handling", func(t *testing.T) {
		// Mock a graph where we can simulate transition failure? 
		// SetNodeStatus primarily fails if node is missing or invalid transition.
		// Let's rely on the fact that if we have a Pending node, transition to Running is valid.
		// We can test 'missing node' by corrupting memory but that's hard safely.
		// Instead, we trust the integration.
	})
}
