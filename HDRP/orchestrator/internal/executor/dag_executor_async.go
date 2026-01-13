package executor

import (
	"context"
	"fmt"
	"log"
	"sync"

	"hdrp/internal/dag"
)

// executeNodeAsync wraps executeNode to run it asynchronously and send results to a channel.
func (e *DAGExecutor) executeNodeAsync(
	ctx context.Context,
	node *dag.Node,
	graph *dag.Graph,
	nodeResults map[string]*NodeResult,
	resultsMu *sync.RWMutex,
	runID string,
	resultChan chan<- *NodeResult,
) {
	log.Printf("[Executor] Executing node %s (type: %s)", node.ID, node.Type)

	// Acquire distributed lock if configured
	if e.lockManager != nil {
		acquired, err := e.lockManager.AcquireNodeLockWithRetry(ctx, node.ID, 3)
		if err != nil {
			resultChan <- &NodeResult{
				NodeID:  node.ID,
				Success: false,
				Error:   fmt.Errorf("failed to acquire lock: %w", err),
			}
			return
		}
		if !acquired {
			resultChan <- &NodeResult{
				NodeID:  node.ID,
				Success: false,
				Error:   fmt.Errorf("node already being executed by another instance"),
			}
			return
		}
		defer func() {
			if err := e.lockManager.ReleaseNodeLock(ctx, node.ID); err != nil {
				log.Printf("[Executor] Warning: failed to release lock for node %s: %v", node.ID, err)
			}
		}()
	}

	// Acquire rate limit token
	limiter := e.rateLimiters.GetLimiter(node.Type)
	if err := limiter.Acquire(ctx); err != nil {
		resultChan <- &NodeResult{
			NodeID:  node.ID,
			Success: false,
			Error:   fmt.Errorf("rate limit acquire failed: %w", err),
		}
		return
	}
	defer limiter.Release()

	// Execute the node with timeout
	execCtx, cancel := context.WithTimeout(ctx, e.config.NodeExecutionTimeout)
	defer cancel()

	// Read current results (thread-safe)
	resultsMu.RLock()
	resultsCopy := make(map[string]*NodeResult, len(nodeResults))
	for k, v := range nodeResults {
		resultsCopy[k] = v
	}
	resultsMu.RUnlock()

	result := e.executeNode(execCtx, node, graph, resultsCopy, runID)
	resultChan <- result
}
