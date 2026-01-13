package concurrency

import (
	"os"
	"strconv"
	"time"
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

// LoadConfig reads configuration from environment variables with sensible defaults.
func LoadConfig() *Config {
	return &Config{
		MaxWorkers:            getEnvInt("MAX_WORKERS", 10),
		ResearcherRateLimit:   getEnvInt("RESEARCHER_RATE_LIMIT", 5),
		CriticRateLimit:       getEnvInt("CRITIC_RATE_LIMIT", 3),
		SynthesizerRateLimit:  getEnvInt("SYNTHESIZER_RATE_LIMIT", 2),
		LockProvider:          getEnvString("LOCK_PROVIDER", "none"),
		EtcdEndpoints:         getEnvString("ETCD_ENDPOINTS", "localhost:2379"),
		RedisAddr:             getEnvString("REDIS_ADDR", "localhost:6379"),
		LockTimeout:           getEnvDuration("LOCK_TIMEOUT", 30*time.Second),
		NodeExecutionTimeout:  getEnvDuration("NODE_EXECUTION_TIMEOUT", 5*time.Minute),
	}
}

func getEnvInt(key string, defaultValue int) int {
	if val := os.Getenv(key); val != "" {
		if parsed, err := strconv.Atoi(val); err == nil {
			return parsed
		}
	}
	return defaultValue
}

func getEnvString(key, defaultValue string) string {
	if val := os.Getenv(key); val != "" {
		return val
	}
	return defaultValue
}

func getEnvDuration(key string, defaultValue time.Duration) time.Duration {
	if val := os.Getenv(key); val != "" {
		if parsed, err := time.ParseDuration(val); err == nil {
			return parsed
		}
	}
	return defaultValue
}
