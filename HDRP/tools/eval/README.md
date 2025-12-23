# Evaluation Suite

This directory contains the benchmarking harness used to compare HDRP against baseline ReAct agents.

## Metrics
1.  **Claim Accuracy:** Percentage of claims supported by their cited source.
2.  **Trajectory Efficiency:** Ratio of useful nodes to total nodes explored.
3.  **Hallucination Rate:** Frequency of unverified claims entering the final report.

## Usage
```bash
python benchmark.py --baseline=react --system=hdrp --task=complex_research
```
