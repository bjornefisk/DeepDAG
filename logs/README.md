# Execution Logs

This directory stores the structured trace artifacts for every system run.

## Schema
Logs are stored in **JSON Lines (`.jsonl`)** format to support streaming analysis.

```json
{"timestamp": "...", "run_id": "...", "component": "critic", "event": "verification_failure", "payload": {...}}
```

## Purpose
These logs are the ground truth for the **Evals** pipeline. They allow us to replay a research session and identify exactly where "Trajectory Drift" occurred.
