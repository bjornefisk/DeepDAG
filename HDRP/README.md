# HDRP: Hierarchical Deep Research Planner

## Overview
HDRP is a research operating system that performs deep, verifiable research using a dynamically expanding Directed Acyclic Graph (DAG). It demonstrates that hierarchical planning and explicit verification outperform flat ReAct loops.

## Architecture
- **Orchestrator (Go):** Handles concurrency, DAG state management, and gRPC communication.
- **Services (Python):** AI-heavy tasks (Planning, Researching, Critiquing, Synthesizing).
- **Communication:** gRPC.

## Components
1. **Principal:** Generates the initial DAG.
2. **Researcher:** Executes tasks and finds facts.
3. **Critic:** Verifies claims against sources.
4. **Synthesizer:** Compiles verified info into reports.

