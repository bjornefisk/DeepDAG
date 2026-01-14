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
		return target == StatusPending || target == StatusRunning || target == StatusCancelled || target == StatusBlocked
	case StatusBlocked:
		return target == StatusPending || target == StatusCancelled
	case StatusPending:
		return target == StatusRunning || target == StatusCancelled || target == StatusFailed
	case StatusRunning:
		return target == StatusSucceeded || target == StatusFailed || target == StatusCancelled || target == StatusRetrying
	case StatusFailed:
		// Allow retries from failed to retrying or cancelled
		return target == StatusRetrying || target == StatusCancelled
	case StatusRetrying:
		// From retrying, can go back to running (retry attempt) or to failed (retries exhausted)
		return target == StatusRunning || target == StatusFailed || target == StatusCancelled
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

// EvaluateReadiness scans the graph and updates node statuses based on dependencies.
// It moves eligible nodes to PENDING and unsatisfied ones to BLOCKED.
func (g *Graph) EvaluateReadiness() error {
	// Build a map of node ID to Status for quick lookup
	nodeStatus := make(map[string]Status)
	for _, n := range g.Nodes {
		nodeStatus[n.ID] = n.Status
	}

	// Build reverse adjacency list (Child -> Parents)
	parents := make(map[string][]string)
	for _, e := range g.Edges {
		parents[e.To] = append(parents[e.To], e.From)
	}

	// Iterate and update statuses
	for _, n := range g.Nodes {
		// Only evaluate nodes waiting to start
		if n.Status != StatusCreated && n.Status != StatusBlocked {
			continue
		}

		// Check if all parents have succeeded OR are in a retryable state
		// This enables graceful degradation - children can proceed even if parent is retrying
		allParentsSucceeded := true
		hasRetryingParent := false
		for _, parentID := range parents[n.ID] {
			parentStatus := nodeStatus[parentID]
			if parentStatus == StatusRetrying {
				hasRetryingParent = true
				allParentsSucceeded = false
				break
			}
			if parentStatus != StatusSucceeded {
				allParentsSucceeded = false
				break
			}
		}

		var targetStatus Status
		if allParentsSucceeded {
			targetStatus = StatusPending
		} else if hasRetryingParent {
			// Keep blocked while parent is retrying
			targetStatus = StatusBlocked
		} else {
			targetStatus = StatusBlocked
		}

		// Only update if state changes to avoid unnecessary writes/locks in real DB
		if n.Status != targetStatus {
			if err := g.SetNodeStatus(n.ID, targetStatus); err != nil {
				return fmt.Errorf("failed to update node %s readiness: %w", n.ID, err)
			}
		}
	}
	return nil
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
