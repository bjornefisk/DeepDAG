# HDRP (Hierarchical Deep Research Planner)

![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg) ![Status](https://img.shields.io/badge/Status-Prototype-yellow)

HDRP is a research engine designed to mitigate **trajectory drift** in autonomous agents. It replaces standard flat ReAct loops with a **hierarchical, verifiable Directed Acyclic Graph (DAG)**, enforcing global constraints on long-horizon reasoning tasks.

## Problem

Standard ReAct agents lack hierarchical structure: without explicit state management and verification, errors compound and objectives drift. HDRP solves this by decoupling **Planning**, **Execution**, and **Verification** into specialized components.

**Core insight:** Deep research is a graph traversal problem requiring explicit state management (Go) and semantic reasoning (Python).

## System Architecture

HDRP implements a **compound AI system** using a polyglot architecture.
*   **Orchestrator (Go):** Handles concurrency, DAG state management, and race conditions.
*   **Microservices (Python):** Handle semantic tasks via gRPC.

### The Agent Hierarchy

| Component | Role | Systems Analogy |
| :--- | :--- | :--- |
| **Principal** | Decomposes queries into a dependency graph. **No external tool access.** | Query Planner / Compiler Frontend |
| **Researcher** | Executes atomic leaf nodes. Returns structured claims, not prose. | Map Worker / IO Thread |
| **Critic** | Validates claims against source text. Rejects unverified outputs. | Static Analyzer / Unit Test |
| **Synthesizer** | Compiles verified leaf nodes into the final artifact. | Linker / Reducer |

## Key Mechanisms

### Dynamic Graph Expansion
The **Researcher** identifies new entities during execution, which the **Principal** evaluates against the global objective. New sub-graphs are injected at runtime, allowing the plan to evolve without losing context.

### Explicit Verification
An adversarial **Critic** validates that each claim's supporting text entails the claim and originates from the cited source. Unverified claims are rejected and retried with updated constraints.

### Structured Logging
All state transitions (DAG mutations, verifications) are serialized to `HDRP/logs/<run_id>.jsonl` for reproducibility and A/B testing.

## Directory Structure

```text
HDRP/
├── orchestrator/       # Go: Core DAG engine & gRPC server
├── services/           # Python: AI Agents (Principal, Researcher, Critic)
├── api/proto/          # gRPC Service Definitions
├── tools/eval/         # Benchmarking suite
├── tools/search/       # Search providers (simulated, Tavily, etc.)
├── artifacts/          # Generated research artifacts (reports + DAGs)
├── cli.py              # Python CLI entry point
└── logs/               # Structured execution traces
```

## CLI Usage

### Installation

- **Create and activate a virtual environment** (recommended), then install Python dependencies:

```bash
cd DeepDAG
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
pip install -r HDRP/services/requirements.txt
```

### Running the HDRP CLI

- **Basic research query using Tavily** (real web search, requires API key):

```bash
export TAVILY_API_KEY="your-tavily-api-key"
python -m HDRP.cli run --query "Latest developments in quantum computing" --provider tavily
```

- **Use the simulated provider** (no external calls, deterministic):

```bash
python -m HDRP.cli run --query "Test query" --provider simulated
```

- **Write the report to a file**:

```bash
python -m HDRP.cli \
  run \
  --query "AI research trends in 2025" \
  --provider tavily \
  --output hdrp_report.md
```

If you later add a `hdrp` entry point via `pyproject.toml`, you will be able to run:

```bash
hdrp run --query "Latest developments in quantum computing" --provider tavily
```

The CLI runs the full Python pipeline:

- **Search** via `HDRP.tools.search` (Tavily or simulated)
- **Research** using `ResearcherService` (extracts atomic claims with traceability)
- **Critic** using `CriticService` (verifies and filters claims)
- **Synthesis** using `SynthesizerService` (generates a markdown report with citations)

## License

Licensed under the Apache License 2.0. See [HDRP/LICENSE](HDRP/LICENSE) for details.
