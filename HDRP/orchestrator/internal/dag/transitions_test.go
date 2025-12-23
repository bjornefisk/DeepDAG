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
