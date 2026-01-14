package executor

import (
	"context"
	"fmt"
	"log"
	"sync"

	"hdrp/internal/clients"
	"hdrp/internal/concurrency"
	"hdrp/internal/dag"
	"hdrp/internal/retry"
	"hdrp/internal/storage"

	pb "github.com/deepdag/hdrp/api/gen/services"
)

// DAGExecutor orchestrates concurrent DAG node execution.
type DAGExecutor struct {
	clients         *clients.ServiceClients
	maxWorkers      int
	config          *concurrency.Config
	rateLimiters    *concurrency.RateLimiterManager
	lockManager     *concurrency.LockManager
	retryPolicy     *retry.RetryPolicy
	circuitBreakers *retry.PerServiceBreakers
	checkpointStore retry.CheckpointStore
	retryMetrics    *retry.RetryMetrics
	storage         storage.Storage // Persistent storage for DAG state
	mu              sync.RWMutex
}

// ExecutionResult contains the final DAG execution outcome.
type ExecutionResult struct {
	GraphID        string
	Success        bool
	PartialSuccess bool              // True if some nodes succeeded but not all
	SucceededNodes []string          // List of successful node IDs
	FailedNodes    map[string]string // nodeID -> error message
	FinalReport    string
	ArtifactURI    string
	ErrorMessage   string
	RetryMetrics   *retry.RetryMetrics // Retry statistics
}

// NodeResult contains a single node's execution outcome.
type NodeResult struct {
	NodeID  string
	Success bool
	Data    interface{} // Node-specific output: claims, verification results, etc.
	Error   error
}

// NewDAGExecutor creates a DAG executor with the specified worker pool size.
// If maxWorkers <= 0, uses default from configuration.
func NewDAGExecutor(clients *clients.ServiceClients, maxWorkers int) *DAGExecutor {
	config := concurrency.LoadConfig()
	
	if maxWorkers <= 0 {
		maxWorkers = config.MaxWorkers
	}

	// Initialize lock manager
	lockManager, err := concurrency.NewLockManager(config)
	if err != nil {
		log.Printf("[DAGExecutor] Warning: failed to initialize lock manager: %v", err)
		// Continue with nil lock manager - will skip distributed locking
	}

	// Initialize checkpoint store
	checkpointStore, err := retry.NewFileCheckpointStore("./checkpoints")
	if err != nil {
		log.Printf("[DAGExecutor] Warning: failed to initialize checkpoint store: %v", err)
		checkpointStore = retry.NewInMemoryCheckpointStore()
	}

	// Initialize storage for DAG persistence
	store, err := storage.NewSQLiteStorage()
	if err != nil {
		log.Printf("[DAGExecutor] Warning: failed to initialize storage: %v. Running in-memory only.", err)
		store = nil
	}

	executor := &DAGExecutor{
		clients:         clients,
		maxWorkers:      maxWorkers,
		config:          config,
		rateLimiters:    concurrency.NewRateLimiterManager(config),
		lockManager:     lockManager,
		retryPolicy:     retry.DefaultPolicy(),
		circuitBreakers: retry.NewPerServiceBreakers(),
		checkpointStore: checkpointStore,
		retryMetrics:    retry.NewRetryMetrics(),
		storage:         store,
	}

	if store != nil {
		log.Printf("[DAGExecutor] Persistent storage enabled")
	}

	return executor
}

