package concurrency

import (
	"context"
	"fmt"
	"log"
	"sync"
	"time"
)

// LockManager provides a factory for creating distributed locks based on configuration.
type LockManager struct {
	lock     DistributedLock
	provider string
	config   *Config
	mu       sync.RWMutex
}

// NewLockManager creates a lock manager based on the configuration.
func NewLockManager(config *Config) (*LockManager, error) {
	manager := &LockManager{
		provider: config.LockProvider,
		config:   config,
	}

	var err error
	switch config.LockProvider {
	case "etcd":
		manager.lock, err = NewEtcdLock(config.EtcdEndpoints)
		if err != nil {
			log.Printf("[LockManager] Failed to initialize etcd lock: %v, falling back to in-memory", err)
			manager.lock = NewInMemoryLock()
			manager.provider = "memory"
		}
	case "redis":
		manager.lock, err = NewRedisLock(config.RedisAddr)
		if err != nil {
			log.Printf("[LockManager] Failed to initialize redis lock: %v, falling back to in-memory", err)
			manager.lock = NewInMemoryLock()
			manager.provider = "memory"
		}
	case "none", "memory", "":
		manager.lock = NewInMemoryLock()
		manager.provider = "memory"
	default:
		return nil, fmt.Errorf("unsupported lock provider: %s", config.LockProvider)
	}

	log.Printf("[LockManager] Initialized with provider: %s", manager.provider)
	return manager, nil
}

// AcquireNodeLock acquires a lock for a node with retry logic.
func (lm *LockManager) AcquireNodeLock(ctx context.Context, nodeID string) (bool, error) {
	ttl := lm.config.LockTimeout
	return lm.lock.AcquireNodeLock(ctx, nodeID, ttl)
}

// AcquireNodeLockWithRetry attempts to acquire a lock with exponential backoff retry.
func (lm *LockManager) AcquireNodeLockWithRetry(ctx context.Context, nodeID string, maxRetries int) (bool, error) {
	backoff := 100 * time.Millisecond

	for attempt := 0; attempt < maxRetries; attempt++ {
		acquired, err := lm.AcquireNodeLock(ctx, nodeID)
		if err != nil {
			return false, err
		}
		if acquired {
			return true, nil
		}

		// Exponential backoff
		select {
		case <-time.After(backoff):
			backoff *= 2
			if backoff > 5*time.Second {
				backoff = 5 * time.Second
			}
		case <-ctx.Done():
			return false, ctx.Err()
		}
	}

	return false, nil
}

// ReleaseNodeLock releases a lock for a node.
func (lm *LockManager) ReleaseNodeLock(ctx context.Context, nodeID string) error {
	return lm.lock.ReleaseNodeLock(ctx, nodeID)
}

// ExtendLock extends the TTL of a lock.
func (lm *LockManager) ExtendLock(ctx context.Context, nodeID string) error {
	ttl := lm.config.LockTimeout
	return lm.lock.ExtendLock(ctx, nodeID, ttl)
}

// Close closes the underlying lock implementation.
func (lm *LockManager) Close() error {
	lm.mu.Lock()
	defer lm.mu.Unlock()

	if lm.lock != nil {
		return lm.lock.Close()
	}
	return nil
}

// HealthCheck verifies the lock backend is healthy.
func (lm *LockManager) HealthCheck(ctx context.Context) error {
	lm.mu.RLock()
	defer lm.mu.RUnlock()

	if lm.lock == nil {
		return fmt.Errorf("lock not initialized")
	}

	return lm.lock.HealthCheck(ctx)
}

// GetProvider returns the current lock provider name.
func (lm *LockManager) GetProvider() string {
	lm.mu.RLock()
	defer lm.mu.RUnlock()
	return lm.provider
}
