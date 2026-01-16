# Configuration Management

This document explains the centralized configuration system for HDRP.

## Overview

HDRP uses a centralized configuration system based on YAML files with environment-specific overlays and environment variable overrides. This replaces scattered `os.getenv()` calls throughout the codebase.

**Technology Stack:**
- **Python**: Pydantic v2 BaseSettings for type-safe configuration
- **Go**: Viper for YAML loading and environment variable binding
- **Config Files**: YAML with environment-specific overlays

## Configuration Precedence

Configuration values are resolved in the following order (highest to lowest):

1. **Environment Variables** (highest precedence)
   - Python: `HDRP_SEARCH_PROVIDER=google`
   - Go: `HDRP_SERVICES_PRINCIPAL_ADDRESS=localhost:50051`

2. **Environment-Specific YAML** 
   - `config/config.dev.yaml` (development)
   - `config/config.staging.yaml` (staging)
   - `config/config.prod.yaml` (production)

3. **Base YAML** (lowest precedence)
   - `config/config.yaml`

##Files Structure

```
HDRP/
├── config/
│   ├── config.yaml              # Base configuration
│   ├── config.dev.yaml          # Development overrides
│   ├── config.staging.yaml      # Staging overrides
│   └── config.prod.yaml         # Production overrides
├── services/shared/
│   ├── settings.py              # Python Pydantic settings
│   └── secrets.py               # Secret management abstraction
└── orchestrator/internal/config/
    └── settings.go              # Go Viper configuration
```

## Usage

### Python Services

```python
from HDRP.services.shared.settings import get_settings

# Get settings singleton
settings = get_settings()

# Access configuration
search_provider = settings.search.provider
max_workers = settings.concurrency.max_workers

# Access secrets (SecretStr)
if settings.search.google.api_key:
    api_key = settings.search.google.api_key.get_secret_value()
```

### Go Orchestrator

```go
import "hdrp/internal/config"

// Load configuration
cfg, err := config.Load("../config/config.yaml")
if err != nil {
    log.Fatalf("Failed to load config: %v", err)
}

// Access configuration
principalAddr := cfg.Services.Principal.Address
maxWorkers := cfg.Concurrency.MaxWorkers
```

### Command-Line Interface

```bash
# Python CLI - uses settings automatically
python -m HDRP.cli run --query "test quantum entanglement"

# Override via environment variables
HDRP_SEARCH_PROVIDER=google \
GOOGLE_API_KEY=your_key \
python -m HDRP.cli run --query "test"

# Override max workers
HDRP_CONCURRENCY_MAX_WORKERS=20 python -m HDRP.cli run --query "test"

# Go orchestrator - with custom config
cd HDRP/orchestrator
./server --config ../config/config.yaml --port 50055

# Override via environment
HDRP_CONCURRENCY_MAX_WORKERS=20 ./server
```

## Environment Switching

Set the `HDRP_ENV` environment variable to switch between configurations:

```bash
# Use development config
HDRP_ENV=dev python -m HDRP.cli run --query "test"

# Use staging config
HDRP_ENV=staging python -m HDRP.cli run --query "test"

# Use production config
HDRP_ENV=prod python -m HDRP.cli run --query "test"
```

## Configuration Sections

### Search Providers

Configure search provider settings:

```yaml
search:
  provider: simulated  # simulated, google, tavily
  google:
    api_key: ""        # Set via env var or secret manager
    cx: ""
    timeout_seconds: 8.0
    max_results: 10
```

**Environment Variables:**
- `HDRP_SEARCH_PROVIDER`
- `GOOGLE_API_KEY`
- `GOOGLE_CX`
- `GOOGLE_TIMEOUT_SECONDS`
- `GOOGLE_MAX_RESULTS`

### Service Discovery

Configure gRPC service addresses:

```yaml
services:
  principal:
    address: localhost:50051
  researcher:
    address: localhost:50052
  critic:
    address: localhost:50053
  synthesizer:
    address: localhost:50054
```

