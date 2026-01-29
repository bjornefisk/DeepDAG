package config

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/spf13/viper"
)

// Config represents the application configuration
type Config struct {
	Environment string          `mapstructure:"environment"`
	Services    ServiceConfig   `mapstructure:"services"`
	Concurrency ConcurrencyConfig `mapstructure:"concurrency"`
	Storage     StorageConfig   `mapstructure:"storage"`
}

// ServiceConfig holds service discovery addresses
type ServiceConfig struct {
	Principal   ServiceAddress `mapstructure:"principal"`
	Researcher  ServiceAddress `mapstructure:"researcher"`
	Critic      ServiceAddress `mapstructure:"critic"`
	Synthesizer ServiceAddress `mapstructure:"synthesizer"`
}

// ServiceAddress represents a single service endpoint
type ServiceAddress struct {
	Address string `mapstructure:"address"`
}

// ConcurrencyConfig holds concurrency settings
type ConcurrencyConfig struct {
	MaxWorkers int         `mapstructure:"max_workers"`
	RateLimits RateLimits  `mapstructure:"rate_limits"`
	Lock       LockConfig  `mapstructure:"lock"`
	Timeouts   Timeouts    `mapstructure:"timeouts"`
}

// RateLimits holds per-service rate limits
type RateLimits struct {
	Researcher  int `mapstructure:"researcher"`
	Critic      int `mapstructure:"critic"`
	Synthesizer int `mapstructure:"synthesizer"`
}

// LockConfig holds distributed locking configuration
type LockConfig struct {
	Provider      string      `mapstructure:"provider"` // none, etcd, redis
	Etcd          EtcdConfig  `mapstructure:"etcd"`
	Redis         RedisConfig `mapstructure:"redis"`
	TimeoutSeconds int        `mapstructure:"timeout_seconds"`
}

// EtcdConfig holds etcd-specific settings
type EtcdConfig struct {
	Endpoints string `mapstructure:"endpoints"`
}

// RedisConfig holds Redis-specific settings
type RedisConfig struct {
	Address string `mapstructure:"address"`
}

// Timeouts holds execution timeout settings
type Timeouts struct {
	NodeExecutionMinutes int `mapstructure:"node_execution_minutes"`
	LockSeconds          int `mapstructure:"lock_seconds"`
}

// StorageConfig holds storage path configuration
type StorageConfig struct {
	Database DatabaseConfig `mapstructure:"database"`
}

// DatabaseConfig holds database-specific settings
type DatabaseConfig struct {
	Path string `mapstructure:"path"`
}

// Load reads configuration from YAML files and environment variables
//
// Configuration precedence (highest to lowest):
//  1. Environment variables (e.g., HDRP_SERVICES_PRINCIPAL_ADDRESS)
//  2. Environment-specific YAML (e.g., config.dev.yaml)
//  3. Base YAML (config.yaml)
//
// Args:
//   configPath: Path to base config file (e.g., "./config/config.yaml")
//
// Returns:
//   *Config: Loaded configuration
//   error: Any error encountered during loading
func Load(configPath string) (*Config, error) {
	v := viper.New()

	// Set config file path
	if configPath == "" {
		// Default to ../config/config.yaml from orchestrator directory
		configPath = filepath.Join("..", "config", "config.yaml")
	}

	v.SetConfigFile(configPath)

	// Read base config
	if err := v.ReadInConfig(); err != nil {
		// If config file doesn't exist, use defaults with env vars
		if !os.IsNotExist(err) {
			return nil, fmt.Errorf("failed to read config file: %w", err)
		}
	}

	// Load environment-specific overlay
	configDir := filepath.Dir(configPath)
	configExt := filepath.Ext(configPath)
	configBase := strings.TrimSuffix(filepath.Base(configPath), configExt)

	// Get environment from HDRP_ENV or config
	env := os.Getenv("HDRP_ENV")
	if env == "" {
		env = v.GetString("environment")
	}
	if env == "" {
		env = "development"
	}

	// Try to load environment-specific config
	envConfigPath := filepath.Join(configDir, fmt.Sprintf("%s.%s%s", configBase, env, configExt))
	if _, err := os.Stat(envConfigPath); err == nil {
		// Merge environment config
		v.SetConfigFile(envConfigPath)
		if err := v.MergeInConfig(); err != nil {
			return nil, fmt.Errorf("failed to merge environment config: %w", err)
		}
	}

	// Enable environment variable overrides
	v.SetEnvPrefix("HDRP")
	v.SetEnvKeyReplacer(strings.NewReplacer(".", "_"))
	v.AutomaticEnv()

	// Explicitly bind environment variables for nested config fields
	// This is needed because AutomaticEnv only works for keys Viper already knows about
	v.BindEnv("services.principal.address", "HDRP_SERVICES_PRINCIPAL_ADDRESS")
	v.BindEnv("services.researcher.address", "HDRP_SERVICES_RESEARCHER_ADDRESS")
	v.BindEnv("services.critic.address", "HDRP_SERVICES_CRITIC_ADDRESS")
	v.BindEnv("services.synthesizer.address", "HDRP_SERVICES_SYNTHESIZER_ADDRESS")
	v.BindEnv("concurrency.max_workers", "HDRP_CONCURRENCY_MAX_WORKERS")

	// Unmarshal into Config struct
	var cfg Config
	if err := v.Unmarshal(&cfg); err != nil {
		return nil, fmt.Errorf("failed to unmarshal config: %w", err)
	}

	// Validate required fields
	if err := validate(&cfg); err != nil {
		return nil, fmt.Errorf("config validation failed: %w", err)
	}

	return &cfg, nil
}

// validate checks required configuration fields
func validate(cfg *Config) error {
	if cfg.Services.Principal.Address == "" {
		return fmt.Errorf("services.principal.address is required")
	}
	if cfg.Services.Researcher.Address == "" {
		return fmt.Errorf("services.researcher.address is required")
	}
	if cfg.Services.Critic.Address == "" {
		return fmt.Errorf("services.critic.address is required")
	}
	if cfg.Services.Synthesizer.Address == "" {
		return fmt.Errorf("services.synthesizer.address is required")
	}

	if cfg.Concurrency.MaxWorkers <= 0 {
		return fmt.Errorf("concurrency.max_workers must be greater than 0")
	}

	return nil
}

// GetServiceAddress is a helper to retrieve a service address
func (c *Config) GetServiceAddress(service string) string {
	switch service {
	case "principal":
		return c.Services.Principal.Address
	case "researcher":
		return c.Services.Researcher.Address
	case "critic":
		return c.Services.Critic.Address
	case "synthesizer":
		return c.Services.Synthesizer.Address
	default:
		return ""
	}
}
