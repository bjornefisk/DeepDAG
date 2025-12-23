# Synthesizer Agent

## Responsibility
Compiles verified claims into the final user-facing artifact.

## Interface
- **Input:** `VerifiedDAG (Graph)`
- **Output:** `Report (Markdown)`

## Invariants
- **Zero Hallucination:** The synthesizer is strictly forbidden from adding external information not present in the verified DAG nodes.
- **Citation:** Every claim in the final report must link to its source URL.