package dag

import (
	"errors"
	"fmt"
	"sort"
)

var (
	ErrNodeAlreadyRunning = errors.New("scheduler violation: a node is already in RUNNING state")
)

// ScheduleNext acts as a compatibility wrapper for the legacy serial scheduler.
// It selects exactly one node from the PENDING pool to transition to RUNNING.
// For parallel execution, use ScheduleNextBatch instead.
//
// Selection Policy:
// 1. Highest RelevanceScore (Greedy)
// 2. Lowest ID (Deterministic Tie-breaker)
func (g *Graph) ScheduleNext() (*Node, error) {
	batch, err := g.ScheduleNextBatch(1)
	if err != nil {
		return nil, err
	}
	if len(batch) == 0 {
		return nil, nil
	}
	return batch[0], nil
}

// ScheduleNextBatch selects up to maxNodes from the PENDING pool for parallel execution.
// It returns nodes that have all dependencies satisfied and can run concurrently.
//
// Selection Policy:
// 1. Only selects PENDING nodes (not BLOCKED or already RUNNING)
// 2. Sorts by RelevanceScore (descending) then ID (ascending) for determinism
// 3. Returns up to maxNodes, or fewer if not enough eligible nodes exist
// 4. Transitions selected nodes to RUNNING state atomically
//
// Returns:
// - A slice of nodes ready for execution (may be empty)
// - An error if state transition fails
func (g *Graph) ScheduleNextBatch(maxNodes int) ([]*Node, error) {
	if maxNodes <= 0 {
		maxNodes = 1
	}

	// 1. Identify Candidates
	var candidates []*Node
	for i := range g.Nodes {
		if g.Nodes[i].Status == StatusPending {
			candidates = append(candidates, &g.Nodes[i])
		}
	}

	if len(candidates) == 0 {
		return nil, nil // No work available
	}

	// 2. Apply Selection Policy
	// Sort stability is crucial for deterministic replayability.
	sort.Slice(candidates, func(i, j int) bool {
		// Primary: High relevance first
		if candidates[i].RelevanceScore != candidates[j].RelevanceScore {
			return candidates[i].RelevanceScore > candidates[j].RelevanceScore
		}
		// Secondary: Lexicographical ID for determinism
		return candidates[i].ID < candidates[j].ID
	})

	// 3. Select top N nodes
	selectCount := maxNodes
	if selectCount > len(candidates) {
		selectCount = len(candidates)
	}
	
	selected := candidates[:selectCount]

	// 4. Atomic Transition
	// Transition all selected nodes to RUNNING state
	var transitioned []*Node
	for _, node := range selected {
		if err := g.SetNodeStatus(node.ID, StatusRunning); err != nil {
			// Rollback: Set already-transitioned nodes back to PENDING
			for _, rollbackNode := range transitioned {
				_ = g.SetNodeStatus(rollbackNode.ID, StatusPending)
			}
			return nil, fmt.Errorf("failed to transition scheduled node %s: %w", node.ID, err)
		}
		transitioned = append(transitioned, node)
	}

	return transitioned, nil
}

// GetReadyNodesCount returns the number of nodes currently in PENDING state.
// This is useful for determining how many nodes can be scheduled.
func (g *Graph) GetReadyNodesCount() int {
	count := 0
	for i := range g.Nodes {
		if g.Nodes[i].Status == StatusPending {
			count++
		}
	}
	return count
}

// GetRunningNodesCount returns the number of nodes currently in RUNNING state.
func (g *Graph) GetRunningNodesCount() int {
	count := 0
	for i := range g.Nodes {
		if g.Nodes[i].Status == StatusRunning {
			count++
		}
	}
	return count
}
