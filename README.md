# HDRP (Hierarchical Deep Research Planner)

![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg) ![Status](https://img.shields.io/badge/Status-Prototype-yellow)

HDRP is a research engine designed to mitigate **trajectory drift** in autonomous agents. It replaces standard flat ReAct loops with a **hierarchical, verifiable Directed Acyclic Graph (DAG)**, enforcing global constraints on long-horizon reasoning tasks.

## Abstract

Current open-ended agents suffer from a fundamental control problem: without hierarchical structure, the probability of diverging from the primary objective increases with each reasoning step. HDRP addresses this by decoupling **Planning**, **Execution**, and **Verification** into specialized, adversarial components.

## Core Problem: The Failure of ReAct

Standard ReAct loops (`THINK` → `SEARCH` → `ACT`) function as state-limited random walks.
1.  **Context Pollution:** Irrelevant search artifacts saturate the context window.
2.  **Loss of Global Objective:** The agent optimizes for the local next step rather than the global goal.
3.  **Lack of Rollback:** Errors in early steps propagate unchecked, compounding into hallucinations.

**Thesis:** Deep research is a graph traversal problem, not a sequence generation problem. It requires explicit state management (Go) and semantic reasoning (Python).

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

### 1. Dynamic Graph Expansion (Runtime Mutation)
Static plans are insufficient for exploratory domains. HDRP supports **online planning**:
*   The **Researcher** identifies new entities or dependencies during execution.
*   The **Principal** evaluates these signals against the global objective.
*   New sub-graphs are injected into the DAG at runtime, allowing the plan to evolve without losing the root objective.

### 2. Explicit Verification (The Critic)
To combat hallucination, we implement an adversarial "Critic" loop:
*   **Invariant:** No claim propagates to the Synthesizer without passing verification.
*   **Method:** The Critic verifies that `supporting_text` strictly entails `claim` and originates from `source_url`.
*   **Reflexion:** Rejected claims trigger a retry logic with updated constraints.

### 3. Traceability & Evaluation
We adopt an **evals-first** methodology.
*   **Structured Logging:** All state transitions (DAG mutations, claim verifications) are serialized to `HDRP/logs/<run_id>.jsonl`.
*   **Reproducibility:** Deterministic DAG traversals allow for A/B testing of planner logic.

## Directory Structure

```text
HDRP/
├── orchestrator/       # Go: Core DAG engine & gRPC server
├── services/           # Python: AI Agents (Principal, Researcher, Critic)
├── api/proto/          # gRPC Service Definitions
├── tools/eval/         # Benchmarking suite
└── logs/               # Structured execution traces
```

## License

Licensed under the Apache License 2.0. See [HDRP/LICENSE](HDRP/LICENSE) for details.
