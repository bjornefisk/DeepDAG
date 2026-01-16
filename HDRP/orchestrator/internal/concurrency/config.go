package concurrency

import (
	"time"

	"hdrp/internal/config"
)

// Config holds concurrency-related configuration.
type Config struct {
	MaxWorkers            int
	ResearcherRateLimit   int
	CriticRateLimit       int
	SynthesizerRateLimit  int
	LockProvider          string
	EtcdEndpoints         string
	RedisAddr             string
	LockTimeout           time.Duration
	NodeExecutionTimeout  time.Duration
}

// NewConfig creates a concurrency config from the main configuration.
//
// This factory replaces the old LoadConfig() function that used os.Getenv directly.
// Now all configuration comes from centralized config loaded by Viper.
func NewConfig(cfg *config.Config) *Config {
	return &Config{
		MaxWorkers:           cfg.Concurrency.MaxWorkers,
		ResearcherRateLimit:  cfg.Concurrency.RateLimits.Researcher,
		CriticRateLimit:      cfg.Concurrency.RateLimits.Critic,
		SynthesizerRateLimit: cfg.Concurrency.RateLimits.Synthesizer,
		LockProvider:         cfg.Concurrency.Lock.Provider,
		EtcdEndpoints:        cfg.Concurrency.Lock.Etcd.Endpoints,
		RedisAddr:            cfg.Concurrency.Lock.Redis.Address,
		LockTimeout:          time.Duration(cfg.Concurrency.Lock.TimeoutSeconds) * time.Second,
		NodeExecutionTimeout: time.Duration(cfg.Concurrency.Timeouts.NodeExecutionMinutes) * time.Minute,
	}
}
