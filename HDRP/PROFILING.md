# Profiling and Optimization Guide

## Overview

This document describes the profiling and optimization infrastructure added to DeepDAG to improve query execution performance.

## Optimizations Implemented

### 1. Researcher Service
- **Concurrent claim extraction**: Uses ThreadPoolExecutor to process multiple search results in parallel
- **Profiling integration**: Optional profiling via `HDRP_ENABLE_PROFILING` environment variable

**Performance impact**: Reduces claim extraction time by processing search results concurrently instead of sequentially.

### 2. Critic Service
- **Tokenization caching**: Caches tokenized text to avoid redundant string processing
- **Batch verification**: New `verify_batch()` method for concurrent verification of multiple claim sets
- **Thread pool**: Uses ThreadPoolExecutor for parallel processing

**Performance impact**: Significantly reduces verification time for large claim sets through caching and parallelization.

### 3. NLI Inference Acceleration
- **Backend selection**: Choose PyTorch or ONNX Runtime via config/env
- **GPU/CPU auto-selection**: Configure device for deployment-specific latency targets
- **INT8 quantization**: Optional ONNX INT8 model for faster CPU inference

**Performance impact**: Reduces entailment scoring latency per claim without changing core verification logic.

### 3. Go Orchestrator
- **pprof endpoints**: Enabled runtime profiling at `/debug/pprof/`
- Endpoints available:
  - `/debug/pprof/` - Index of available profiles
  - `/debug/pprof/profile` - CPU profile
  - `/debug/pprof/heap` - Memory profile
  - `/debug/pprof/goroutine` - Goroutine dump

## Using Profiling Tools

### Python Services

#### Enable Profiling
```bash
export HDRP_ENABLE_PROFILING=1
```

#### View Profiling Data
Profiling data is saved to `profiling_data/` directory when enabled.

```bash
# View with snakeviz (interactive)
snakeviz profiling_data/search_*.prof

# View with pstats (command line)
python -m pstats profiling_data/claim_extraction_*.prof
```

### Go Orchestrator

#### CPU Profile
```bash
# Capture 30-second CPU profile
go tool pprof http://localhost:50055/debug/pprof/profile?seconds=30

# Analyze in interactive mode
(pprof) top10
(pprof) list <function_name>
(pprof) web  # Opens browser visualization
```

#### Memory Profile
```bash
go tool pprof http://localhost:50055/debug/pprof/heap
```

#### Goroutine Analysis
```bash
go tool pprof http://localhost:50055/debug/pprof/goroutine
```

## Benchmarking

### Run Benchmark
```bash
# Run with simulated provider (fast, no API calls)
python HDRP/benchmark.py --queries 10 --output baseline.json

# Run with real provider
python HDRP/benchmark.py --queries 10 --provider google --api-key YOUR_KEY --output optimized.json
```

### Compare Results
```bash
python HDRP/benchmark.py --compare baseline.json optimized.json
```

### NLI ONNX Export and Runtime
```bash
# Export ONNX model (and INT8 optional)
python HDRP/tools/eval/export_nli_onnx.py --output-dir artifacts/nli_onnx --int8

# Use ONNX Runtime backend
export HDRP_NLI_BACKEND=onnxruntime
export HDRP_NLI_ONNX_PATH=artifacts/nli_onnx/model.onnx
export HDRP_NLI_DEVICE=auto
export HDRP_NLI_ONNX_PROVIDERS=CUDAExecutionProvider,CPUExecutionProvider

# Use INT8 model for CPU
export HDRP_NLI_ONNX_PATH=artifacts/nli_onnx/model.int8.onnx
export HDRP_NLI_INT8=1
```

This will show:
- Latency improvements across metrics (mean, median, p95, p99)
- Percentage improvement for each metric
- Whether the 30% improvement target was met

### Example Output
```
BENCHMARK COMPARISON
============================================================
Baseline:  baseline.json
Optimized: optimized.json

Metric     Baseline    Optimized       Change   % Improvement
-----------------------------------------------------------------
mean          15.34s       10.12s    ↓   5.22s           34.0%
median        14.89s        9.87s    ↓   5.02s           33.7%
p95           18.45s       12.34s    ↓   6.11s           33.1%
p99           19.23s       13.01s    ↓   6.22s           32.3%

Overall Mean Latency Improvement: 34.0%
✓ TARGET MET: 30% latency reduction achieved!
```

## Key Performance Improvements

1. **Concurrent Processing**: Both researcher and critic services now process items in parallel
2. **Caching**: Tokenization cache eliminates redundant string processing
3. **Thread Pools**: Reusable thread pools reduce overhead of creating/destroying threads
4. **Profiling**: Built-in profiling infrastructure makes it easy to identify new bottlenecks

## Next Steps

1. Run baseline benchmarks before deploying
2. Monitor production performance with pprof
3. Identify additional optimization opportunities
4. Consider adding:
   - Connection pooling for gRPC clients
   - Async I/O for search provider
   - Result caching for repeated queries
