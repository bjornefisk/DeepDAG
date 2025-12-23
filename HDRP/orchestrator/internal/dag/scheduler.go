package dag

import (
	"errors"
	"fmt"
	"sort"
)

var (
	ErrNodeAlreadyRunning = errors.New("scheduler violation: a node is already in RUNNING state")
)

// ScheduleNext acts as a strict serial scheduler.
// It selects exactly one node from the PENDING pool to transition to RUNNING.
//
// Selection Policy:
// 1. Highest RelevanceScore (Greedy)
// 2. Lowest ID (Deterministic Tie-breaker)
//
// Constraints:
// - Returns ErrNodeAlreadyRunning if any node is currently RUNNING.
// - Returns nil if no nodes are PENDING.
func (g *Graph) ScheduleNext() (*Node, error) {
	// 1. Enforce Serial Execution Constraint
	// We scan for any currently running nodes. In a distributed system,
	// this would require a distributed lock or lease, but for this MVP
	// in-memory check is sufficient.
	for _, n := range g.Nodes {
		if n.Status == StatusRunning {
			return nil, ErrNodeAlreadyRunning
		}
	}

	// 2. Identify Candidates
	var candidates []*Node
	for i := range g.Nodes {
		if g.Nodes[i].Status == StatusPending {
			candidates = append(candidates, &g.Nodes[i])
		}
	}

	if len(candidates) == 0 {
		return nil, nil // No work available
	}

	// 3. Apply Selection Policy
	// Sort stability is crucial for deterministic replayability.
	sort.Slice(candidates, func(i, j int) bool {
		// Primary: High relevance first
		if candidates[i].RelevanceScore != candidates[j].RelevanceScore {
			return candidates[i].RelevanceScore > candidates[j].RelevanceScore
		}
		// Secondary: Lexicographical ID for determinism
		return candidates[i].ID < candidates[j].ID
	})

	selected := candidates[0]

	// 4. Atomic Transition (Logical)
	// We perform the state transition immediately to reserve this node.
	if err := g.SetNodeStatus(selected.ID, StatusRunning); err != nil {
		return nil, fmt.Errorf("failed to transition scheduled node %s: %w", selected.ID, err)
	}

	// Return a copy of the scheduled node with updated status
	// (SetNodeStatus updated the underlying array, but our pointer 'selected' matches that memory)
	return selected, nil
}
