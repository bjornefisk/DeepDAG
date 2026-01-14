package dag

import (
	"errors"
	"fmt"
	"log"
	"strings"

	"hdrp/internal/storage"
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
	StatusRetrying  Status = "RETRYING"  // Node is waiting to retry after failure
	StatusCancelled Status = "CANCELLED"
)

// Node represents a step in the processing pipeline.
type Node struct {
	ID             string            `json:"id"`
	Type           string            `json:"type"`
	Config         map[string]string `json:"config"`
	Status         Status            `json:"status"`
	RelevanceScore float64           `json:"relevance_score"`
	Depth          int               `json:"depth"`
	RetryCount     int               `json:"retry_count"`      // Number of retry attempts made
	LastError      string            `json:"last_error,omitempty"` // Last error encountered
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

// Signal represents an event or message that can trigger graph modifications.
type Signal struct {
	Type    string            `json:"type"`
	Source  string            `json:"source"`
	Payload map[string]string `json:"payload"`
}

// Graph represents the DAG structure.
type Graph struct {
	ID       string            `json:"id"`
	Nodes    []Node            `json:"nodes"`
	Edges    []Edge            `json:"edges"`
	Status   Status            `json:"status"`
	Metadata map[string]string `json:"metadata"`
	
	// Storage backend for persistence (nil for in-memory only)
	storage storage.Storage `json:"-"`
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

// ReceiveSignal processes incoming signals and modifies the graph accordingly.
func (g *Graph) ReceiveSignal(sig Signal) error {
	switch sig.Type {
	case "ENTITY_DISCOVERY":
		return g.handleEntityDiscovery(sig)
	default:
		// Ignore unknown signals
		return nil
	}
}

// handleEntityDiscovery processes entity discovery signals.
func (g *Graph) handleEntityDiscovery(sig Signal) error {
	entity, ok := sig.Payload["entity"]
	if !ok {
		return errors.New("entity discovery signal missing 'entity' in payload")
	}

	// Check relevance
	goal, ok := g.Metadata["goal"]
	if !ok {
		return errors.New("graph missing 'goal' in metadata")
	}
	if !strings.Contains(goal, entity) && !strings.Contains(entity, goal) {
		return fmt.Errorf("entity '%s' not relevant to goal '%s'", entity, goal)
	}

	// Check for duplicates
	for _, n := range g.Nodes {
		if n.Type == "agent" && n.Config["entity"] == entity {
			return nil // Duplicate, ignore
		}
	}

	// Check depth limit
	sourceNode := g.findNode(sig.Source)
	if sourceNode == nil {
		return fmt.Errorf("source node '%s' not found", sig.Source)
	}
	if sourceNode.Depth >= 1 {
		return errors.New("max expansion depth reached")
	}

	// Add node
	newNodeID := fmt.Sprintf("%s-%s", sig.Source, entity)
	newNode := Node{
		ID:             newNodeID,
		Type:           "agent",
		Config:         map[string]string{"entity": entity},
		Status:         StatusCreated,
		RelevanceScore: 1.0, // Placeholder
		Depth:          sourceNode.Depth + 1,
	}
	g.Nodes = append(g.Nodes, newNode)

	// Persist node
	if err := g.persistNode(&newNode); err != nil {
		return fmt.Errorf("failed to persist new node: %w", err)
	}

	// Log to WAL
	if g.storage != nil {
		payload := &storage.AddNodePayload{
			Node: storage.NodeState{
				NodeID:         newNode.ID,
				Type:           newNode.Type,
				Config:         newNode.Config,
				Status:         string(newNode.Status),
				RelevanceScore: newNode.RelevanceScore,
				Depth:          newNode.Depth,
				RetryCount:     newNode.RetryCount,
				LastError:      newNode.LastError,
			},
		}
		if err := g.storage.LogMutation(g.ID, storage.MutationAddNode, payload); err != nil {
			log.Printf("[DAG] Warning: failed to log add node mutation: %v", err)
		}
	}

	// Add edge
	newEdge := Edge{From: sig.Source, To: newNodeID}
	g.Edges = append(g.Edges, newEdge)

	// Persist edge
	if err := g.persistEdge(sig.Source, newNodeID); err != nil {
		return fmt.Errorf("failed to persist new edge: %w", err)
	}

	// Log to WAL
	if g.storage != nil {
		payload := &storage.AddEdgePayload{
			From: sig.Source,
			To:   newNodeID,
		}
		if err := g.storage.LogMutation(g.ID, storage.MutationAddEdge, payload); err != nil {
			log.Printf("[DAG] Warning: failed to log add edge mutation: %v", err)
		}
	}

	// Evaluate readiness
	if err := g.EvaluateReadiness(); err != nil {
		return err
	}

	// Resume if succeeded
	if g.Status == StatusSucceeded {
		g.Status = StatusRunning
	}

	return nil
}

// findNode finds a node by ID.
func (g *Graph) findNode(id string) *Node {
	for i := range g.Nodes {
		if g.Nodes[i].ID == id {
			return &g.Nodes[i]
		}
	}
	return nil
}

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

// NewGraphWithStorage creates a graph with a storage backend.
// If store is nil, the graph operates in-memory only.
func NewGraphWithStorage(id string, store storage.Storage) *Graph {
	return &Graph{
		ID:       id,
		Nodes:    []Node{},
		Edges:    []Edge{},
		Status:   StatusCreated,
		Metadata: make(map[string]string),
		storage:  store,
	}
}

// SetStorage attaches a storage backend to an existing graph.
func (g *Graph) SetStorage(store storage.Storage) {
	g.storage = store
}

// persistGraphState saves the graph metadata to storage if available.
func (g *Graph) persistGraphState() error {
	if g.storage == nil {
		return nil // No persistence configured
	}

	graphState := &storage.GraphState{
		ID:       g.ID,
		Status:   string(g.Status),
		Metadata: g.Metadata,
	}

	return g.storage.SaveGraph(graphState)
}

// persistNode saves a node to storage if available.
func (g *Graph) persistNode(node *Node) error {
	if g.storage == nil {
		return nil
	}

	nodeState := &storage.NodeState{
		NodeID:         node.ID,
		Type:           node.Type,
		Config:         node.Config,
		Status:         string(node.Status),
		RelevanceScore: node.RelevanceScore,
		Depth:          node.Depth,
		RetryCount:     node.RetryCount,
		LastError:      node.LastError,
	}

	return g.storage.SaveNode(g.ID, nodeState)
}

// persistEdge saves an edge to storage if available.
func (g *Graph) persistEdge(from, to string) error {
	if g.storage == nil {
		return nil
	}

	return g.storage.SaveEdge(g.ID, from, to)
}

// LoadFromStorage restores graph state from storage.
func (g *Graph) LoadFromStorage(graphID string) error {
	if g.storage == nil {
		return fmt.Errorf("no storage backend configured")
	}

	// Try crash recovery first
	recovered, err := g.storage.RecoverGraph(graphID)
	if err != nil {
		return fmt.Errorf("recovery failed: %w", err)
	}

	if recovered == nil {
		return fmt.Errorf("no stored state found for graph %s", graphID)
	}

	// Restore graph metadata
	g.ID = recovered.Graph.ID
	g.Status = Status(recovered.Graph.Status)
	g.Metadata = recovered.Graph.Metadata

	// Restore nodes
	g.Nodes = make([]Node, 0, len(recovered.Nodes))
	for _, nodeState := range recovered.Nodes {
		g.Nodes = append(g.Nodes, Node{
			ID:             nodeState.NodeID,
			Type:           nodeState.Type,
			Config:         nodeState.Config,
			Status:         Status(nodeState.Status),
			RelevanceScore: nodeState.RelevanceScore,
			Depth:          nodeState.Depth,
			RetryCount:     nodeState.RetryCount,
			LastError:      nodeState.LastError,
		})
	}

	// Restore edges
	g.Edges = make([]Edge, 0, len(recovered.Edges))
	for _, edgeState := range recovered.Edges {
		g.Edges = append(g.Edges, Edge{
			From: edgeState.From,
			To:   edgeState.To,
		})
	}

	return nil
}

