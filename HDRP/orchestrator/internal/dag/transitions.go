package dag

import (
	"fmt"
	"sync"
)

// StateMachine manages status transitions for a Graph or Node.
// It ensures that transitions follow a valid lifecycle.
type StateMachine struct {
	mu     sync.RWMutex
	status Status
}

func NewStateMachine(initial Status) *StateMachine {
	if initial == "" {
		initial = StatusCreated
	}
	return &StateMachine{status: initial}
}

// Status returns the current status.
func (sm *StateMachine) Status() Status {
	sm.mu.RLock()
	defer sm.mu.RUnlock()
	return sm.status
}

// Transition attempts to move the state to target.
// It returns an error if the transition is invalid.
func (sm *StateMachine) Transition(target Status) error {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	if !isValidTransition(sm.status, target) {
		return fmt.Errorf("invalid status transition: %s -> %s", sm.status, target)
	}

	sm.status = target
	return nil
}

// isValidTransition defines the permitted state machine edges.
func isValidTransition(current, target Status) bool {
	if current == target {
		return true
	}

	switch current {
	case StatusCreated:
		return target == StatusPending || target == StatusRunning || target == StatusCancelled
	case StatusPending:
		return target == StatusRunning || target == StatusCancelled || target == StatusFailed
	case StatusRunning:
		return target == StatusSucceeded || target == StatusFailed || target == StatusCancelled
	case StatusFailed:
		// Allow retries from failed to running or pending
		return target == StatusRunning || target == StatusPending || target == StatusCancelled
	case StatusCancelled:
		// Cancelled is terminal for an execution attempt, but could be reset to Created
		return target == StatusCreated
	case StatusSucceeded:
		// Succeeded is terminal for a specific run
		return false
	default:
		return false
	}
}

// SetStatus is a helper for Graph to update its status and its nodes' statuses if necessary.
// In a real system, this might involve database updates.
func (g *Graph) SetStatus(s Status) error {
	// Simple validation for the graph level status
	// For MVP, we'll just check if it's a valid target from current
	if !isValidTransition(g.Status, s) {
		return fmt.Errorf("invalid graph status transition: %s -> %s", g.Status, s)
	}
	g.Status = s
	return nil
}

// SetNodeStatus updates a specific node's status.
func (g *Graph) SetNodeStatus(nodeID string, s Status) error {
	for i := range g.Nodes {
		if g.Nodes[i].ID == nodeID {
			if !isValidTransition(g.Nodes[i].Status, s) {
				return fmt.Errorf("invalid node status transition for %s: %s -> %s", nodeID, g.Nodes[i].Status, s)
			}
			g.Nodes[i].Status = s
			return nil
		}
	}
	return fmt.Errorf("node %s not found in graph", nodeID)
}
