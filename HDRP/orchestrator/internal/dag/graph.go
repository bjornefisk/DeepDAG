package dag

import (
	"errors"
	"fmt"
)

// Node represents a step in the processing pipeline.
type Node struct {
	ID     string            `json:"id"`
	Type   string            `json:"type"`
	Config map[string]string `json:"config"`
}

// Edge represents a directed connection between two nodes.
type Edge struct {
	From string `json:"from"`
	To   string `json:"to"`
}

// Graph represents the DAG structure.
type Graph struct {
	ID    string `json:"id"`
	Nodes []Node `json:"nodes"`
	Edges []Edge `json:"edges"`
}

// ValidationError represents an aggregation of validation issues.
type ValidationError struct {
	Errors []string
}

func (v *ValidationError) Error() string {
	if len(v.Errors) == 0 {
		return ""
	}
	return fmt.Sprintf("graph validation failed with %d errors: %v", len(v.Errors), v.Errors[0])
}

// Validate performs structural and semantic validation on the Graph.
// It ensures the graph is a valid DAG (Directed Acyclic Graph).
func (g *Graph) Validate() error {
	var errs []string

	if len(g.Nodes) == 0 {
		return errors.New("graph is empty: no nodes defined")
	}

	// 1. Check for unique Node IDs and existence
	nodeMap := make(map[string]bool)
	for _, n := range g.Nodes {
		if n.ID == "" {
			errs = append(errs, "found node with empty ID")
			continue
		}
		if nodeMap[n.ID] {
			errs = append(errs, fmt.Sprintf("duplicate node ID: %s", n.ID))
		}
		nodeMap[n.ID] = true

		if n.Type == "" {
			errs = append(errs, fmt.Sprintf("node %s has no type specified", n.ID))
		}
	}

	// 2. Check Edges validity
	adj := make(map[string][]string)
	for _, e := range g.Edges {
		if !nodeMap[e.From] {
			errs = append(errs, fmt.Sprintf("edge source node '%s' does not exist", e.From))
		}
		if !nodeMap[e.To] {
			errs = append(errs, fmt.Sprintf("edge target node '%s' does not exist", e.To))
		}
		if e.From == e.To {
			errs = append(errs, fmt.Sprintf("self-loop detected on node '%s'", e.From))
		}
		
		// Build adjacency list only for valid nodes to avoid panic/issues later
		if nodeMap[e.From] && nodeMap[e.To] {
			adj[e.From] = append(adj[e.From], e.To)
		}
	}

	if len(errs) > 0 {
		return &ValidationError{Errors: errs}
	}

	// 3. Cycle Detection
	if err := checkCycles(g.Nodes, adj); err != nil {
		return err
	}

	return nil
}

// checkCycles uses DFS to detect cycles in the graph.
func checkCycles(nodes []Node, adj map[string][]string) error {
	visited := make(map[string]bool)
	recursionStack := make(map[string]bool)

	for _, n := range nodes {
		if visited[n.ID] {
			continue
		}
		if hasCycle(n.ID, adj, visited, recursionStack) {
			return fmt.Errorf("cycle detected starting at or involving node '%s'", n.ID)
		}
	}
	return nil
}

func hasCycle(nodeID string, adj map[string][]string, visited, stack map[string]bool) bool {
	visited[nodeID] = true
	stack[nodeID] = true

	for _, neighbor := range adj[nodeID] {
		if !visited[neighbor] {
			if hasCycle(neighbor, adj, visited, stack) {
				return true
			}
		} else if stack[neighbor] {
			// If neighbor is in the current recursion stack, we found a cycle
			return true
		}
	}

	stack[nodeID] = false
	return false
}
