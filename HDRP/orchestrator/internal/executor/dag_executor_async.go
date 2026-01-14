package executor

import (
	"context"
	"fmt"
	"log"
	"sync"
	"time"

	"hdrp/internal/dag"
	"hdrp/internal/retry"
)

// executeNodeAsync wraps executeNode to run it asynchronously with retry logic.
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

	// Load checkpoint to determine starting attempt
	checkpoint, _ := e.checkpointStore.Load(runID, node.ID)
	startAttempt := checkpoint.AttemptNumber

	var result *NodeResult

	// Retry loop with exponential backoff
	for attempt := startAttempt; attempt <= e.retryPolicy.MaxAttempts; attempt++ {
		e.retryMetrics.RecordAttempt(node.ID)

		// Check circuit breaker before attempting
		if !e.circuitBreakers.ShouldAllow(node.Type) {
			e.retryMetrics.RecordCircuitBreakerHit(node.ID)
			result = &NodeResult{
				NodeID:  node.ID,
				Success: false,
				Error:   fmt.Errorf("circuit breaker open for service type %s", node.Type),
			}
			log.Printf("[Retry] Circuit breaker open for %s, skipping node %s", node.Type, node.ID)
			break
		}

		// Set status to RETRYING if this is a retry attempt
		if attempt > 0 {
			if err := graph.SetNodeStatus(node.ID, dag.StatusRetrying); err != nil {
				log.Printf("[Retry] Warning: failed to set retrying status for node %s: %v", node.ID, err)
			}
			log.Printf("[Retry] Retrying node %s (attempt %d/%d)", node.ID, attempt+1, e.retryPolicy.MaxAttempts+1)
		}

		// Execute the node with timeout
		execCtx, cancel := context.WithTimeout(ctx, e.config.NodeExecutionTimeout)
		
		// Read current results (thread-safe)
		resultsMu.RLock()
		resultsCopy := make(map[string]*NodeResult, len(nodeResults))
		for k, v := range nodeResults {
			resultsCopy[k] = v
		}
		resultsMu.RUnlock()

		result = e.executeNode(execCtx, node, graph, resultsCopy, runID)
		cancel()

		if result.Success {
			// Success - record metrics and clean up checkpoint
			e.circuitBreakers.RecordSuccess(node.Type)
			e.retryMetrics.RecordSuccess(node.ID)
			e.checkpointStore.Delete(runID, node.ID)
			log.Printf("[Executor] Node %s succeeded on attempt %d", node.ID, attempt+1)
			break
		}

		// Failure - classify error and decide on retry
		errorType := retry.ClassifyError(result.Error)
		e.circuitBreakers.RecordFailure(node.Type)
		e.retryMetrics.RecordFailure(node.ID, errorType)

		log.Printf("[Retry] Node %s failed on attempt %d: %v (error type: %s)", 
			node.ID, attempt+1, result.Error, errorType.String())

		// Check if we should retry
		if !retry.IsRetryable(result.Error) {
			log.Printf("[Retry] Node %s encountered permanent error, no retry", node.ID)
			break
		}

		if attempt >= e.retryPolicy.MaxAttempts {
			log.Printf("[Retry] Node %s exhausted all %d retry attempts", node.ID, e.retryPolicy.MaxAttempts+1)
			break
		}

		// Save checkpoint before waiting
		if err := e.checkpointStore.Save(runID, node.ID, attempt+1, result.Error); err != nil {
			log.Printf("[Retry] Warning: failed to save checkpoint for node %s: %v", node.ID, err)
		}

		// Update node's LastError in graph
		if n := graph.Nodes; n != nil {
			for i := range n {
				if n[i].ID == node.ID {
					n[i].LastError = result.Error.Error()
					n[i].RetryCount = attempt + 1
					break
				}
			}
		}

		// Calculate backoff delay
		delay := retry.ExponentialBackoff(e.retryPolicy, attempt)
		log.Printf("[Retry] Node %s will retry in %v", node.ID, delay)

		// Wait with context cancellation support
		select {
		case <-time.After(delay):
			// Continue to next retry attempt
		case <-ctx.Done():
			result.Error = fmt.Errorf("retry cancelled: %w", ctx.Err())
			log.Printf("[Retry] Node %s retry cancelled by context", node.ID)
			break
		}
	}

	// Update final error in graph if failed
	if !result.Success && result.Error != nil {
		if n := graph.Nodes; n != nil {
			for i := range n {
				if n[i].ID == node.ID {
					n[i].LastError = result.Error.Error()
					n[i].RetryCount = startAttempt + 1
					break
				}
			}
		}
	}

	resultChan <- result
}
