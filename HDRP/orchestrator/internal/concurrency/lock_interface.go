package concurrency

import (
	"context"
	"time"
)

// DistributedLock provides an interface for distributed locking mechanisms.
// Implementations can use etcd, Redis, or in-memory locks for single-instance deployments.
type DistributedLock interface {
	// AcquireNodeLock attempts to acquire an exclusive lock for a node.
	// Returns true if the lock was acquired, false if it's already held by another process.
	AcquireNodeLock(ctx context.Context, nodeID string, ttl time.Duration) (bool, error)

	// ReleaseNodeLock releases the lock for a node.
	ReleaseNodeLock(ctx context.Context, nodeID string) error

	// ExtendLock extends the TTL of an existing lock.
	ExtendLock(ctx context.Context, nodeID string, ttl time.Duration) error

	// Close cleans up resources and closes connections.
	Close() error

	// HealthCheck verifies the lock backend is accessible.
	HealthCheck(ctx context.Context) error
}

// LockMetrics tracks lock statistics.
type LockMetrics struct {
	AcquireAttempts int64
	AcquireSuccess  int64
	AcquireFailures int64
	ReleaseAttempts int64
	ReleaseSuccess  int64
	ReleaseFailures int64
	ExtendAttempts  int64
	ExtendSuccess   int64
	ExtendFailures  int64
}
