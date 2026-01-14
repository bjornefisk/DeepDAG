package retry

import (
	"testing"
	"time"
)

func TestDefaultPolicy(t *testing.T) {
	policy := DefaultPolicy()
	
	if policy.MaxAttempts != 3 {
		t.Errorf("Expected MaxAttempts=3, got %d", policy.MaxAttempts)
	}
	if policy.InitialDelay != 1*time.Second {
		t.Errorf("Expected InitialDelay=1s, got %v", policy.InitialDelay)
	}
	if policy.BackoffMultiplier != 2.0 {
		t.Errorf("Expected BackoffMultiplier=2.0, got %f", policy.BackoffMultiplier)
	}
	if policy.MaxDelay != 30*time.Second {
		t.Errorf("Expected MaxDelay=30s, got %v", policy.MaxDelay)
	}
}

func TestExponentialBackoff(t *testing.T) {
	policy := &RetryPolicy{
		InitialDelay:      100 * time.Millisecond,
		BackoffMultiplier: 2.0,
		MaxDelay:          1 * time.Second,
	}

	tests := []struct {
		attempt  int
		expected time.Duration
	}{
		{0, 100 * time.Millisecond},  // 100ms * 2^0 = 100ms
		{1, 200 * time.Millisecond},  // 100ms * 2^1 = 200ms
		{2, 400 * time.Millisecond},  // 100ms * 2^2 = 400ms
		{3, 800 * time.Millisecond},  // 100ms * 2^3 = 800ms
		{4, 1 * time.Second},         // 100ms * 2^4 = 1600ms, capped at 1s
		{5, 1 * time.Second},         // Capped at max delay
	}

	for _, tt := range tests {
		result := ExponentialBackoff(policy, tt.attempt)
		if result != tt.expected {
			t.Errorf("Attempt %d: expected %v, got %v", tt.attempt, tt.expected, result)
		}
	}
}

func TestShouldRetry(t *testing.T) {
	policy := &RetryPolicy{MaxAttempts: 3}

	tests := []struct {
		attempt  int
		expected bool
	}{
		{0, true},
		{1, true},
		{2, true},
		{3, false}, // Exhausted
		{4, false},
	}

	for _, tt := range tests {
		result := policy.ShouldRetry(tt.attempt)
		if result != tt.expected {
			t.Errorf("Attempt %d: expected %v, got %v", tt.attempt, tt.expected, result)
		}
	}
}
