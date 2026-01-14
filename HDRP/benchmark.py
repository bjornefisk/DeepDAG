#!/usr/bin/env python3
"""Benchmark script for testing DeepDAG performance.

Runs multiple queries and measures latency metrics.
"""

import argparse
import json
import time
import statistics
from typing import List, Dict
from pathlib import Path
from HDRP.orchestrated_runner import run_orchestrated_programmatic


# Test queries of varying complexity
BENCHMARK_QUERIES = [
    "What is the capital of France?",
    "How does photosynthesis work?",
    "Explain quantum entanglement",
    "What are the main causes of climate change?",
    "How do neural networks learn?",
    "What is the history of the internet?",
    "Explain the theory of relativity",
    "What are the benefits of renewable energy?",
    "How does the human immune system work?",
    "What is cryptocurrency and how does it work?",
]


def run_benchmark(
    num_queries: int = 10,
    provider: str = "simulated",
    api_key: str = None,
    output_file: str = None,
) -> Dict:
    """Run benchmark with specified number of queries.
    
    Args:
        num_queries: Number of queries to run
        provider: Search provider to use
        api_key: Optional API key
        output_file: Optional file to save results
        
    Returns:
        Dictionary with benchmark results
    """
    print(f"Running benchmark with {num_queries} queries...")
    print(f"Provider: {provider}")
    print("-" * 60)
    
    queries = BENCHMARK_QUERIES[:num_queries]
    latencies = []
    successes = 0
    failures = 0
    
    for i, query in enumerate(queries, 1):
        print(f"\n[{i}/{num_queries}] Query: {query}")
        
        start_time = time.time()
        
        try:
            result = run_orchestrated_programmatic(
                query=query,
                provider=provider,
                api_key=api_key,
                verbose=False,
            )
            
            elapsed = time.time() - start_time
            latencies.append(elapsed)
            
            if result.get("success"):
                successes += 1
                print(f"  ✓ Success in {elapsed:.2f}s")
            else:
                failures += 1
                print(f"  ✗ Failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            elapsed = time.time() - start_time
            latencies.append(elapsed)
            failures += 1
            print(f"  ✗ Exception: {e}")
    
    # Calculate statistics
    if latencies:
        results = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "num_queries": num_queries,
            "provider": provider,
            "successes": successes,
            "failures": failures,
            "latencies": {
                "min": min(latencies),
                "max": max(latencies),
                "mean": statistics.mean(latencies),
                "median": statistics.median(latencies),
                "p95": sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) > 1 else latencies[0],
                "p99": sorted(latencies)[int(len(latencies) * 0.99)] if len(latencies) > 1 else latencies[0],
                "stdev": statistics.stdev(latencies) if len(latencies) > 1 else 0,
                "all_latencies": latencies,
            }
        }
    else:
        results = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "num_queries": num_queries,
            "provider": provider,
            "successes": 0,
            "failures": num_queries,
            "error": "No successful queries",
        }
    
    # Print summary
    print("\n" + "=" * 60)
    print("BENCHMARK RESULTS")
    print("=" * 60)
    print(f"Queries:   {num_queries}")
    print(f"Successes: {successes}")
    print(f"Failures:  {failures}")
    
    if "latencies" in results:
        lat = results["latencies"]
        print(f"\nLatency (seconds):")
        print(f"  Min:    {lat['min']:.2f}s")
        print(f"  Max:    {lat['max']:.2f}s")
        print(f"  Mean:   {lat['mean']:.2f}s")
        print(f"  Median: {lat['median']:.2f}s")
        print(f"  P95:    {lat['p95']:.2f}s")
        print(f"  P99:    {lat['p99']:.2f}s")
        print(f"  StdDev: {lat['stdev']:.2f}s")
    
    # Save results
    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\nResults saved to: {output_file}")
    
    return results


def compare_results(baseline_file: str, optimized_file: str):
    """Compare two benchmark results.
    
    Args:
        baseline_file: Path to baseline results
        optimized_file: Path to optimized results
    """
    with open(baseline_file) as f:
        baseline = json.load(f)
    
    with open(optimized_file) as f:
        optimized = json.load(f)
    
    print("=" * 60)
    print("BENCHMARK COMPARISON")
    print("=" * 60)
    print(f"Baseline:  {baseline_file}")
    print(f"Optimized: {optimized_file}")
    print()
    
    if "latencies" not in baseline or "latencies" not in optimized:
        print("Error: Missing latency data in one or both files")
        return
    
    baseline_lat = baseline["latencies"]
    optimized_lat = optimized["latencies"]
    
    metrics = ["mean", "median", "p95", "p99"]
    
    print(f"{'Metric':<10} {'Baseline':>12} {'Optimized':>12} {'Change':>12} {'% Improvement':>15}")
    print("-" * 65)
    
    for metric in metrics:
        base_val = baseline_lat[metric]
        opt_val = optimized_lat[metric]
        change = base_val - opt_val
        pct_improvement = (change / base_val) * 100 if base_val > 0 else 0
        
        sign = "↓" if change > 0 else "↑"
        
        print(f"{metric:<10} {base_val:>10.2f}s {opt_val:>10.2f}s {sign} {abs(change):>8.2f}s {pct_improvement:>13.1f}%")
    
    # Overall assessment
    mean_improvement = ((baseline_lat["mean"] - optimized_lat["mean"]) / baseline_lat["mean"]) * 100
    
    print()
    print(f"Overall Mean Latency Improvement: {mean_improvement:.1f}%")
    
    if mean_improvement >= 30:
        print("✓ TARGET MET: 30% latency reduction achieved!")
    else:
        print(f"✗ Target not met. Need {30 - mean_improvement:.1f}% more improvement.")


def main():
    parser = argparse.ArgumentParser(description="Benchmark DeepDAG performance")
    parser.add_argument(
        "--queries",
        "-n",
        type=int,
        default=10,
        help="Number of queries to run (default: 10)"
    )
    parser.add_argument(
        "--provider",
        "-p",
        default="simulated",
        help="Search provider to use (default: simulated)"
    )
    parser.add_argument(
        "--api-key",
        "-k",
        help="API key for search provider"
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output file for results (JSON)"
    )
    parser.add_argument(
        "--compare",
        "-c",
        nargs=2,
        metavar=("BASELINE", "OPTIMIZED"),
        help="Compare two result files"
    )
    
    args = parser.parse_args()
    
    if args.compare:
        compare_results(args.compare[0], args.compare[1])
    else:
        run_benchmark(
            num_queries=args.queries,
            provider=args.provider,
            api_key=args.api_key,
            output_file=args.output,
        )


if __name__ == "__main__":
    main()
