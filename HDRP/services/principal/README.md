# Principal Agent (Planner)

## Responsibility
Decomposes high-level user queries into a dependency graph of atomic sub-questions.

## Interface
- **Input:** `UserQuery (string)`
- **Output:** `DAG (Nodes[], Edges[])`

## Implementation Notes
- **No Web Access:** The planner relies solely on its internal world model to generate the initial plan.
- **Dynamic Updates:** Can receive signals from the Orchestrator to "re-plan" based on new context.