// Execute runs the DAG to completion with dependency-aware parallel scheduling.
func (e *DAGExecutor) Execute(ctx context.Context, graph *dag.Graph, runID string) (*ExecutionResult, error) {
	log.Printf("[Executor] Starting execution of graph %s with max %d workers", graph.ID, e.maxWorkers)

	// Attach storage to graph if available
	if e.storage != nil {
		graph.SetStorage(e.storage)
		
		// Persist initial graph state
		if err := e.persistInitialGraph(graph); err != nil {
			log.Printf("[Executor] Warning: failed to persist initial graph: %v", err)
		}
	}

	if err := graph.Validate(); err != nil {
		return nil, fmt.Errorf("graph validation failed: %w", err)
	}

	if err := graph.SetStatus(dag.StatusRunning); err != nil {
		return nil, fmt.Errorf("failed to set graph status: %w", err)
	}

	if err := graph.EvaluateReadiness(); err != nil {
		return nil, fmt.Errorf("failed to evaluate readiness: %w", err)
	}

	nodeResults := make(map[string]*NodeResult)
	var resultsMu sync.RWMutex

	// Channel for node completion notifications
	resultChan := make(chan *NodeResult, e.maxWorkers)
	defer close(resultChan)

	// Track number of nodes currently executing
	pendingCount := 0
	
	// Execution loop
	for {
		select {
		case <-ctx.Done():
			return nil, fmt.Errorf("execution cancelled: %w", ctx.Err())
		default:
		}

		// Schedule a batch of ready nodes
		availableSlots := e.maxWorkers - pendingCount
		if availableSlots > 0 {
			batch, err := graph.ScheduleNextBatch(availableSlots)
			if err != nil {
				return nil, fmt.Errorf("scheduling failed: %w", err)
			}

			// Launch goroutines for each scheduled node
			for _, node := range batch {
				pendingCount++
				go e.executeNodeAsync(ctx, node, graph, nodeResults, &resultsMu, runID, resultChan)
			}
		}

		// Wait for at least one node to complete if any are pending
		if pendingCount > 0 {
			select {
			case result := <-resultChan:
				pendingCount--
				
				// Store result
				resultsMu.Lock()
				nodeResults[result.NodeID] = result
				resultsMu.Unlock()

				// Update graph state
				var newStatus dag.Status
				if result.Success {
					newStatus = dag.StatusSucceeded
				} else {
					newStatus = dag.StatusFailed
					log.Printf("[Executor] Node %s failed: %v", result.NodeID, result.Error)
				}

				if err := graph.SetNodeStatus(result.NodeID, newStatus); err != nil {
					return nil, fmt.Errorf("failed to update node status: %w", err)
				}

				// Re-evaluate readiness to unblock dependent nodes
				if err := graph.EvaluateReadiness(); err != nil {
					return nil, fmt.Errorf("failed to re-evaluate readiness: %w", err)
				}

			case <-ctx.Done():
				return nil, fmt.Errorf("execution cancelled: %w", ctx.Err())
			}
		}

		// Check termination conditions
		if pendingCount == 0 && graph.GetReadyNodesCount() == 0 {
			// No more work to schedule and nothing running
			allDone := true
			anyFailed := false
			succeededNodes := []string{}
			failedNodes := make(map[string]string)

			for _, n := range graph.Nodes {
				if n.Status == dag.StatusPending || n.Status == dag.StatusRunning || n.Status == dag.StatusBlocked || n.Status == dag.StatusRetrying {
					allDone = false
					break
				}
				if n.Status == dag.StatusFailed {
					anyFailed = true
					failedNodes[n.ID] = n.LastError
				} else if n.Status == dag.StatusSucceeded {
					succeededNodes = append(succeededNodes, n.ID)
				}
			}

			if allDone {
				if anyFailed {
					// Check for partial success
					if len(succeededNodes) > 0 {
						// Extract partial results
						result, err := e.extractFinalResult(graph, nodeResults)
						if err == nil && result != nil {
							result.PartialSuccess = true
							result.Success = false
							result.SucceededNodes = succeededNodes
							result.FailedNodes = failedNodes
							result.ErrorMessage = fmt.Sprintf("%d nodes failed, %d succeeded", len(failedNodes), len(succeededNodes))
							result.RetryMetrics = e.retryMetrics
							log.Printf("[Executor] Graph completed with partial success: %d succeeded, %d failed", len(succeededNodes), len(failedNodes))
							return result, nil
						}
					}
					// Total failure
					return &ExecutionResult{
						GraphID:        graph.ID,
						Success:        false,
						PartialSuccess: false,
						SucceededNodes: succeededNodes,
						FailedNodes:    failedNodes,
						ErrorMessage:   fmt.Sprintf("All critical nodes failed: %d total failures", len(failedNodes)),
						RetryMetrics:   e.retryMetrics,
					}, nil
				}

				// Full success
				result, err := e.extractFinalResult(graph, nodeResults)
				if err != nil {
					return nil, err
				}
				result.SucceededNodes = succeededNodes
				result.RetryMetrics = e.retryMetrics
				log.Printf("[Executor] Graph completed successfully: %d nodes", len(succeededNodes))
				return result, nil
			}

			// Deadlock detected: no work available but not all nodes completed
			return &ExecutionResult{
				GraphID:      graph.ID,
				Success:      false,
				ErrorMessage: "Execution deadlocked: nodes are blocked",
				RetryMetrics: e.retryMetrics,
			}, nil
		}
	}
}

// executeNode dispatches to type-specific execution handlers.
func (e *DAGExecutor) executeNode(
	ctx context.Context,
	node *dag.Node,
	graph *dag.Graph,
	nodeResults map[string]*NodeResult,
	runID string,
) *NodeResult {
	switch node.Type {
	case "researcher":
		return e.executeResearcher(ctx, node, runID)
	case "critic":
		return e.executeCritic(ctx, node, graph, nodeResults, runID)
	case "synthesizer":
		return e.executeSynthesizer(ctx, node, graph, nodeResults, runID)
	default:
		return &NodeResult{
			NodeID:  node.ID,
			Success: false,
			Error:   fmt.Errorf("unknown node type: %s", node.Type),
		}
	}
}

