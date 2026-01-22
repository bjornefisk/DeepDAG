"""Centralized configuration management using Pydantic settings.

This module provides type-safe, validated configuration loading from:
1. YAML config files (config.yaml + environment overlays)
2. Environment variables (highest precedence)

Usage:
    from HDRP.services.shared.settings import get_settings
    
    settings = get_settings()
    api_key = settings.search.google_api_key.get_secret_value()
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional, Literal, List

import yaml
from pydantic import BaseSettings, SecretStr, Field, validator


# === Search Configuration ===

class GoogleSearchConfig(BaseSettings):
    """Google Custom Search configuration."""
    api_key: Optional[SecretStr] = Field(None, env="GOOGLE_API_KEY")
    cx: Optional[str] = Field(None, env="GOOGLE_CX")
    timeout_seconds: float = Field(8.0, env="GOOGLE_TIMEOUT_SECONDS")
    max_results: int = Field(10, env="GOOGLE_MAX_RESULTS")


class TavilySearchConfig(BaseSettings):
    """Tavily Search configuration."""
    api_key: Optional[SecretStr] = Field(None, env="TAVILY_API_KEY")
    search_depth: str = Field("basic", env="TAVILY_SEARCH_DEPTH")
    topic: str = Field("general", env="TAVILY_TOPIC")
    timeout_seconds: float = Field(8.0, env="TAVILY_TIMEOUT_SECONDS")
    max_results: int = Field(10, env="TAVILY_MAX_RESULTS")


class SearchConfig(BaseSettings):
    """Search provider configuration."""
    provider: str = Field("simulated", env="HDRP_SEARCH_PROVIDER")
    google: GoogleSearchConfig = GoogleSearchConfig()
    tavily: TavilySearchConfig = TavilySearchConfig()


# === NLI Configuration ===

class NLIConfig(BaseSettings):
    """NLI inference configuration."""
    backend: Literal["torch", "onnxruntime"] = Field("torch", env="HDRP_NLI_BACKEND")
    device: str = Field("auto", env="HDRP_NLI_DEVICE")
    batch_size: int = Field(8, env="HDRP_NLI_BATCH_SIZE")
    max_length: int = Field(256, env="HDRP_NLI_MAX_LENGTH")
    onnx_model_path: Optional[str] = Field(None, env="HDRP_NLI_ONNX_PATH")
    onnx_providers: List[str] = Field(default_factory=list, env="HDRP_NLI_ONNX_PROVIDERS")
    int8: bool = Field(False, env="HDRP_NLI_INT8")

    @validator("onnx_providers", pre=True)
    def normalize_onnx_providers(cls, v):
        if v is None or v == "":
            return []
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v


# === Service Discovery ===

class ServiceAddresses(BaseSettings):
    """gRPC service addresses."""
    principal: str = Field("localhost:50051", env="HDRP_PRINCIPAL_ADDR")
    researcher: str = Field("localhost:50052", env="HDRP_RESEARCHER_ADDR")
    critic: str = Field("localhost:50053", env="HDRP_CRITIC_ADDR")
    synthesizer: str = Field("localhost:50054", env="HDRP_SYNTHESIZER_ADDR")


# === Concurrency Configuration ===

class RateLimitsConfig(BaseSettings):
    """Per-service rate limits."""
    researcher: int = Field(5, env="RESEARCHER_RATE_LIMIT")
    critic: int = Field(3, env="CRITIC_RATE_LIMIT")
    synthesizer: int = Field(2, env="SYNTHESIZER_RATE_LIMIT")


class LockConfig(BaseSettings):
    """Distributed locking configuration."""
    provider: Literal["none", "etcd", "redis"] = Field("none", env="LOCK_PROVIDER")
    etcd_endpoints: str = Field("localhost:2379", env="ETCD_ENDPOINTS")
    redis_address: str = Field("localhost:6379", env="REDIS_ADDR")
    timeout_seconds: int = Field(30, env="LOCK_TIMEOUT")


class TimeoutsConfig(BaseSettings):
    """Execution timeouts."""
    node_execution_minutes: int = Field(5, env="NODE_EXECUTION_TIMEOUT")
    lock_seconds: int = Field(30, env="LOCK_TIMEOUT")


class ConcurrencyConfig(BaseSettings):
    """Concurrency and parallelism settings."""
    max_workers: int = Field(10, env="MAX_WORKERS")
    rate_limits: RateLimitsConfig = RateLimitsConfig()
    lock: LockConfig = LockConfig()
    timeouts: TimeoutsConfig = TimeoutsConfig()


# === Storage Configuration ===

class DatabaseConfig(BaseSettings):
    """Database configuration."""
    path: str = Field("./hdrp.db", env="HDRP_DB_PATH")


class StorageConfig(BaseSettings):
    """Storage paths configuration."""
    database: DatabaseConfig = DatabaseConfig()
    logs_directory: str = Field("./logs", env="HDRP_LOGS_DIR")
    artifacts_directory: str = Field("./artifacts", env="HDRP_ARTIFACTS_DIR")


# === Observability Configuration ===

class SentryConfig(BaseSettings):
    """Sentry error tracking configuration."""
    dsn: Optional[SecretStr] = Field(None, env="SENTRY_DSN")
    traces_sample_rate: float = Field(0.1, env="SENTRY_TRACES_SAMPLE_RATE")
    environment: str = Field("development", env="HDRP_ENV")


class ProfilingConfig(BaseSettings):
    """Performance profiling configuration."""
    enabled: bool = Field(False, env="HDRP_ENABLE_PROFILING")
    output_directory: str = Field("./profiling_data", env="PROFILING_OUTPUT_DIR")


class LoggingConfig(BaseSettings):
    """Logging configuration."""
    level: str = Field("INFO", env="LOG_LEVEL")
    format: Literal["json", "text"] = Field("json", env="LOG_FORMAT")


class ObservabilityConfig(BaseSettings):
    """Observability and monitoring settings."""
    sentry: SentryConfig = SentryConfig()
    profiling: ProfilingConfig = ProfilingConfig()
    logging: LoggingConfig = LoggingConfig()


# === Secret Management ===

class AWSSecretsConfig(BaseSettings):
    """AWS Secrets Manager configuration."""
    region: str = Field("us-west-2", env="AWS_REGION")
    secret_name_prefix: str = Field("hdrp/", env="AWS_SECRET_PREFIX")


class VaultConfig(BaseSettings):
    """HashiCorp Vault configuration."""
    address: str = Field("http://localhost:8200", env="VAULT_ADDR")
    token: Optional[SecretStr] = Field(None, env="VAULT_TOKEN")
    mount_path: str = Field("secret/hdrp", env="VAULT_MOUNT_PATH")


class SecretsConfig(BaseSettings):
    """Secret management configuration."""
    provider: Literal["environment", "aws_secrets_manager", "vault"] = Field(
        "environment", env="HDRP_SECRETS_PROVIDER"
    )
    aws: AWSSecretsConfig = AWSSecretsConfig()
    vault: VaultConfig = VaultConfig()


# === Main Settings ===

class HDRPSettings(BaseSettings):
    """Main HDRP configuration."""
    environment: str = Field("development", env="HDRP_ENV")
    search: SearchConfig = SearchConfig()
    nli: NLIConfig = NLIConfig()
    services: ServiceAddresses = ServiceAddresses()
    concurrency: ConcurrencyConfig = ConcurrencyConfig()
    storage: StorageConfig = StorageConfig()
    observability: ObservabilityConfig = ObservabilityConfig()
    secrets: SecretsConfig = SecretsConfig()

    class Config:
        env_file = ".env"
        env_nested_delimiter = "__"
        case_sensitive = False

    @validator("*", pre=True, always=True)
    def load_from_yaml(cls, v, field):
        """Load values from YAML config file if not already set."""
        # This validator will be called for each field
        # We'll load the YAML in get_settings() instead
        return v


def _load_yaml_config(config_path: Optional[Path] = None) -> dict:
    """Load configuration from YAML files with environment overlay.
    
    Args:
        config_path: Path to base config file. If None, searches for config.yaml
                    in HDRP root directory.
    
    Returns:
        Merged configuration dictionary.
    """
    if config_path is None:
        # Default to HDRP/config/config.yaml
        hdrp_root = Path(__file__).parent.parent.parent
        config_path = hdrp_root / "config" / "config.yaml"
    
    if not config_path.exists():
        # Return empty dict if no config file found (env vars will be used)
        return {}
    
    # Load base config
    with open(config_path, "r") as f:
        config = yaml.safe_load(f) or {}
    
    # Load environment-specific overlay
    env = os.getenv("HDRP_ENV", config.get("environment", "development"))
    env_config_path = config_path.parent / f"config.{env}.yaml"
    
    if env_config_path.exists():
        with open(env_config_path, "r") as f:
            env_config = yaml.safe_load(f) or {}
        
        # Deep merge environment config into base config
        config = _deep_merge(config, env_config)
    
    return config


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override dict into base dict.
    
    Args:
        base: Base configuration dictionary.
        override: Override values to merge.
    
    Returns:
        Merged dictionary.
    """
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    
    return result


