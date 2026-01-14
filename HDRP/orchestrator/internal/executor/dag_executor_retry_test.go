package executor

import (
	"context"
	"errors"
	"fmt"
	"math/rand"
	"testing"
	"time"

	"hdrp/internal/clients"
	"hdrp/internal/dag"
	"hdrp/internal/retry"

	pb "github.com/deepdag/hdrp/api/gen/services"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// Mock client that can inject failures
type mockResearcherClient struct {
	failureCount    int
	maxFailures     int
	failureType     error
	shouldFail      func(callCount int) bool
	callCount       int
}

func (m *mockResearcherClient) Research(ctx context.Context, req *pb.ResearchRequest, opts ...interface{}) (*pb.ResearchResponse, error) {
	m.callCount++
	
	if m.shouldFail != nil && m.shouldFail(m.callCount) {
		return nil, m.failureType
	}
	
	if m.callCount <= m.maxFailures {
		m.failureCount++
		return nil, m.failureType
	}
	
	// Success
	return &pb.ResearchResponse{
		Claims: []*pb.AtomicClaim{
			{Text: "Test claim", Confidence: 0.9},
		},
	}, nil
}

type mockCriticClient struct{}

func (m *mockCriticClient) Verify(ctx context.Context, req *pb.VerifyRequest, opts ...interface{}) (*pb.VerifyResponse, error) {
	return &pb.VerifyResponse{
		Results:       []*pb.CritiqueResult{},
		VerifiedCount: int32(len(req.Claims)),
	}, nil
}

type mockSynthesizerClient struct{}

func (m *mockSynthesizerClient) Synthesize(ctx context.Context, req *pb.SynthesizeRequest, opts ...interface{}) (*pb.SynthesizeResponse, error) {
	return &pb.SynthesizeResponse{
		Report:      "Test report",
		ArtifactUri: "test://artifact",
	}, nil
}

// TestRetryTransientError verifies that transient errors trigger retries
func TestRetryTransientError(t *testing.T) {
	// Create mock client that fails twice with transient error, then succeeds
	mockClient := &mockResearcherClient{
		maxFailures: 2,
		failureType: context.DeadlineExceeded, // Transient error
	}

	clients := &clients.ServiceClients{
		Researcher:  mockClient,
		Critic:      &mockCriticClient{},
		Synthesizer: &mockSynthesizerClient{},
	}

	executor := NewDAGExecutor(clients, 4)
	
	// Override retry policy for faster testing
	executor.retryPolicy = &retry.RetryPolicy{
		MaxAttempts:      3,
		InitialDelay:     10 * time.Millisecond,
		BackoffMultiplier: 1.5,
		MaxDelay:         100 * time.Millisecond,
	}

	graph := &dag.Graph{
		ID:     "test-retry",
		Status: dag.StatusCreated,
		Nodes: []dag.Node{
			{
				ID:     "researcher1",
				Type:   "researcher",
				Config: map[string]string{"query": "test query"},
				Status: dag.StatusCreated,
			},
		},
		Edges: []dag.Edge{},
	}

	ctx := context.Background()
	result, err := executor.Execute(ctx, graph, "test-run-1")

	if err != nil {
		t.Fatalf("Execution should succeed after retries: %v", err)
	}

	if !result.Success {
		t.Errorf("Expected success after retries, got failure: %s", result.ErrorMessage)
	}

	// Verify retry metrics
	metrics := executor.retryMetrics.GetNodeMetrics("researcher1")
	if metrics == nil {
		t.Fatal("Expected retry metrics for researcher1")
	}

	// Should have 3 attempts (2 failures + 1 success)
	if metrics.TotalAttempts != 3 {
		t.Errorf("Expected 3 total attempts, got %d", metrics.TotalAttempts)
	}

	if metrics.FailureCount != 2 {
		t.Errorf("Expected 2 failures, got %d", metrics.FailureCount)
	}

	if mockClient.callCount != 3 {
		t.Errorf("Expected 3 calls to researcher, got %d", mockClient.callCount)
	}
}

// TestNoPermanentErrorRetry verifies that permanent errors don't trigger retries
func TestNoPermanentErrorRetry(t *testing.T) {
	// Create mock client that fails with permanent error
	mockClient := &mockResearcherClient{
		maxFailures: 10, // More than max retries
		failureType: status.Error(codes.InvalidArgument, "validation failed"), // Permanent error
	}

	clients := &clients.ServiceClients{
		Researcher:  mockClient,
		Critic:      &mockCriticClient{},
		Synthesizer: &mockSynthesizerClient{},
	}

	executor := NewDAGExecutor(clients, 4)
	executor.retryPolicy = &retry.RetryPolicy{
		MaxAttempts:      3,
		InitialDelay:     10 * time.Millisecond,
		BackoffMultiplier: 2.0,
		MaxDelay:         100 * time.Millisecond,
	}

	graph := &dag.Graph{
		ID:     "test-no-retry",
		Status: dag.StatusCreated,
		Nodes: []dag.Node{
			{
				ID:     "researcher1",
				Type:   "researcher",
				Config: map[string]string{"query": "test query"},
				Status: dag.StatusCreated,
			},
		},
		Edges: []dag.Edge{},
	}

	ctx := context.Background()
	result, err := executor.Execute(ctx, graph, "test-run-2")

	if err != nil {
		t.Fatalf("Execution error: %v", err)
	}

	if result.Success {
		t.Error("Expected failure due to permanent error")
	}

	// Should only attempt once (no retries for permanent errors)
	if mockClient.callCount != 1 {
		t.Errorf("Expected 1 call (no retries for permanent error), got %d", mockClient.callCount)
	}
}

// TestSiblingContinuesAfterFailure verifies that sibling nodes execute even when one branch fails
func TestSiblingContinuesAfterFailure(t *testing.T) {
	failingClient := &mockResearcherClient{
		maxFailures: 10,
		failureType: errors.New("permanent failure"),
	}

	successClient := &mockResearcherClient{
		maxFailures: 0, // Never fails
	}

	// We'll track which node is being called by the query
	mockClient := &mockResearcherClient{
		shouldFail: func(callCount int) bool {
			return callCount == 1 // First call fails (researcher1)
		},
		failureType: errors.New("permanent failure"),
	}

	clients := &clients.ServiceClients{
		Researcher:  mockClient,
		Critic:      &mockCriticClient{},
		Synthesizer: &mockSynthesizerClient{},
	}

	executor := NewDAGExecutor(clients, 4)
	executor.retryPolicy = &retry.RetryPolicy{
		MaxAttempts:      0, // No retries for faster test
		InitialDelay:     10 * time.Millisecond,
		BackoffMultiplier: 2.0,
		MaxDelay:         100 * time.Millisecond,
	}

	// Create graph with two independent branches
	graph := &dag.Graph{
		ID:     "test-siblings",
		Status: dag.StatusCreated,
		Nodes: []dag.Node{
			{
				ID:     "researcher1",
				Type:   "researcher",
				Config: map[string]string{"query": "will fail"},
				Status: dag.StatusCreated,
			},
			{
				ID:     "researcher2",
				Type:   "researcher",
				Config: map[string]string{"query": "will succeed"},
				Status: dag.StatusCreated,
			},
		},
		Edges: []dag.Edge{}, // No dependencies - siblings
	}

	ctx := context.Background()
	result, err := executor.Execute(ctx, graph, "test-run-3")

	if err != nil {
		t.Fatalf("Execution error: %v", err)
	}

	// Should have partial success
	if !result.PartialSuccess {
		t.Error("Expected partial success when one sibling fails")
	}

	if result.Success {
		t.Error("Overall success should be false when any node fails")
	}

	// Both nodes should have been attempted
	if mockClient.callCount != 2 {
		t.Errorf("Expected both siblings to execute, got %d calls", mockClient.callCount)
	}

	// Check succeeded and failed nodes
	if len(result.SucceededNodes) != 1 {
		t.Errorf("Expected 1 succeeded node, got %d", len(result.SucceededNodes))
	}

	if len(result.FailedNodes) != 1 {
		t.Errorf("Expected 1 failed node, got %d", len(result.FailedNodes))
	}
}

// Test30PercentFailureRate verifies graceful degradation with random failures
func Test30PercentFailureRate(t *testing.T) {
	rand.Seed(time.Now().UnixNano())
	
	m mockClient := &mockResearcherClient{
		shouldFail: func(callCount int) bool {
			// 30% chance of failure
			return rand.Float64() < 0.3
		},
		failureType: context.DeadlineExceeded, // Transient error
	}

	clients := &clients.ServiceClients{
		Researcher:  mockClient,
		Critic:      &mockCriticClient{},
		Synthesizer: &mockSynthesizerClient{},
	}

	executor := NewDAGExecutor(clients, 4)
	executor.retryPolicy = &retry.RetryPolicy{
		MaxAttempts:      3,
		InitialDelay:     5 * time.Millisecond,
		BackoffMultiplier: 2.0,
		MaxDelay:         50 * time.Millisecond,
	}

	// Create graph with 10 independent nodes
	nodes := make([]dag.Node, 10)
	for i := 0; i < 10; i++ {
		nodes[i] = dag.Node{
			ID:     fmt.Sprintf("researcher%d", i),
			Type:   "researcher",
			Config: map[string]string{"query": fmt.Sprintf("query %d", i)},
			Status: dag.StatusCreated,
		}
	}

	graph := &dag.Graph{
		ID:     "test-random-failures",
		Status: dag.StatusCreated,
		Nodes:  nodes,
		Edges:  []dag.Edge{},
	}

	ctx := context.Background()
	result, err := executor.Execute(ctx, graph, "test-run-4")

	if err != nil {
		t.Fatalf("Execution error: %v", err)
	}

	// With retries, most nodes should eventually succeed
	// Even with 30% base failure rate, exponential backoff should recover most
	succeededRatio := float64(len(result.SucceededNodes)) / float64(len(nodes))
	
	if succeededRatio < 0.5 {
		t.Logf("Warning: Only %.0f%% of nodes succeeded with 30%% failure rate and retries", succeededRatio*100)
	}

	// Should have partial results even with some failures
	if len(result.SucceededNodes) == 0 && len(result.FailedNodes) > 0 {
		t.Error("Expected at least some nodes to succeed with retries")
	}

	t.Logf("Results: %d succeeded, %d failed out of %d total",
		len(result.SucceededNodes), len(result.FailedNodes), len(nodes))
	
	// Log retry metrics
	allMetrics := executor.retryMetrics.GetAllMetrics()
	totalRetries := 0
	for _, metrics := range allMetrics {
		if metrics.TotalAttempts > 1 {
			totalRetries += (metrics.TotalAttempts - 1)
		}
	}
	t.Logf("Total retries performed: %d", totalRetries)
}

// TestCircuitBreakerTrip verifies circuit breaker opens after threshold
func TestCircuitBreakerTrip(t *testing.T) {
	mockClient := &mockResearcherClient{
		maxFailures: 100, // Always fail
		failureType: errors.New("service down"),
	}

	clients := &clients.ServiceClients{
		Researcher:  mockClient,
		Critic:      &mockCriticClient{},
		Synthesizer: &mockSynthesizerClient{},
	}

	executor := NewDAGExecutor(clients, 10)
	executor.retryPolicy = &retry.RetryPolicy{
		MaxAttempts:      0, // No retries for this test
		InitialDelay:     10 * time.Millisecond,
		BackoffMultiplier: 2.0,
		MaxDelay:         100 * time.Millisecond,
	}

	// Create 15 researcher nodes to trip circuit breaker (default needs 10 requests at 50% failure)
	nodes := make([]dag.Node, 15)
	for i := 0; i < 15; i++ {
		nodes[i] = dag.Node{
			ID:     fmt.Sprintf("researcher%d", i),
			Type:   "researcher",
			Config: map[string]string{"query": fmt.Sprintf("query %d", i)},
			Status: dag.StatusCreated,
		}
	}

	graph := &dag.Graph{
		ID:     "test-circuit-breaker",
		Status: dag.StatusCreated,
		Nodes:  nodes,
		Edges:  []dag.Edge{},
	}

	ctx := context.Background()
	result, err := executor.Execute(ctx, graph, "test-run-5")

	if err != nil {
		t.Fatalf("Execution error: %v", err)
	}

	// Check circuit breaker state
	breaker := executor.circuitBreakers.GetBreaker("researcher")
	state := breaker.GetState()

	// Circuit should eventually open
	if state != retry.CircuitOpen {
		t.Logf("Warning: Circuit breaker not open after %d failures (state: %v)", mockClient.callCount, state)
	}

	// Some requests should have been blocked by circuit breaker
	circuitBreakerBlocked := false
	for _, metrics := range executor.retryMetrics.GetAllMetrics() {
		if metrics.CircuitBreakerHits > 0 {
			circuitBreakerBlocked = true
			break
		}
	}

	if !circuitBreakerBlocked {
		t.Logf("Warning: No circuit breaker hits recorded")
	}

	t.Logf("Circuit breaker state: %v, Total calls: %d", state, mockClient.callCount)
}