// executeResearcher invokes the Researcher service via gRPC.
func (e *DAGExecutor) executeResearcher(ctx context.Context, node *dag.Node, runID string) *NodeResult {
	query, ok := node.Config["query"]
	if !ok {
		return &NodeResult{
			NodeID:  node.ID,
			Success: false,
			Error:   fmt.Errorf("researcher node missing 'query' in config"),
		}
	}

	req := &pb.ResearchRequest{
		Query:        query,
		SourceNodeId: node.ID,
		RunId:        runID,
		Config:       node.Config,
	}

	resp, err := e.clients.Researcher.Research(ctx, req)
	if err != nil {
		return &NodeResult{
			NodeID:  node.ID,
			Success: false,
			Error:   fmt.Errorf("researcher RPC failed: %w", err),
		}
	}

	log.Printf("[Executor] Researcher node %s extracted %d claims", node.ID, len(resp.Claims))

	return &NodeResult{
		NodeID:  node.ID,
		Success: true,
		Data:    resp.Claims,
	}
}

// executeCritic aggregates parent claims and invokes the Critic service.
func (e *DAGExecutor) executeCritic(
	ctx context.Context,
	node *dag.Node,
	graph *dag.Graph,
	nodeResults map[string]*NodeResult,
	runID string,
) *NodeResult {
	task, ok := node.Config["task"]
	if !ok {
		return &NodeResult{
			NodeID:  node.ID,
			Success: false,
			Error:   fmt.Errorf("critic node missing 'task' in config"),
		}
	}

	var allClaims []*pb.AtomicClaim
	for _, edge := range graph.Edges {
		if edge.To == node.ID {
			parentResult, ok := nodeResults[edge.From]
			if !ok || !parentResult.Success {
				return &NodeResult{
					NodeID:  node.ID,
					Success: false,
					Error:   fmt.Errorf("parent node %s not completed successfully", edge.From),
				}
			}

			if claims, ok := parentResult.Data.([]*pb.AtomicClaim); ok {
				allClaims = append(allClaims, claims...)
			}
		}
	}

	req := &pb.VerifyRequest{
		Claims: allClaims,
		Task:   task,
		RunId:  runID,
	}

	resp, err := e.clients.Critic.Verify(ctx, req)
	if err != nil {
		return &NodeResult{
			NodeID:  node.ID,
			Success: false,
			Error:   fmt.Errorf("critic RPC failed: %w", err),
		}
	}

	log.Printf("[Executor] Critic node %s verified %d/%d claims", node.ID, resp.VerifiedCount, len(allClaims))

	return &NodeResult{
		NodeID:  node.ID,
		Success: true,
		Data:    resp.Results,
	}
}

// executeSynthesizer aggregates verification results and generates the final report.
func (e *DAGExecutor) executeSynthesizer(
	ctx context.Context,
	node *dag.Node,
	graph *dag.Graph,
	nodeResults map[string]*NodeResult,
	runID string,
) *NodeResult {
	var allResults []*pb.CritiqueResult
	for _, edge := range graph.Edges {
		if edge.To == node.ID {
			parentResult, ok := nodeResults[edge.From]
			if !ok || !parentResult.Success {
				return &NodeResult{
					NodeID:  node.ID,
					Success: false,
					Error:   fmt.Errorf("parent node %s not completed successfully", edge.From),
				}
			}

			if results, ok := parentResult.Data.([]*pb.CritiqueResult); ok {
				allResults = append(allResults, results...)
			}
		}
	}

	context := make(map[string]string)
	if query, ok := node.Config["query"]; ok {
		context["report_title"] = fmt.Sprintf("HDRP Research Report: %s", query)
		context["introduction"] = "This report was generated by the Hierarchical Deep Research Planner (HDRP) using concurrent DAG execution."
	}

	req := &pb.SynthesizeRequest{
		VerificationResults: allResults,
		Context:             context,
		RunId:               runID,
	}

	resp, err := e.clients.Synthesizer.Synthesize(ctx, req)
	if err != nil {
		return &NodeResult{
			NodeID:  node.ID,
			Success: false,
			Error:   fmt.Errorf("synthesizer RPC failed: %w", err),
		}
	}

	log.Printf("[Executor] Synthesizer node %s generated report (%d chars)", node.ID, len(resp.Report))

	return &NodeResult{
		NodeID:  node.ID,
		Success: true,
		Data:    resp,
	}
}

