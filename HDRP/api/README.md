# gRPC Service Definitions

Protocol Buffer definitions for the polyglot interface between Go Orchestrator and Python Microservices.

- **`hdrp.proto`**: Service contracts for Planner, Worker, Critic, and Synthesizer

## Code Generation

Do not edit generated files manually.

```bash
# Go
protoc --go_out=. --go-grpc_out=. proto/hdrp.proto

# Python
python -m grpc_tools.protoc -Iproto --python_out=../services/shared --grpc_python_out=../services/shared proto/hdrp.proto
```
