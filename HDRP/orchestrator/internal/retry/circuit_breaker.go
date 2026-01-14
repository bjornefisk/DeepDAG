package retry

import (
	"sync"
	"time"
)

// CircuitState represents the state of a circuit breaker.
type CircuitState int

const (
	// CircuitClosed means requests are allowed through normally.
	CircuitClosed CircuitState = iota
	// CircuitOpen means requests are blocked due to high failure rate.
	CircuitOpen
	// CircuitHalfOpen means limited requests are allowed to test recovery.
	CircuitHalfOpen
)

// String returns the string representation of CircuitState.
func (s CircuitState) String() string {
	switch s {
	case CircuitClosed:
		return "Closed"
	case CircuitOpen:
		return "Open"
	case CircuitHalfOpen:
		return "HalfOpen"
	default:
		return "Unknown"
	}
}

// CircuitBreaker implements the circuit breaker pattern to prevent cascading failures.
type CircuitBreaker struct {
	mu sync.RWMutex

	// Configuration
	failureThreshold  float64       // Failure rate (0.0-1.0) to open circuit
	minRequests      int           // Minimum requests before evaluating threshold
	openTimeout      time.Duration // Time to wait before transitioning to half-open
	halfOpenMaxTests int           // Max requests allowed in half-open state

	// State
	state            CircuitState
	failures         int
	successes        int
	consecutiveSuccesses int // For half-open state
	lastFailureTime  time.Time
	openedAt         time.Time
}

// NewCircuitBreaker creates a new circuit breaker with default settings.
func NewCircuitBreaker() *CircuitBreaker {
	return &CircuitBreaker{
		failureThreshold:  0.5,  // 50% failure rate
		minRequests:      10,    // Need at least 10 requests
		openTimeout:      30 * time.Second,
		halfOpenMaxTests: 3,     // Allow 3 test requests
		state:            CircuitClosed,
	}
}

// NewCircuitBreakerWithConfig creates a circuit breaker with custom settings.
func NewCircuitBreakerWithConfig(failureThreshold float64, minRequests int, openTimeout time.Duration) *CircuitBreaker {
	return &CircuitBreaker{
		failureThreshold:  failureThreshold,
		minRequests:      minRequests,
		openTimeout:      openTimeout,
		halfOpenMaxTests: 3,
		state:            CircuitClosed,
	}
}

// ShouldAllow determines if a request should be allowed through.
func (cb *CircuitBreaker) ShouldAllow() bool {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	switch cb.state {
	case CircuitClosed:
		return true

	case CircuitOpen:
		// Check if we should transition to half-open
		if time.Since(cb.openedAt) >= cb.openTimeout {
			cb.state = CircuitHalfOpen
			cb.consecutiveSuccesses = 0
			return true
		}
		return false

	case CircuitHalfOpen:
		// Allow limited test requests
		return cb.consecutiveSuccesses < cb.halfOpenMaxTests

	default:
		return false
	}
}

// RecordSuccess records a successful request.
func (cb *CircuitBreaker) RecordSuccess() {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	cb.successes++

	switch cb.state {
	case CircuitHalfOpen:
		cb.consecutiveSuccesses++
		// If enough consecutive successes, close the circuit
		if cb.consecutiveSuccesses >= cb.halfOpenMaxTests {
			cb.state = CircuitClosed
			cb.reset()
		}

	case CircuitClosed:
		// Check if we should reset counters to prevent stale data
		if cb.failures+cb.successes >= cb.minRequests*2 {
			cb.reset()
		}
	}
}

// RecordFailure records a failed request.
func (cb *CircuitBreaker) RecordFailure() {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	cb.failures++
	cb.lastFailureTime = time.Now()

	switch cb.state {
	case CircuitHalfOpen:
		// Any failure in half-open immediately reopens the circuit
		cb.state = CircuitOpen
		cb.openedAt = time.Now()
		cb.consecutiveSuccesses = 0

	case CircuitClosed:
		// Check if we should open the circuit
		totalRequests := cb.failures + cb.successes
		if totalRequests >= cb.minRequests {
			failureRate := float64(cb.failures) / float64(totalRequests)
			if failureRate >= cb.failureThreshold {
				cb.state = CircuitOpen
				cb.openedAt = time.Now()
			}
		}
	}
}

// GetState returns the current circuit state.
func (cb *CircuitBreaker) GetState() CircuitState {
	cb.mu.RLock()
	defer cb.mu.RUnlock()
	return cb.state
}

// GetStats returns current statistics.
func (cb *CircuitBreaker) GetStats() (failures, successes int, state CircuitState) {
	cb.mu.RLock()
	defer cb.mu.RUnlock()
	return cb.failures, cb.successes, cb.state
}

// reset clears the counters (must be called with lock held).
func (cb *CircuitBreaker) reset() {
	cb.failures = 0
	cb.successes = 0
	cb.consecutiveSuccesses = 0
}

// PerServiceBreakers manages circuit breakers for different service types.
type PerServiceBreakers struct {
	mu       sync.RWMutex
	breakers map[string]*CircuitBreaker
}

// NewPerServiceBreakers creates a new manager for per-service circuit breakers.
func NewPerServiceBreakers() *PerServiceBreakers {
	return &PerServiceBreakers{
		breakers: make(map[string]*CircuitBreaker),
	}
}

// GetBreaker returns the circuit breaker for a service type, creating it if needed.
func (psb *PerServiceBreakers) GetBreaker(serviceType string) *CircuitBreaker {
	psb.mu.RLock()
	breaker, exists := psb.breakers[serviceType]
	psb.mu.RUnlock()

	if exists {
		return breaker
	}

	// Create new breaker
	psb.mu.Lock()
	defer psb.mu.Unlock()

	// Double-check after acquiring write lock
	if breaker, exists := psb.breakers[serviceType]; exists {
		return breaker
	}

	breaker = NewCircuitBreaker()
	psb.breakers[serviceType] = breaker
	return breaker
}

// ShouldAllow checks if requests to a service type should be allowed.
func (psb *PerServiceBreakers) ShouldAllow(serviceType string) bool {
	return psb.GetBreaker(serviceType).ShouldAllow()
}

// RecordSuccess records a successful request for a service type.
func (psb *PerServiceBreakers) RecordSuccess(serviceType string) {
	psb.GetBreaker(serviceType).RecordSuccess()
}

// RecordFailure records a failed request for a service type.
func (psb *PerServiceBreakers) RecordFailure(serviceType string) {
	psb.GetBreaker(serviceType).RecordFailure()
}
