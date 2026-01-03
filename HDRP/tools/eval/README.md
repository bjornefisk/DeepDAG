# Evaluation Suite

Benchmarking harness for comparing HDRP against baseline ReAct agents.

## Quick Start

```bash
# Run comparison (simulated provider, deterministic)
python -m HDRP.tools.eval.compare --provider simulated

# Run with real web search (requires TAVILY_API_KEY)
export TAVILY_API_KEY="your-key"
python -m HDRP.tools.eval.compare --provider tavily

# Show detailed breakdown
python -m HDRP.tools.eval.compare --provider simulated --detailed

# Filter by complexity
python -m HDRP.tools.eval.compare --complexity complex --provider simulated
```

## Metrics

| Category | Metrics |
| :--- | :--- |
| **Performance** | Total time, search latency, API calls |
| **Quality** | Claims extracted/verified, source diversity |
| **Trajectory** | Relevant claims ratio, search efficiency |
| **Hallucination** | Claims without attribution, risk score (0-1) |

## Components

- **test_queries.py** — Test suite across 3 complexity levels (simple, medium, complex)
- **metrics.py** — Metric collection and computation
- **results_formatter.py** — Rich-formatted console output
- **compare.py** — Main orchestrator for comparative runs
- **react_agent.py** — Minimal ReAct baseline

## Expected Results

HDRP demonstrates:
- ✓ Lower hallucination rate (explicit Critic verification)
- ✓ Higher source diversity (hierarchical decomposition)
- ✓ Better trajectory efficiency (relevant claims ratio)
- ⚠️ Potentially higher latency (quality vs speed trade-off)

## Adding Tests

Edit `test_queries.py`:

```python
COMPLEX_QUERIES.append(
    TestQuery(
        id="complex_04",
        question="Your question here",
        complexity=QueryComplexity.COMPLEX,
        description="Brief description",
        expected_subtopics=["topic1", "topic2"],
    )
)
```
