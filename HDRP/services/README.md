# AI Microservices (Python)

This directory hosts the semantic reasoning agents. Each agent is designed as a stateless microservice that responds to gRPC requests from the Go Orchestrator.

## Environment Setup

We use a shared virtual environment for all services to simplify dependency management during the prototype phase.

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Shared Utilities
- `shared/`: Contains the generated gRPC code and the structured logger (`logger.py`).