// extractFinalResult retrieves the report from completed synthesizer nodes.
func (e *DAGExecutor) extractFinalResult(graph *dag.Graph, nodeResults map[string]*NodeResult) (*ExecutionResult, error) {
	for _, node := range graph.Nodes {
		if node.Type == "synthesizer" && node.Status == dag.StatusSucceeded {
			result, ok := nodeResults[node.ID]
			if !ok || !result.Success {
				continue
			}

			if synthResp, ok := result.Data.(*pb.SynthesizeResponse); ok {
				return &ExecutionResult{
					GraphID:     graph.ID,
					Success:     true,
					FinalReport: synthResp.Report,
					ArtifactURI: synthResp.ArtifactUri,
				}, nil
			}
		}
	}

	return &ExecutionResult{
		GraphID:      graph.ID,
		Success:      false,
		ErrorMessage: "No synthesizer output found",
	}, nil
}

// RecoverGraph attempts to recover a graph from persistent storage.
// Returns the recovered graph or nil if no recovery data exists.
func (e *DAGExecutor) RecoverGraph(graphID string) (*dag.Graph, error) {
	if e.storage == nil {
		return nil, fmt.Errorf("no storage backend available")
	}

	log.Printf("[Executor] Attempting to recover graph %s from storage", graphID)

	graph := dag.NewGraphWithStorage(graphID, e.storage)
	if err := graph.LoadFromStorage(graphID); err != nil {
		return nil, fmt.Errorf("failed to load graph from storage: %w", err)
	}

	log.Printf("[Executor] Successfully recovered graph %s with %d nodes (status: %s)", 
		graphID, len(graph.Nodes), graph.Status)

	return graph, nil
}

// persistInitialGraph saves the initial graph state to storage.
func (e *DAGExecutor) persistInitialGraph(graph *dag.Graph) error {
	if e.storage == nil {
		return nil
	}

	// Save graph metadata
	graphState := &storage.GraphState{
		ID:       graph.ID,
		Status:   string(graph.Status),
		Metadata: graph.Metadata,
	}
	if err := e.storage.SaveGraph(graphState); err != nil {
		return fmt.Errorf("failed to save graph: %w", err)
	}

	// Log graph creation to WAL
	payload := &storage.CreateGraphPayload{
		Graph: *graphState,
	}
	if err := e.storage.LogMutation(graph.ID, storage.MutationCreateGraph, payload); err != nil {
		return fmt.Errorf("failed to log graph creation: %w", err)
	}

	// Save all nodes
	for i := range graph.Nodes {
		nodeState := &storage.NodeState{
			NodeID:         graph.Nodes[i].ID,
			Type:           graph.Nodes[i].Type,
			Config:         graph.Nodes[i].Config,
			Status:         string(graph.Nodes[i].Status),
			RelevanceScore: graph.Nodes[i].RelevanceScore,
			Depth:          graph.Nodes[i].Depth,
			RetryCount:     graph.Nodes[i].RetryCount,
			LastError:      graph.Nodes[i].LastError,
		}
		if err := e.storage.SaveNode(graph.ID, nodeState); err != nil {
			return fmt.Errorf("failed to save node %s: %w", graph.Nodes[i].ID, err)
		}

		// Log node creation to WAL
		addPayload := &storage.AddNodePayload{
			Node: *nodeState,
		}
		if err := e.storage.LogMutation(graph.ID, storage.MutationAddNode, addPayload); err != nil {
			log.Printf("[Executor] Warning: failed to log node creation: %v", err)
		}
	}

	// Save all edges
	for _, edge := range graph.Edges {
		if err := e.storage.SaveEdge(graph.ID, edge.From, edge.To); err != nil {
			return fmt.Errorf("failed to save edge %s->%s: %w", edge.From, edge.To, err)
		}

		// Log edge creation to WAL
		edgePayload := &storage.AddEdgePayload{
			From: edge.From,
			To:   edge.To,
		}
		if err := e.storage.LogMutation(graph.ID, storage.MutationAddEdge, edgePayload); err != nil {
			log.Printf("[Executor] Warning: failed to log edge creation: %v", err)
		}
	}

	log.Printf("[Executor] Persisted initial graph %s with %d nodes and %d edges", 
		graph.ID, len(graph.Nodes), len(graph.Edges))

	return nil
}

// Close releases resources held by the executor.
func (e *DAGExecutor) Close() error {
	if e.storage != nil {
		return e.storage.Close()
	}
	return nil
}
