package dag

import (
	"testing"
)

func TestStatusTransitions(t *testing.T) {
	tests := []struct {
		name    string
		initial Status
		target  Status
		wantErr bool
	}{
		{"Created to Running", StatusCreated, StatusRunning, false},
		{"Created to Pending", StatusCreated, StatusPending, false},
		{"Pending to Running", StatusPending, StatusRunning, false},
		{"Running to Succeeded", StatusRunning, StatusSucceeded, false},
		{"Running to Failed", StatusRunning, StatusFailed, false},
		{"Succeeded to Running", StatusSucceeded, StatusRunning, true}, // Terminal
		{"Failed to Running", StatusFailed, StatusRunning, false},    // Retry
		{"Created to Succeeded", StatusCreated, StatusSucceeded, true}, // Must run first
		{"Running to Cancelled", StatusRunning, StatusCancelled, false},
		{"Cancelled to Created", StatusCancelled, StatusCreated, false}, // Reset
		{"Created to Blocked", StatusCreated, StatusBlocked, false},
		{"Blocked to Pending", StatusBlocked, StatusPending, false},
		{"Blocked to Cancelled", StatusBlocked, StatusCancelled, false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			sm := NewStateMachine(tt.initial)
			err := sm.Transition(tt.target)
			if (err != nil) != tt.wantErr {
				t.Errorf("Transition() error = %v, wantErr %v", err, tt.wantErr)
			}
			if err == nil && sm.Status() != tt.target {
				t.Errorf("Expected status %s, got %s", tt.target, sm.Status())
			}
		})
	}
}

func TestEvaluateReadiness(t *testing.T) {
	t.Run("Simple Dependency Chain", func(t *testing.T) {
		// A -> B
		g := &Graph{
			Nodes: []Node{
				{ID: "A", Status: StatusCreated},
				{ID: "B", Status: StatusCreated},
			},
			Edges: []Edge{
				{From: "A", To: "B"},
			},
		}

		// Initial Check
		if err := g.EvaluateReadiness(); err != nil {
			t.Fatalf("EvaluateReadiness failed: %v", err)
		}
		if g.Nodes[0].Status != StatusPending {
			t.Errorf("Node A should be Pending (no deps), got %s", g.Nodes[0].Status)
		}
		if g.Nodes[1].Status != StatusBlocked {
			t.Errorf("Node B should be Blocked (waiting on A), got %s", g.Nodes[1].Status)
		}

		// Complete A
		g.Nodes[0].Status = StatusSucceeded
		if err := g.EvaluateReadiness(); err != nil {
			t.Fatalf("EvaluateReadiness failed: %v", err)
		}
		if g.Nodes[1].Status != StatusPending {
			t.Errorf("Node B should be Pending (A finished), got %s", g.Nodes[1].Status)
		}
	})

	t.Run("Diamond Dependency", func(t *testing.T) {
		// A -> B, A -> C, B -> D, C -> D
		g := &Graph{
			Nodes: []Node{
				{ID: "A", Status: StatusSucceeded},
				{ID: "B", Status: StatusSucceeded},
				{ID: "C", Status: StatusRunning}, // C is not done yet
				{ID: "D", Status: StatusCreated},
			},
			Edges: []Edge{
				{From: "A", To: "B"}, {From: "A", To: "C"},
				{From: "B", To: "D"}, {From: "C", To: "D"},
			},
		}

		// Check D blocked by C
		if err := g.EvaluateReadiness(); err != nil {
			t.Fatalf("EvaluateReadiness failed: %v", err)
		}
		if g.Nodes[3].ID != "D" {
			t.Fatal("Node D index mismatch")
		}
		if g.Nodes[3].Status != StatusBlocked {
			t.Errorf("Node D should be Blocked (C running), got %s", g.Nodes[3].Status)
		}

		// Complete C
		g.Nodes[2].Status = StatusSucceeded
		if err := g.EvaluateReadiness(); err != nil {
			t.Fatalf("EvaluateReadiness failed: %v", err)
		}
		if g.Nodes[3].Status != StatusPending {
			t.Errorf("Node D should be Pending (all parents succeeded), got %s", g.Nodes[3].Status)
		}
	})
}

func TestGraphStatusTransitions(t *testing.T) {
	g := &Graph{
		ID:     "test-graph",
		Status: StatusCreated,
		Nodes: []Node{
			{ID: "node1", Status: StatusCreated},
		},
	}

	// Valid graph transition
	if err := g.SetStatus(StatusRunning); err != nil {
		t.Errorf("Failed valid graph transition: %v", err)
	}

	// Valid node transition
	if err := g.SetNodeStatus("node1", StatusRunning); err != nil {
		t.Errorf("Failed valid node transition: %v", err)
	}

	// Invalid node transition
	if err := g.SetNodeStatus("node1", StatusCreated); err == nil {
		t.Error("Expected error for invalid node transition (Running -> Created), got nil")
	}

	// Node not found
	if err := g.SetNodeStatus("missing", StatusRunning); err == nil {
		t.Error("Expected error for missing node, got nil")
	}
}
