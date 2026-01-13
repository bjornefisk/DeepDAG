package concurrency

import (
	"context"
	"fmt"
	"sync"
	"time"
)

// InMemoryLock provides a simple in-memory lock for single-instance deployments.
// This is NOT suitable for multi-instance deployments.
type InMemoryLock struct {
	locks   map[string]*lockEntry
	mu      sync.RWMutex
	metrics LockMetrics
}

type lockEntry struct {
	expiresAt time.Time
	mu        sync.Mutex
}

// NewInMemoryLock creates an in-memory lock manager.
func NewInMemoryLock() *InMemoryLock {
	lock := &InMemoryLock{
		locks: make(map[string]*lockEntry),
	}

	// Start background cleanup goroutine
	go lock.cleanupExpiredLocks()

	return lock
}

// AcquireNodeLock attempts to acquire a lock for a node.
func (l *InMemoryLock) AcquireNodeLock(ctx context.Context, nodeID string, ttl time.Duration) (bool, error) {
	l.mu.Lock()
	defer l.mu.Unlock()

	l.metrics.AcquireAttempts++

	// Check if lock exists and is not expired
	if entry, exists := l.locks[nodeID]; exists {
		if time.Now().Before(entry.expiresAt) {
			l.metrics.AcquireFailures++
			return false, nil
		}
		// Lock expired, remove it
		delete(l.locks, nodeID)
	}

	// Acquire the lock
	l.locks[nodeID] = &lockEntry{
		expiresAt: time.Now().Add(ttl),
	}

	l.metrics.AcquireSuccess++
	return true, nil
}

// ReleaseNodeLock releases a lock for a node.
func (l *InMemoryLock) ReleaseNodeLock(ctx context.Context, nodeID string) error {
	l.mu.Lock()
	defer l.mu.Unlock()

	l.metrics.ReleaseAttempts++

	if _, exists := l.locks[nodeID]; !exists {
		l.metrics.ReleaseFailures++
		return fmt.Errorf("lock for node %s does not exist", nodeID)
	}

	delete(l.locks, nodeID)
	l.metrics.ReleaseSuccess++
	return nil
}

// ExtendLock extends the TTL of an existing lock.
func (l *InMemoryLock) ExtendLock(ctx context.Context, nodeID string, ttl time.Duration) error {
	l.mu.Lock()
	defer l.mu.Unlock()

	l.metrics.ExtendAttempts++

	entry, exists := l.locks[nodeID]
	if !exists {
		l.metrics.ExtendFailures++
		return fmt.Errorf("lock for node %s does not exist", nodeID)
	}

	entry.expiresAt = time.Now().Add(ttl)
	l.metrics.ExtendSuccess++
	return nil
}

// Close is a no-op for in-memory locks.
func (l *InMemoryLock) Close() error {
	return nil
}

// HealthCheck always returns nil for in-memory locks.
func (l *InMemoryLock) HealthCheck(ctx context.Context) error {
	return nil
}

// GetMetrics returns the current lock metrics.
func (l *InMemoryLock) GetMetrics() LockMetrics {
	l.mu.RLock()
	defer l.mu.RUnlock()
	return l.metrics
}

// cleanupExpiredLocks periodically removes expired locks.
func (l *InMemoryLock) cleanupExpiredLocks() {
	ticker := time.NewTicker(10 * time.Second)
	defer ticker.Stop()

	for range ticker.C {
		l.mu.Lock()
		now := time.Now()
		for nodeID, entry := range l.locks {
			if now.After(entry.expiresAt) {
				delete(l.locks, nodeID)
			}
		}
		l.mu.Unlock()
	}
}
