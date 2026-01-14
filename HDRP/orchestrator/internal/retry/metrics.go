package retry

import (
	"fmt"
	"sync"
)

// NodeMetrics tracks retry metrics for a single node.
type NodeMetrics struct {
	NodeID            string
	TotalAttempts     int
	SuccessCount      int
	FailureCount      int
	TransientErrors   int
	PermanentErrors   int
	CircuitBreakerHits int
}

// RetryMetrics tracks retry statistics across all nodes in an execution.
type RetryMetrics struct {
	mu          sync.RWMutex
	nodeMetrics map[string]*NodeMetrics
}

// NewRetryMetrics creates a new metrics tracker.
func NewRetryMetrics() *RetryMetrics {
	return &RetryMetrics{
		nodeMetrics: make(map[string]*NodeMetrics),
	}
}

// RecordAttempt records a retry attempt for a node.
func (rm *RetryMetrics) RecordAttempt(nodeID string) {
	rm.mu.Lock()
	defer rm.mu.Unlock()

	if rm.nodeMetrics[nodeID] == nil {
		rm.nodeMetrics[nodeID] = &NodeMetrics{NodeID: nodeID}
	}
	rm.nodeMetrics[nodeID].TotalAttempts++
}

// RecordSuccess records a successful execution.
func (rm *RetryMetrics) RecordSuccess(nodeID string) {
	rm.mu.Lock()
	defer rm.mu.Unlock()

	if rm.nodeMetrics[nodeID] == nil {
		rm.nodeMetrics[nodeID] = &NodeMetrics{NodeID: nodeID}
	}
	rm.nodeMetrics[nodeID].SuccessCount++
}

// RecordFailure records a failed execution with error type.
func (rm *RetryMetrics) RecordFailure(nodeID string, errorType ErrorType) {
	rm.mu.Lock()
	defer rm.mu.Unlock()

	if rm.nodeMetrics[nodeID] == nil {
		rm.nodeMetrics[nodeID] = &NodeMetrics{NodeID: nodeID}
	}
	
	metrics := rm.nodeMetrics[nodeID]
	metrics.FailureCount++
	
	switch errorType {
	case ErrorTypeTransient:
		metrics.TransientErrors++
	case ErrorTypePermanent:
		metrics.PermanentErrors++
	}
}

// RecordCircuitBreakerHit records when a circuit breaker blocks a request.
func (rm *RetryMetrics) RecordCircuitBreakerHit(nodeID string) {
	rm.mu.Lock()
	defer rm.mu.Unlock()

	if rm.nodeMetrics[nodeID] == nil {
		rm.nodeMetrics[nodeID] = &NodeMetrics{NodeID: nodeID}
	}
	rm.nodeMetrics[nodeID].CircuitBreakerHits++
}

// GetNodeMetrics returns metrics for a specific node.
func (rm *RetryMetrics) GetNodeMetrics(nodeID string) *NodeMetrics {
	rm.mu.RLock()
	defer rm.mu.RUnlock()

	if metrics, exists := rm.nodeMetrics[nodeID]; exists {
		// Return a copy to prevent race conditions
		return &NodeMetrics{
			NodeID:            metrics.NodeID,
			TotalAttempts:     metrics.TotalAttempts,
			SuccessCount:      metrics.SuccessCount,
			FailureCount:      metrics.FailureCount,
			TransientErrors:   metrics.TransientErrors,
			PermanentErrors:   metrics.PermanentErrors,
			CircuitBreakerHits: metrics.CircuitBreakerHits,
		}
	}
	return nil
}

// GetAllMetrics returns all node metrics.
func (rm *RetryMetrics) GetAllMetrics() map[string]*NodeMetrics {
	rm.mu.RLock()
	defer rm.mu.RUnlock()

	result := make(map[string]*NodeMetrics)
	for nodeID, metrics := range rm.nodeMetrics {
		result[nodeID] = &NodeMetrics{
			NodeID:            metrics.NodeID,
			TotalAttempts:     metrics.TotalAttempts,
			SuccessCount:      metrics.SuccessCount,
			FailureCount:      metrics.FailureCount,
			TransientErrors:   metrics.TransientErrors,
			PermanentErrors:   metrics.PermanentErrors,
			CircuitBreakerHits: metrics.CircuitBreakerHits,
		}
	}
	return result
}

// Summary returns a formatted summary of retry metrics.
func (rm *RetryMetrics) Summary() string {
	rm.mu.RLock()
	defer rm.mu.RUnlock()

	if len(rm.nodeMetrics) == 0 {
		return "No retry metrics recorded"
	}

	var summary string
	summary += fmt.Sprintf("Retry Metrics Summary (%d nodes):\n", len(rm.nodeMetrics))
	
	totalAttempts := 0
	totalFailures := 0
	totalRetries := 0
	
	for nodeID, metrics := range rm.nodeMetrics {
		totalAttempts += metrics.TotalAttempts
		totalFailures += metrics.FailureCount
		
		if metrics.TotalAttempts > 1 {
			totalRetries += (metrics.TotalAttempts - 1)
			summary += fmt.Sprintf("  - %s: %d attempts, %d failures (%d transient, %d permanent)\n",
				nodeID, metrics.TotalAttempts, metrics.FailureCount,
				metrics.TransientErrors, metrics.PermanentErrors)
		}
	}
	
	summary += fmt.Sprintf("Total: %d attempts, %d retries, %d failures\n", 
		totalAttempts, totalRetries, totalFailures)
	
	return summary
}
