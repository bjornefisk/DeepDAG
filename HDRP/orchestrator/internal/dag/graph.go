package dag

import (
	"errors"
	"fmt"
	"strings"
)

// Status represents the current execution state of a graph or node.
type Status string

const (
	StatusCreated   Status = "CREATED"
	StatusPending   Status = "PENDING"
	StatusRunning   Status = "RUNNING"
	StatusBlocked   Status = "BLOCKED"
	StatusSucceeded Status = "SUCCEEDED"
	StatusFailed    Status = "FAILED"
	StatusCancelled Status = "CANCELLED"
)

// Signal represents an external event or discovery that might affect the graph.
type Signal struct {
	Type    string            `json:"type"`
	Payload map[string]string `json:"payload"`
	Source  string            `json:"source"`
}

// Node represents a step in the processing pipeline.
type Node struct {
	ID             string            `json:"id"`
	Type           string            `json:"type"`
	Config         map[string]string `json:"config"`
	Status         Status            `json:"status"`
	RelevanceScore float64           `json:"relevance_score"`
}

// Validate ensures the node represents a single, atomic unit of work.
func (n *Node) Validate() error {
	forbiddenKeys := []string{"steps", "tasks", "pipeline", "subgraph", "batch"}
	
	for _, forbidden := range forbiddenKeys {
		if _, exists := n.Config[forbidden]; exists {
			return fmt.Errorf("node '%s' violates atomicity: config key '%s' implies composite/non-atomic behavior", n.ID, forbidden)
		}
	}
	return nil
}

// Edge represents a directed connection between two nodes.
type Edge struct {
	From string `json:"from"`
	To   string `json:"to"`
}

// Graph represents the DAG structure.
type Graph struct {
	ID       string            `json:"id"`
	Nodes    []Node            `json:"nodes"`
	Edges    []Edge            `json:"edges"`
	Status   Status            `json:"status"`
	Metadata map[string]string `json:"metadata"`
}

// ReceiveSignal processes an incoming signal.
func (g *Graph) ReceiveSignal(sig Signal) error {
	if sig.Type != "ENTITY_DISCOVERY" {
		return nil
	}

	entity, ok := sig.Payload["entity"]
	if !ok {
		return fmt.Errorf("signal payload missing 'entity'")
	}

	// MVP Relevance Check: Simple containment
	goal := g.Metadata["goal"]
	if goal != "" {
		// Check if entity is mentioned in goal or vice versa (simplistic MVP)
		isRelevant := strings.Contains(strings.ToLower(goal), strings.ToLower(entity)) ||
			strings.Contains(strings.ToLower(entity), strings.ToLower(goal))
		
		if !isRelevant {
			return fmt.Errorf("entity '%s' not relevant to goal '%s'", entity, goal)
		}
	}
	
	return g.addNodeForEntity(entity, sig.Source)
}

func (g *Graph) addNodeForEntity(entity, parentID string) error {
	// Generate deterministic ID for the new node
	cleanEntity := strings.ReplaceAll(strings.ToLower(entity), " ", "_")
	newNodeID := fmt.Sprintf("%s-sub-%s", parentID, cleanEntity)

	newNode := Node{
		ID:     newNodeID,
		Type:   "researcher_agent", // Default for expansion
		Status: StatusCreated,
		Config: map[string]string{
			"goal": fmt.Sprintf("Research sub-topic: %s", entity),
		},
		RelevanceScore: 1.0, 
	}

	g.Nodes = append(g.Nodes, newNode)
	g.Edges = append(g.Edges, Edge{
		From: parentID,
		To:   newNodeID,
	})

	return nil
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

		// Enforce Node Atomicity
		if err := n.Validate(); err != nil {
			errs = append(errs, err.Error())
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

	// 4. Max Depth Enforcement
	// We limit the graph to 3 layers to prevent complex, uncontrollable chains in this MVP.
	const MaxDepth = 3
	if err := checkDepth(g.Nodes, adj, MaxDepth); err != nil {
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

// checkDepth verifies that the longest path in the graph does not exceed the limit.
// It assumes the graph is acyclic (checkCycles must run first).
func checkDepth(nodes []Node, adj map[string][]string, limit int) error {
	memo := make(map[string]int)

	var getDepth func(string) int
	getDepth = func(id string) int {
		if d, ok := memo[id]; ok {
			return d
		}
		
		maxChildDepth := 0
		for _, neighbor := range adj[id] {
			d := getDepth(neighbor)
			if d > maxChildDepth {
				maxChildDepth = d
			}
		}
		
		depth := 1 + maxChildDepth
		memo[id] = depth
		return depth
	}

	for _, n := range nodes {
		if d := getDepth(n.ID); d > limit {
			return fmt.Errorf("graph exceeds max depth of %d layers", limit)
		}
	}
	return nil
}
