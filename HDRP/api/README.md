# API Definitions (gRPC/Protobuf)

This directory contains the canonical Protocol Buffer definitions (`.proto`) that define the interface between the Go Orchestrator and Python Microservices.

## Service Contracts

The system relies on strict strict typing across the polyglot boundary.

- **`hdrp.proto`**: Defines the `Planner`, `Worker`, `Critic`, and `Synthesizer` services.

## Code Generation

**Do not edit generated files manually.**

### Go (Orchestrator)
```bash
protoc --go_out=. --go-grpc_out=. proto/hdrp.proto
```

### Python (Services)
```bash
python -m grpc_tools.protoc -Iproto --python_out=../services/shared --grpc_python_out=../services/shared proto/hdrp.proto
```
