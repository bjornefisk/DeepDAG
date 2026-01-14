package retry

import (
	"testing"
	"time"
)

func TestCircuitBreakerClosed(t *testing.T) {
	cb := NewCircuitBreaker()

	// Closed state should allow all requests
	if !cb.ShouldAllow() {
		t.Error("Circuit breaker should allow requests when closed")
	}

	// Record some successes
	for i := 0; i < 5; i++ {
		cb.RecordSuccess()
	}

	if state := cb.GetState(); state != CircuitClosed {
		t.Errorf("Expected state Closed, got %v", state)
	}
}

func TestCircuitBreakerOpens(t *testing.T) {
	cb := NewCircuitBreakerWithConfig(0.5, 10, 1*time.Second)

	// Record failures to reach threshold (50% of 10 = 5 failures)
	for i := 0; i < 6; i++ {
		cb.RecordFailure()
	}
	// Add some successes to reach minRequests
	for i := 0; i < 4; i++ {
		cb.RecordSuccess()
	}

	// Circuit should be open now (6 failures out of 10 = 60%)
	if state := cb.GetState(); state != CircuitOpen {
		t.Errorf("Expected state Open, got %v", state)
	}

	if cb.ShouldAllow() {
		t.Error("Circuit breaker should block requests when open")
	}
}

func TestCircuitBreakerHalfOpen(t *testing.T) {
	cb := NewCircuitBreakerWithConfig(0.5, 10, 100*time.Millisecond)

	// Force circuit to open
	for i := 0; i < 10; i++ {
		cb.RecordFailure()
	}

	if state := cb.GetState(); state != CircuitOpen {
		t.Errorf("Expected state Open, got %v", state)
	}

	// Wait for timeout
	time.Sleep(150 * time.Millisecond)

	// Should transition to half-open on first check
	if !cb.ShouldAllow() {
		t.Error("Circuit breaker should allow test requests in half-open state")
	}

	if state := cb.GetState(); state != CircuitHalfOpen {
		t.Errorf("Expected state HalfOpen, got %v", state)
	}
}

func TestCircuitBreakerHalfOpenToClose(t *testing.T) {
	cb := NewCircuitBreakerWithConfig(0.5, 10, 50*time.Millisecond)

	// Open the circuit
	for i := 0; i < 10; i++ {
		cb.RecordFailure()
	}

	// Wait for timeout
	time.Sleep(100 * time.Millisecond)

	// Transition to half-open
	cb.ShouldAllow()

	// Record successful test requests (need 3 consecutive successes)
	for i := 0; i < 3; i++ {
		cb.RecordSuccess()
	}

	// Should be closed now
	if state := cb.GetState(); state != CircuitClosed {
		t.Errorf("Expected state Closed after successful tests, got %v", state)
	}
}

func TestCircuitBreakerHalfOpenToOpen(t *testing.T) {
	cb := NewCircuitBreakerWithConfig(0.5, 10, 50*time.Millisecond)

	// Open the circuit
	for i := 0; i < 10; i++ {
		cb.RecordFailure()
	}

	// Wait for timeout
	time.Sleep(100 * time.Millisecond)

	// Transition to half-open
	cb.ShouldAllow()

	// Any failure in half-open reopens the circuit
	cb.RecordFailure()

	if state := cb.GetState(); state != CircuitOpen {
		t.Errorf("Expected state Open after failure in half-open, got %v", state)
	}
}

func TestPerServiceBreakers(t *testing.T) {
	psb := NewPerServiceBreakers()

	// Different services should have independent breakers
	psb.RecordFailure("researcher")
	psb.RecordFailure("researcher")
	psb.RecordSuccess("critic")

	researcherBreaker := psb.GetBreaker("researcher")
	criticBreaker := psb.GetBreaker("critic")

	failures1, successes1, _ := researcherBreaker.GetStats()
	failures2, successes2, _ := criticBreaker.GetStats()

	if failures1 != 2 || successes1 != 0 {
		t.Errorf("Researcher breaker should have 2 failures, 0 successes, got %d, %d", failures1, successes1)
	}

	if failures2 != 0 || successes2 != 1 {
		t.Errorf("Critic breaker should have 0 failures, 1 success, got %d, %d", failures2, successes2)
	}
}

func TestPerServiceBreakersConcurrent(t *testing.T) {
	psb := NewPerServiceBreakers()

	// Test concurrent access
	done := make(chan bool)
	for i := 0; i < 10; i++ {
		go func() {
			for j := 0; j < 100; j++ {
				if psb.ShouldAllow("researcher") {
					psb.RecordSuccess("researcher")
				}
			}
			done <- true
		}()
	}

	// Wait for all goroutines
	for i := 0; i < 10; i++ {
		<-done
	}

	breaker := psb.GetBreaker("researcher")
	_, successes, _ := breaker.GetStats()

	if successes != 1000 {
		t.Errorf("Expected 1000 successes, got %d", successes)
	}
}
