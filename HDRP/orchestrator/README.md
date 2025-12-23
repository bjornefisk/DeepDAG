# Orchestrator (Go)

The high-performance core responsible for DAG state management and concurrency control.

## Responsibilities

1.  **DAG Consistency:** Ensures the graph remains acyclic during dynamic expansion.
2.  **Concurrency:** Manages worker pools for parallel research tasks using Goroutines.
3.  **RPC Dispatch:** Routes logical tasks (Plan, Research, Verify) to the appropriate gRPC stub.
4.  **Logging:** Centralized structured logging for run reproducibility.

## Key Packages

- `cmd/server`: Entry point. Initializes the gRPC server and DAG manager.
- `internal/dag`: Thread-safe graph data structure with expansion logic.
- `internal/grpc`: Service implementations handling Protobuf requests.

## Development

```bash
# Run locally
go run cmd/server/main.go

# Test with race detection (Critical)
go test -race ./...
```