def _flatten_config(config: dict, parent_key: str = "", sep: str = "__") -> dict:
    """Flatten nested config dict for Pydantic env var parsing.
    
    Args:
        config: Nested configuration dictionary.
        parent_key: Parent key for recursion.
        sep: Separator for nested keys.
    
    Returns:
        Flattened dictionary.
    """
    items = []
    
    for k, v in config.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        
        if isinstance(v, dict):
            items.extend(_flatten_config(v, new_key, sep).items())
        else:
            items.append((new_key, v))
    
    return dict(items)


@lru_cache(maxsize=1)
def get_settings(config_path: Optional[Path] = None) -> HDRPSettings:
    """Get cached settings instance.
    
    Configuration precedence (highest to lowest):
    1. Environment variables (e.g., HDRP_SEARCH_PROVIDER)
    2. Environment-specific YAML (e.g., config.dev.yaml)
    3. Base YAML config (config.yaml)
    
    Args:
        config_path: Optional path to base config file.
    
    Returns:
        Singleton HDRPSettings instance.
    """
    # Load YAML config
    yaml_config = _load_yaml_config(config_path)
    
    # Flatten for Pydantic parsing
    flat_config = _flatten_config(yaml_config)
    
    # Create settings (env vars will override YAML values)
    return HDRPSettings(**flat_config)


def reload_settings(config_path: Optional[Path] = None) -> HDRPSettings:
    """Force reload of settings (clears cache).
    
    Useful for testing or runtime config updates.
    
    Args:
        config_path: Optional path to base config file.
    
    Returns:
        New HDRPSettings instance.
    """
    get_settings.cache_clear()
    return get_settings(config_path)
