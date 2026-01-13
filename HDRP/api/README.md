# gRPC Service Definitions

Protocol Buffer definitions for the polyglot interface between Go Orchestrator and Python Microservices.

- **`hdrp.proto`**: Service contracts for Planner, Worker, Critic, and Synthesizer
- **`hdrp_services.proto`**: Service definitions with validation rules and REST gateway annotations

## Features

- **Field Validation**: Using buf/protovalidate for runtime validation (query length, required fields, confidence score ranges)
- **gRPC-Gateway**: REST API endpoints automatically mapped from gRPC services  
- **OpenAPI Spec**: Auto-generated API documentation from protobuf annotations
- **Buf Linting**: Enforced protobuf best practices and style guidelines

## Code Generation

Do not edit generated files manually.

### Prerequisites

Install buf CLI (one-time setup):
```bash
# Linux/macOS
go install github.com/bufbuild/buf/cmd/buf@latest

# Or via brew
brew install bufbuild/buf/buf
```

### Generate All Code

```bash
cd api

# Lint protobuf files
buf lint

# Generate Go, Python, gRPC-Gateway, and OpenAPI specs
buf generate

# The generated files will be in:
# - gen/go/          (Go protobuf + gRPC)
# - gen/python/      (Python protobuf + gRPC)
# - openapi/         (OpenAPI/Swagger specs)
```

### Legacy Commands (deprecated)

The old protoc commands still work but are deprecated in favor of buf:

```bash
# Go (deprecated - use buf generate instead)
protoc --go_out=. --go-grpc_out=. proto/hdrp.proto proto/hdrp_services.proto

# Python (deprecated - use buf generate instead)  
python -m grpc_tools.protoc -Iproto --python_out=../services/shared --grpc_python_out=../services/shared proto/hdrp.proto proto/hdrp_services.proto
```

## REST API Endpoints

The gRPC-Gateway provides REST endpoints:

- `POST /v1/decompose` - Decompose query into DAG (Principal Service)
- `POST /v1/research` - Conduct research and extract claims (Researcher Service)
- `POST /v1/verify` - Verify claims (Critic Service)
- `POST /v1/synthesize` - Generate final report (Synthesizer Service)

See `openapi/apidocs.swagger.json` for complete API documentation.

## Validation Rules

All services enforce the following validations:

- **query**: 1-500 characters, non-empty, no whitespace-only
- **run_id**: Required, non-empty
- **confidence**: 0.0-1.0 range
- **claims/results**: Minimum 1 item required for verification and synthesis

Invalid requests return gRPC status `INVALID_ARGUMENT` (HTTP 400).