**Environment Variables:**
- `HDRP_SERVICES_PRINCIPAL_ADDRESS`
- `HDRP_SERVICES_RESEARCHER_ADDRESS`
- `HDRP_SERVICES_CRITIC_ADDRESS`
- `HDRP_SERVICES_SYNTHESIZER_ADDRESS`

### Concurrency

Configure worker pools and rate limits:

```yaml
concurrency:
  max_workers: 10
  rate_limits:
    researcher: 5
    critic: 3
    synthesizer: 2
  lock:
    provider: none  # none, etcd, redis
    timeout_seconds: 30
```

**Environment Variables:**
- `HDRP_CONCURRENCY_MAX_WORKERS`
- `HDRP_CONCURRENCY_RATE_LIMITS_RESEARCHER`
- `LOCK_PROVIDER`
- `ETCD_ENDPOINTS`
- `REDIS_ADDR`

### Observability

Configure Sentry, profiling, and logging:

```yaml
observability:
  sentry:
    dsn: ""  # Set via env var or secret manager
    traces_sample_rate: 0.1
    environment: development
  profiling:
    enabled: false
  logging:
    level: INFO
    format: json
```

**Environment Variables:**
- `SENTRY_DSN`
- `HDRP_ENV`
- `HDRP_ENABLE_PROFILING`
- `LOG_LEVEL`

## Secret Management

HDRP supports multiple secret providers:

### Environment Variables (Default)

```bash
export GOOGLE_API_KEY=your_key
export SENTRY_DSN=your_dsn
```

### AWS Secrets Manager

```yaml
secrets:
  provider: aws_secrets_manager
  aws:
    region: us-west-2
    secret_name_prefix: hdrp/production/
```

Requires `boto3` and AWS credentials configured.

### HashiCorp Vault

```yaml
secrets:
  provider: vault
  vault:
    address: http://localhost:8200
    mount_path: secret/hdrp
```

Requires `hvac` and `VAULT_TOKEN` environment variable.

### Programmatic Usage

```python
from HDRP.services.shared.secrets import get_secret_provider

provider = get_secret_provider()  # Auto-detects from settings
api_key = provider.get_secret("google_api_key")
```

## Validation

Configuration is automatically validated on load:

**Python**: Pydantic validates types and required fields
**Go**: Custom validation ensures required service addresses are set

Invalid configurations will raise errors with helpful messages.

## Migration from Environment Variables

### Before
```python
import os
api_key = os.getenv("GOOGLE_API_KEY")
provider = os.getenv("HDRP_SEARCH_PROVIDER", "simulated")
```

### After
```python
from HDRP.services.shared.settings import get_settings

settings = get_settings()
provider = settings.search.provider

if settings.search.google.api_key:
    api_key = settings.search.google.api_key.get_secret_value()
```

## Best Practices

1. **Development**: Use `config.dev.yaml` with simulated providers
2. **Staging**: Use `config.staging.yaml` with real APIs and test credentials
3. **Production**: Use `config.prod.yaml` with secret manager integration
4. **Secrets**: Never commit secrets to YAML files - use environment variables or secret managers
5. **Overrides**: Use environment variables for runtime overrides without changing code

## Troubleshooting

### Configuration not loading

Check that config files exist:
```bash
ls -la HDRP/config/
```

### Environment variables not working

Ensure proper naming:
- Python: Use nested delimiters `HDRP_SEARCH__PROVIDER` or flat `HDRP_SEARCH_PROVIDER`
- Go: Use underscores `HDRP_SERVICES_PRINCIPAL_ADDRESS`

### Secrets not resolving

1. Check secret provider configuration
2. Verify AWS/Vault credentials
3. Check secret key prefix matches
4. Review logs for warnings

## Examples

See the test suite for comprehensive examples:
- Python settings: `HDRP/services/shared/test_settings.py` (to be created)
- Search factory: `HDRP/tools/search/test_search.py`
- Go config: `HDRP/orchestrator/internal/config/settings_test.go` (to be created)
