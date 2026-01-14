package retry

import (
	"math"
	"time"
)

// RetryPolicy defines the configuration for retry attempts.
type RetryPolicy struct {
	MaxAttempts      int           // Maximum number of retry attempts (0 = no retries, 1+ = that many retries after initial attempt)
	InitialDelay     time.Duration // Initial delay before first retry
	BackoffMultiplier float64       // Multiplier for exponential backoff
	MaxDelay         time.Duration // Maximum delay between retries
}

// DefaultPolicy returns a sensible default retry policy.
// Max 3 retries (4 total attempts), starting at 1s with 2x backoff, capped at 30s.
func DefaultPolicy() *RetryPolicy {
	return &RetryPolicy{
		MaxAttempts:      3,
		InitialDelay:     1 * time.Second,
		BackoffMultiplier: 2.0,
		MaxDelay:         30 * time.Second,
	}
}

// ExponentialBackoff calculates the delay for a given retry attempt.
// attempt is 0-indexed (0 = first retry, 1 = second retry, etc.)
func ExponentialBackoff(policy *RetryPolicy, attempt int) time.Duration {
	if attempt < 0 {
		attempt = 0
	}

	// Calculate: initialDelay * multiplier^attempt
	delay := float64(policy.InitialDelay) * math.Pow(policy.BackoffMultiplier, float64(attempt))
	
	// Cap at max delay
	if delay > float64(policy.MaxDelay) {
		delay = float64(policy.MaxDelay)
	}

	return time.Duration(delay)
}

// ShouldRetry determines if another retry attempt should be made.
func (p *RetryPolicy) ShouldRetry(attempt int) bool {
	return attempt < p.MaxAttempts
}
