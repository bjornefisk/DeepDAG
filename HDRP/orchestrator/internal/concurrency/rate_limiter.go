package concurrency

import (
	"context"
	"fmt"
	"sync"
	"time"
)

// RateLimiter implements a token bucket rate limiter for controlling concurrency.
type RateLimiter struct {
	maxConcurrent int
	tokens        chan struct{}
	mu            sync.Mutex
}

// NewRateLimiter creates a rate limiter with the specified maximum concurrent operations.
func NewRateLimiter(maxConcurrent int) *RateLimiter {
	if maxConcurrent <= 0 {
		maxConcurrent = 1
	}

	rl := &RateLimiter{
		maxConcurrent: maxConcurrent,
		tokens:        make(chan struct{}, maxConcurrent),
	}

	// Fill the token bucket
	for i := 0; i < maxConcurrent; i++ {
		rl.tokens <- struct{}{}
	}

	return rl
}

// Acquire blocks until a token is available or context is cancelled.
// Returns an error if the context is cancelled before a token is acquired.
func (rl *RateLimiter) Acquire(ctx context.Context) error {
	select {
	case <-rl.tokens:
		return nil
	case <-ctx.Done():
		return fmt.Errorf("rate limiter acquire cancelled: %w", ctx.Err())
	}
}

// TryAcquire attempts to acquire a token without blocking.
// Returns true if a token was acquired, false otherwise.
func (rl *RateLimiter) TryAcquire() bool {
	select {
	case <-rl.tokens:
		return true
	default:
		return false
	}
}

// AcquireWithTimeout attempts to acquire a token with a timeout.
func (rl *RateLimiter) AcquireWithTimeout(timeout time.Duration) error {
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()
	return rl.Acquire(ctx)
}

// Release returns a token to the bucket, allowing another operation to proceed.
func (rl *RateLimiter) Release() {
	select {
	case rl.tokens <- struct{}{}:
	default:
		// This should never happen if Acquire/Release are balanced
		// Log a warning in production
	}
}

// Available returns the number of available tokens.
func (rl *RateLimiter) Available() int {
	return len(rl.tokens)
}

// RateLimiterManager manages rate limiters for different service types.
type RateLimiterManager struct {
	limiters map[string]*RateLimiter
	mu       sync.RWMutex
}

// NewRateLimiterManager creates a manager with rate limiters for each service type.
func NewRateLimiterManager(config *Config) *RateLimiterManager {
	manager := &RateLimiterManager{
		limiters: make(map[string]*RateLimiter),
	}

	manager.limiters["researcher"] = NewRateLimiter(config.ResearcherRateLimit)
	manager.limiters["critic"] = NewRateLimiter(config.CriticRateLimit)
	manager.limiters["synthesizer"] = NewRateLimiter(config.SynthesizerRateLimit)

	return manager
}

// GetLimiter returns the rate limiter for a specific service type.
func (m *RateLimiterManager) GetLimiter(serviceType string) *RateLimiter {
	m.mu.RLock()
	defer m.mu.RUnlock()

	if limiter, ok := m.limiters[serviceType]; ok {
		return limiter
	}

	// Default: no limiting (create a high-capacity limiter)
	return NewRateLimiter(1000)
}

// SetLimiter sets or updates a rate limiter for a service type.
func (m *RateLimiterManager) SetLimiter(serviceType string, maxConcurrent int) {
	m.mu.Lock()
	defer m.mu.Unlock()

	m.limiters[serviceType] = NewRateLimiter(maxConcurrent)
}
