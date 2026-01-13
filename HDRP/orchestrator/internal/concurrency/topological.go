package concurrency

import (
	"fmt"
)

// TopologicalSorter provides utilities for DAG analysis and topological ordering.
type TopologicalSorter struct {
	nodes        []string
	adjacency    map[string][]string // node -> children
	inDegree     map[string]int      // node -> number of dependencies
}

// NewTopologicalSorter creates a sorter from a graph structure.
func NewTopologicalSorter(nodes []string, edges [][2]string) *TopologicalSorter {
	ts := &TopologicalSorter{
		nodes:     nodes,
		adjacency: make(map[string][]string),
		inDegree:  make(map[string]int),
	}

	// Initialize in-degree
	for _, node := range nodes {
		ts.inDegree[node] = 0
	}

	// Build adjacency list and in-degree count
	for _, edge := range edges {
		from, to := edge[0], edge[1]
		ts.adjacency[from] = append(ts.adjacency[from], to)
		ts.inDegree[to]++
	}

	return ts
}

// GetReadyNodes returns all nodes with no unsatisfied dependencies (in-degree = 0).
func (ts *TopologicalSorter) GetReadyNodes() []string {
	var ready []string
	for node, degree := range ts.inDegree {
		if degree == 0 {
			ready = append(ready, node)
		}
	}
	return ready
}

// MarkCompleted marks a node as completed and updates in-degrees of dependent nodes.
// Returns the list of nodes that became ready as a result.
func (ts *TopologicalSorter) MarkCompleted(nodeID string) ([]string, error) {
	if _, exists := ts.inDegree[nodeID]; !exists {
		return nil, fmt.Errorf("node %s not found", nodeID)
	}

	// Remove this node from consideration (set to -1 to indicate completion)
	ts.inDegree[nodeID] = -1

	// Decrease in-degree for all children
	var newlyReady []string
	for _, child := range ts.adjacency[nodeID] {
		if ts.inDegree[child] > 0 {
			ts.inDegree[child]--
			if ts.inDegree[child] == 0 {
				newlyReady = append(newlyReady, child)
			}
		}
	}

	return newlyReady, nil
}

// GetLevels returns nodes grouped by their topological level.
// Level 0 contains nodes with no dependencies, level 1 contains nodes
// that only depend on level 0, etc.
func (ts *TopologicalSorter) GetLevels() ([][]string, error) {
	// Create a copy of in-degree to avoid mutation
	inDegreeCopy := make(map[string]int)
	for k, v := range ts.inDegree {
		if v >= 0 { // Only copy uncompleted nodes
			inDegreeCopy[k] = v
		}
	}

	var levels [][]string
	
	for len(inDegreeCopy) > 0 {
		// Find all nodes with in-degree 0
		var currentLevel []string
		for node, degree := range inDegreeCopy {
			if degree == 0 {
				currentLevel = append(currentLevel, node)
			}
		}

		if len(currentLevel) == 0 {
			// Cycle detected or no progress possible
			return nil, fmt.Errorf("cycle detected or invalid graph state")
		}

		levels = append(levels, currentLevel)

		// Remove current level nodes and update in-degrees
		for _, node := range currentLevel {
			delete(inDegreeCopy, node)
			for _, child := range ts.adjacency[node] {
				if deg, exists := inDegreeCopy[child]; exists {
					inDegreeCopy[child] = deg - 1
				}
			}
		}
	}

	return levels, nil
}

// Clone creates a deep copy of the topological sorter.
func (ts *TopologicalSorter) Clone() *TopologicalSorter {
	clone := &TopologicalSorter{
		nodes:     make([]string, len(ts.nodes)),
		adjacency: make(map[string][]string),
		inDegree:  make(map[string]int),
	}

	copy(clone.nodes, ts.nodes)

	for k, v := range ts.adjacency {
		clone.adjacency[k] = make([]string, len(v))
		copy(clone.adjacency[k], v)
	}

	for k, v := range ts.inDegree {
		clone.inDegree[k] = v
	}

	return clone
}

// IsComplete returns true if all nodes have been marked as completed.
func (ts *TopologicalSorter) IsComplete() bool {
	for _, degree := range ts.inDegree {
		if degree >= 0 {
			return false
		}
	}
	return true
}

// GetDependencies returns the list of nodes that the given node depends on.
func (ts *TopologicalSorter) GetDependencies(nodeID string) []string {
	var deps []string
	for from, children := range ts.adjacency {
		for _, child := range children {
			if child == nodeID {
				deps = append(deps, from)
			}
		}
	}
	return deps
}
