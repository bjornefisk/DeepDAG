#!/usr/bin/env python3
"""
Unified benchmark runner for DeepDAG/HDRP.

Subcommands:
  - pipeline: pipeline latency benchmark and ReActAgent sanity checks
  - nli: critic-based or direct NLI verification benchmarks
  - scifact: SciFact NLI model evaluation

Examples:
  python benchmark.py pipeline --queries 10 --provider simulated
  python benchmark.py pipeline --compare artifacts/base.json artifacts/opt.json
  python benchmark.py pipeline --question "What is the capital of France?"

  python benchmark.py nli --mode critic --output-report artifacts/nli_benchmark.json
  python benchmark.py nli --mode direct --output-report artifacts/nli_direct.json

  python benchmark.py scifact --test-file artifacts/scifact_nli/test.jsonl \
    --baseline-model cross-encoder/nli-deberta-v3-base \
    --tuned-model artifacts/nli_scifact
"""

import argparse
import json
import statistics
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import sys
from typing import Dict, Iterable, List

from HDRP.services.critic.nli_verifier import NLIVerifier
from HDRP.services.critic.service import CriticService
from HDRP.services.shared.pipeline_runner import PipelineRunner, build_search_provider
from HDRP.services.shared.settings import get_settings
from HDRP.services.shared.claims import AtomicClaim
from HDRP.tools.eval.react_agent import ReActAgent
from HDRP.tools.eval.test_queries import QueryComplexity, get_queries_by_complexity
from HDRP.tools.search import SearchProvider
from HDRP.tools.search.base import SearchError
from HDRP.tools.search.api_key_validator import APIKeyError


# ----------------------------
# Pipeline benchmark utilities
# ----------------------------

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


def run_pipeline_benchmark(
    num_queries: int = 10,
    provider: str = "simulated",
    api_key: str = None,
    output_file: str = None,
) -> Dict:
    """Run pipeline benchmark with specified number of queries."""
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
            # Build search provider once per query
            search_provider = build_search_provider(provider, api_key)
            runner = PipelineRunner(
                search_provider=search_provider,
                verbose=False,
            )
            result = runner.execute(query=query)

            elapsed = time.time() - start_time
            latencies.append(elapsed)

            if result.get("success"):
                successes += 1
                print(f"  OK  Success in {elapsed:.2f}s")
            else:
                failures += 1
                print(f"  FAIL  {result.get('error', 'Unknown error')}")

        except Exception as exc:
            elapsed = time.time() - start_time
            latencies.append(elapsed)
            failures += 1
            print(f"  FAIL  Exception: {exc}")

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
                "p95": sorted(latencies)[min(int(len(latencies) * 0.95), len(latencies) - 1)]
                if len(latencies) > 1
                else latencies[0],
                "p99": sorted(latencies)[min(int(len(latencies) * 0.99), len(latencies) - 1)]
                if len(latencies) > 1
                else latencies[0],
                "stdev": statistics.stdev(latencies) if len(latencies) > 1 else 0,
                "all_latencies": latencies,
            },
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

    print("\n" + "=" * 60)
    print("BENCHMARK RESULTS")
    print("=" * 60)
    print(f"Queries:   {num_queries}")
    print(f"Successes: {successes}")
    print(f"Failures:  {failures}")

    if "latencies" in results:
        lat = results["latencies"]
        print("\nLatency (seconds):")
        print(f"  Min:    {lat['min']:.2f}s")
        print(f"  Max:    {lat['max']:.2f}s")
        print(f"  Mean:   {lat['mean']:.2f}s")
        print(f"  Median: {lat['median']:.2f}s")
        print(f"  P95:    {lat['p95']:.2f}s")
        print(f"  P99:    {lat['p99']:.2f}s")
        print(f"  StdDev: {lat['stdev']:.2f}s")

    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(results, handle, indent=2)
        print(f"\nResults saved to: {output_file}")

    return results


def compare_results(baseline_file: str, optimized_file: str) -> None:
    """Compare two pipeline benchmark results."""
    with open(baseline_file, encoding="utf-8") as handle:
        baseline = json.load(handle)
    with open(optimized_file, encoding="utf-8") as handle:
        optimized = json.load(handle)

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
        direction = "down" if change > 0 else "up"

        print(
            f"{metric:<10} {base_val:>10.2f}s {opt_val:>10.2f}s "
            f"{direction:>4} {abs(change):>8.2f}s {pct_improvement:>13.1f}%"
        )

    mean_improvement = ((baseline_lat["mean"] - optimized_lat["mean"]) / baseline_lat["mean"]) * 100
    print()
    print(f"Overall Mean Latency Improvement: {mean_improvement:.1f}%")
    if mean_improvement >= 30:
        print("TARGET MET: 30% latency reduction achieved!")
    else:
        print(f"Target not met. Need {30 - mean_improvement:.1f}% more improvement.")


def run_react_agent_benchmark(search_provider: str, max_results: int, question: str) -> None:
    """Run a single ReActAgent episode for a sanity check."""
    try:
        provider = build_search_provider(search_provider)
    except (SearchError, APIKeyError) as exc:
        print("\n[ERROR] Failed to initialize search provider:", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        print(
            "\nTip: Use --search-provider simulated for testing without an API key.",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as exc:
        print(f"\n[ERROR] Unexpected error: {exc}", file=sys.stderr)
        sys.exit(1)

    resolved_max = max_results if max_results is not None else provider.DEFAULT_MAX_RESULTS
    agent = ReActAgent(search_provider=provider, max_results=resolved_max)
    result = agent.run(question)
    print(result.final_answer)


# ----------------------------
# NLI benchmark utilities
# ----------------------------

@dataclass
class TestClaim:
    """Test claim with ground truth label for evaluation."""
    claim: AtomicClaim
    ground_truth: str
    category: str


@dataclass
class NliBenchmarkResult:
    """Results for a single benchmark run."""
    method: str
    query_id: str
    query_complexity: str
    total_claims: int
    accepted_claims: int
    rejected_claims: int
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float
    avg_processing_time_ms: float
    cache_hit_rate: float = 0.0
    category_breakdown: Dict[str, Dict[str, int]] = None


def _create_paraphrase_cases() -> List[TestClaim]:
    test_timestamp = datetime.now().isoformat() + "Z"
    cases = []
    paraphrase_pairs = [
        ("The algorithm runs in linear time complexity", "The computational complexity is O(n)"),
        ("Water freezes at zero degrees Celsius", "H2O becomes solid at 0C"),
        ("The company's revenue increased by 25 percent", "Corporate earnings grew by one quarter"),
        ("The function returns a boolean value", "The method outputs true or false"),
        ("The sum of angles in a triangle equals 180 degrees", "Triangle angles total pi radians"),
    ]
    for i, (statement, support) in enumerate(paraphrase_pairs):
        claim = AtomicClaim(
            statement=statement,
            support_text=support,
            source_url=f"https://example.com/paraphrase_{i}",
            confidence=0.9,
            extracted_at=test_timestamp,
            discovered_entities=[],
        )
        cases.append(TestClaim(claim, "ENTAILMENT", "paraphrase"))
    return cases


def _create_contradiction_cases() -> List[TestClaim]:
    test_timestamp = datetime.now().isoformat() + "Z"
    cases = []
    contradiction_pairs = [
        ("Python is a compiled language", "Python is an interpreted language"),
        ("The temperature is increasing", "The temperature is decreasing"),
        ("The system is online and operational", "The system is offline and inaccessible"),
        ("Lightning travels faster than sound", "Sound travels faster than lightning"),
        ("The event happened in the morning", "The event occurred in the evening"),
    ]
    for i, (statement, support) in enumerate(contradiction_pairs):
        claim = AtomicClaim(
            statement=statement,
            support_text=support,
            source_url=f"https://example.com/contradiction_{i}",
            confidence=0.8,
            extracted_at=test_timestamp,
            discovered_entities=[],
        )
        cases.append(TestClaim(claim, "CONTRADICTION", "contradiction"))
    return cases


def _create_partial_overlap_cases() -> List[TestClaim]:
    test_timestamp = datetime.now().isoformat() + "Z"
    cases = []
    partial_overlap_pairs = [
        ("Apple released a new iPhone model", "Apple trees produce fruit in autumn"),
        ("The bank approved the loan application", "The river bank was eroded by flooding"),
        ("Machine learning is quantum computing", "Machine learning uses classical algorithms while quantum computing leverages quantum mechanics"),
        ("Neural networks require GPU acceleration", "Neural networks in the brain consist of neurons"),
        ("The research focuses on climate change mitigation", "The research focuses on climate change prediction"),
    ]
    for i, (statement, support) in enumerate(partial_overlap_pairs):
        claim = AtomicClaim(
            statement=statement,
            support_text=support,
            source_url=f"https://example.com/partial_overlap_{i}",
            confidence=0.7,
            extracted_at=test_timestamp,
            discovered_entities=[],
        )
        cases.append(TestClaim(claim, "NO_ENTAILMENT", "partial_overlap"))
    return cases


def _create_entailment_cases() -> List[TestClaim]:
    test_timestamp = datetime.now().isoformat() + "Z"
    cases = []
    entailment_pairs = [
        ("The vehicle accelerated rapidly", "The car sped up quickly moving from 30 to 60 mph in seconds"),
        ("Dogs are mammals", "Golden Retrievers, Poodles, and German Shepherds are all warm-blooded vertebrates that nurse their young"),
        ("Exercise improves cardiovascular health", "Regular physical activity strengthens the heart muscle and improves blood circulation"),
        ("Photosynthesis produces oxygen", "Plants convert carbon dioxide and water into glucose and O2 using sunlight"),
        ("Einstein developed the theory of relativity", "Albert Einstein published his general relativity paper in 1915, revolutionizing physics"),
    ]
    for i, (statement, support) in enumerate(entailment_pairs):
        claim = AtomicClaim(
            statement=statement,
            support_text=support,
            source_url=f"https://example.com/entailment_{i}",
            confidence=0.95,
            extracted_at=test_timestamp,
            discovered_entities=[],
        )
        cases.append(TestClaim(claim, "ENTAILMENT", "entailment"))
    return cases


def _create_irrelevant_cases() -> List[TestClaim]:
    test_timestamp = datetime.now().isoformat() + "Z"
    cases = []
    irrelevant_pairs = [
        ("Quantum computing uses qubits for parallel computations", "Bananas are rich in potassium and provide energy"),
        ("Machine learning models require training data", "The Great Wall of China is visible from space"),
        ("DNA stores genetic information", "Coffee contains caffeine which acts as a stimulant"),
    ]
    for i, (statement, support) in enumerate(irrelevant_pairs):
        claim = AtomicClaim(
            statement=statement,
            support_text=support,
            source_url=f"https://example.com/irrelevant_{i}",
            confidence=0.5,
            extracted_at=test_timestamp,
            discovered_entities=[],
        )
        cases.append(TestClaim(claim, "NO_ENTAILMENT", "irrelevant"))
    return cases


def _create_adversarial_test_claims() -> List[TestClaim]:
    cases: List[TestClaim] = []
    cases.extend(_create_paraphrase_cases())
    cases.extend(_create_contradiction_cases())
    cases.extend(_create_partial_overlap_cases())
    cases.extend(_create_entailment_cases())
    cases.extend(_create_irrelevant_cases())
    return cases


def _benchmark_critic_method(
    method: str,
    test_query: any,
    test_claims: List[TestClaim],
) -> NliBenchmarkResult:
    use_nli = method == "nli"
    critic = CriticService(use_nli=use_nli, nli_threshold=0.60)

    claims = [tc.claim for tc in test_claims]
    start_time = time.time()
    results = critic.verify(claims, task=test_query.question)
    end_time = time.time()

    processing_time_ms = (end_time - start_time) * 1000
    true_positives = 0
    false_positives = 0
    true_negatives = 0
    false_negatives = 0
    category_breakdown: Dict[str, Dict[str, int]] = {}

    for test_claim, result in zip(test_claims, results):
        should_accept = test_claim.ground_truth == "ENTAILMENT"
        was_accepted = result.is_valid

        if should_accept and was_accepted:
            true_positives += 1
        elif not should_accept and was_accepted:
            false_positives += 1
        elif should_accept and not was_accepted:
            false_negatives += 1
        else:
            true_negatives += 1

        category = test_claim.category
        if category not in category_breakdown:
            category_breakdown[category] = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
        if should_accept and was_accepted:
            category_breakdown[category]["tp"] += 1
        elif not should_accept and was_accepted:
            category_breakdown[category]["fp"] += 1
        elif should_accept and not was_accepted:
            category_breakdown[category]["fn"] += 1
        else:
            category_breakdown[category]["tn"] += 1

    precision = (
        true_positives / (true_positives + false_positives)
        if (true_positives + false_positives) > 0
        else 0.0
    )
    recall = (
        true_positives / (true_positives + false_negatives)
        if (true_positives + false_negatives) > 0
        else 0.0
    )
    f1_score = (
        2 * (precision * recall) / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )

    accepted = sum(1 for r in results if r.is_valid)
    rejected = sum(1 for r in results if not r.is_valid)

    cache_hit_rate = 0.0
    if use_nli and hasattr(critic, "_nli_verifier") and critic._nli_verifier:
        cache_stats = critic._nli_verifier.get_cache_stats()
        cache_hit_rate = cache_stats.get("hit_rate", 0.0)

    return NliBenchmarkResult(
        method=method,
        query_id=test_query.id,
        query_complexity=test_query.complexity.value,
        total_claims=len(test_claims),
        accepted_claims=accepted,
        rejected_claims=rejected,
        true_positives=true_positives,
        false_positives=false_positives,
        true_negatives=true_negatives,
        false_negatives=false_negatives,
        precision=precision,
        recall=recall,
        f1_score=f1_score,
        avg_processing_time_ms=processing_time_ms,
        cache_hit_rate=cache_hit_rate,
        category_breakdown=category_breakdown,
    )


def run_critic_nli_benchmark(output_path: str = None) -> Dict:
    print("=" * 80)
    print("NLI VERIFIER BENCHMARK - ADVERSARIAL TEST SET")
    print("=" * 80)
    print()

    all_results: List[NliBenchmarkResult] = []
    print("Generating adversarial test set...")
    test_claims = _create_adversarial_test_claims()
    print(f"Created {len(test_claims)} adversarial test cases:")

    category_counts: Dict[str, int] = {}
    for tc in test_claims:
        category_counts[tc.category] = category_counts.get(tc.category, 0) + 1
    for category, count in category_counts.items():
        print(f"  - {category}: {count} cases")
    print()

    for complexity in [QueryComplexity.SIMPLE, QueryComplexity.MEDIUM, QueryComplexity.COMPLEX]:
        queries = get_queries_by_complexity(complexity)
        print(f"\n{complexity.value.upper()} QUERIES ({len(queries)} queries)")
        print("-" * 80)

        for query in queries:
            print(f"\nQuery: {query.question}")
            print("  [Heuristic] Running...")
            heuristic_result = _benchmark_critic_method("heuristic", query, test_claims)
            all_results.append(heuristic_result)
            print(
                f"  [Heuristic] Precision: {heuristic_result.precision:.2%}, "
                f"Recall: {heuristic_result.recall:.2%}, "
                f"F1: {heuristic_result.f1_score:.2%}, "
                f"Time: {heuristic_result.avg_processing_time_ms:.1f}ms"
            )

            print("  [NLI]       Running...")
            nli_result = _benchmark_critic_method("nli", query, test_claims)
            all_results.append(nli_result)
            print(
                f"  [NLI]       Precision: {nli_result.precision:.2%}, "
                f"Recall: {nli_result.recall:.2%}, "
                f"F1: {nli_result.f1_score:.2%}, "
                f"Time: {nli_result.avg_processing_time_ms:.1f}ms, "
                f"Cache Hit: {nli_result.cache_hit_rate:.1%}"
            )

            f1_improvement = nli_result.f1_score - heuristic_result.f1_score
            precision_improvement = nli_result.precision - heuristic_result.precision
            recall_improvement = nli_result.recall - heuristic_result.recall
            print(
                f"  [Delta]     F1: {f1_improvement:+.2%}, "
                f"Precision: {precision_improvement:+.2%}, "
                f"Recall: {recall_improvement:+.2%}"
            )

    print("\n" + "=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)

    summary: Dict[str, Dict[str, float]] = {}
    for complexity in [QueryComplexity.SIMPLE, QueryComplexity.MEDIUM, QueryComplexity.COMPLEX]:
        complexity_name = complexity.value
        heuristic_results = [
            r for r in all_results if r.query_complexity == complexity_name and r.method == "heuristic"
        ]
        nli_results = [
            r for r in all_results if r.query_complexity == complexity_name and r.method == "nli"
        ]
        if not heuristic_results or not nli_results:
            continue

        avg_heuristic_precision = sum(r.precision for r in heuristic_results) / len(heuristic_results)
        avg_heuristic_recall = sum(r.recall for r in heuristic_results) / len(heuristic_results)
        avg_heuristic_f1 = sum(r.f1_score for r in heuristic_results) / len(heuristic_results)
        avg_nli_precision = sum(r.precision for r in nli_results) / len(nli_results)
        avg_nli_recall = sum(r.recall for r in nli_results) / len(nli_results)
        avg_nli_f1 = sum(r.f1_score for r in nli_results) / len(nli_results)
        f1_improvement = avg_nli_f1 - avg_heuristic_f1
        precision_improvement = avg_nli_precision - avg_heuristic_precision
        recall_improvement = avg_nli_recall - avg_heuristic_recall
        avg_nli_cache_hit = sum(r.cache_hit_rate for r in nli_results) / len(nli_results)

        summary[complexity_name] = {
            "heuristic_avg_precision": avg_heuristic_precision,
            "heuristic_avg_recall": avg_heuristic_recall,
            "heuristic_avg_f1": avg_heuristic_f1,
            "nli_avg_precision": avg_nli_precision,
            "nli_avg_recall": avg_nli_recall,
            "nli_avg_f1": avg_nli_f1,
            "precision_improvement": precision_improvement,
            "recall_improvement": recall_improvement,
            "f1_improvement": f1_improvement,
            "f1_improvement_pct": f1_improvement / avg_heuristic_f1 if avg_heuristic_f1 > 0 else 0,
            "nli_avg_cache_hit_rate": avg_nli_cache_hit,
        }

        print(f"\n{complexity_name.upper()}:")
        print(
            f"  Heuristic - Precision: {avg_heuristic_precision:.2%}, "
            f"Recall: {avg_heuristic_recall:.2%}, "
            f"F1: {avg_heuristic_f1:.2%}"
        )
        print(
            f"  NLI       - Precision: {avg_nli_precision:.2%}, "
            f"Recall: {avg_nli_recall:.2%}, "
            f"F1: {avg_nli_f1:.2%}"
        )
        print(
            f"  Improvement - F1: {f1_improvement:+.2%} ({f1_improvement/avg_heuristic_f1:+.1%}), "
            f"Precision: {precision_improvement:+.2%}, "
            f"Recall: {recall_improvement:+.2%}"
        )
        print(f"  NLI Cache Hit Rate: {avg_nli_cache_hit:.1%}")

    print("\n" + "=" * 80)
    print("CATEGORY BREAKDOWN - NLI vs Heuristic")
    print("=" * 80)

    category_stats: Dict[str, Dict[str, Dict[str, int]]] = {}
    for result in all_results:
        if result.category_breakdown:
            for category, metrics in result.category_breakdown.items():
                if category not in category_stats:
                    category_stats[category] = {
                        "nli": {"tp": 0, "fp": 0, "tn": 0, "fn": 0},
                        "heuristic": {"tp": 0, "fp": 0, "tn": 0, "fn": 0},
                    }
                method = result.method
                for metric_key, value in metrics.items():
                    category_stats[category][method][metric_key] += value

    for category, methods in category_stats.items():
        print(f"\n{category.upper()}:")
        for method in ["heuristic", "nli"]:
            metrics = methods[method]
            tp, fp, tn, fn = metrics["tp"], metrics["fp"], metrics["tn"], metrics["fn"]
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
            print(f"  [{method.upper():10s}] Precision: {precision:.2%}, Recall: {recall:.2%}, F1: {f1:.2%}")

    complex_f1_improvement = summary.get("complex", {}).get("f1_improvement_pct", 0)
    target_met = complex_f1_improvement > 0.10
    print("\n" + "=" * 80)
    print("TARGET: >10% F1 improvement on complex queries")
    print(f"RESULT: {complex_f1_improvement:+.1%} - {'PASS' if target_met else 'FAIL'}")
    print("=" * 80 + "\n")

    output = {
        "timestamp": datetime.now().isoformat(),
        "test_set_size": len(test_claims),
        "test_set_categories": category_counts,
        "detailed_results": [asdict(r) for r in all_results],
        "summary": summary,
        "category_analysis": category_stats,
        "target_met": target_met,
    }

    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as handle:
            json.dump(output, handle, indent=2)
        print(f"Results saved to: {output_file}")

    return output


@dataclass
class DirectNliTestCase:
    premise: str
    hypothesis: str
    ground_truth: str
    category: str


@dataclass
class DirectNliBenchmarkResult:
    method: str
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float
    avg_processing_time_ms: float
    category_breakdown: Dict[str, Dict[str, int]]
    multi_class_metrics: Dict[str, Dict[str, float]]
    category_accuracy: Dict[str, Dict[str, float]]


def _create_direct_test_cases() -> List[DirectNliTestCase]:
    paraphrase_cases = [
        DirectNliTestCase("The computational complexity is O(n)", "The algorithm runs in linear time", "ENTAILMENT", "paraphrase"),
        DirectNliTestCase("H2O becomes solid at 0C", "Water freezes at zero degrees Celsius", "ENTAILMENT", "paraphrase"),
        DirectNliTestCase("Corporate earnings grew by one quarter", "The company's revenue increased by 25 percent", "ENTAILMENT", "paraphrase"),
        DirectNliTestCase("The method outputs true or false", "The function returns a boolean value", "ENTAILMENT", "paraphrase"),
        DirectNliTestCase("Triangle angles total pi radians", "The sum of angles in a triangle equals 180 degrees", "ENTAILMENT", "paraphrase"),
    ]

    contradiction_cases = [
        DirectNliTestCase("Python is an interpreted language", "Python is a compiled language", "CONTRADICTION", "contradiction"),
        DirectNliTestCase("The temperature is decreasing", "The temperature is increasing", "CONTRADICTION", "contradiction"),
        DirectNliTestCase("The system is offline and inaccessible", "The system is online and operational", "CONTRADICTION", "contradiction"),
        DirectNliTestCase("Sound travels faster than lightning", "Lightning travels faster than sound", "CONTRADICTION", "contradiction"),
        DirectNliTestCase("The event occurred in the evening", "The event happened in the morning", "CONTRADICTION", "contradiction"),
    ]

    partial_overlap_cases = [
        DirectNliTestCase("Apple trees produce fruit in autumn", "Apple released a new iPhone model", "NO_ENTAILMENT", "partial_overlap"),
        DirectNliTestCase("The river bank was eroded by flooding", "The bank approved the loan application", "NO_ENTAILMENT", "partial_overlap"),
        DirectNliTestCase(
            "Machine learning uses classical algorithms while quantum computing leverages quantum mechanics",
            "Machine learning is quantum computing",
            "NO_ENTAILMENT",
            "partial_overlap",
        ),
        DirectNliTestCase("Neural networks in the brain consist of neurons", "Neural networks require GPU acceleration", "NO_ENTAILMENT", "partial_overlap"),
        DirectNliTestCase("The research focuses on climate change prediction", "The research focuses on climate change mitigation", "NO_ENTAILMENT", "partial_overlap"),
    ]

    entailment_cases = [
        DirectNliTestCase("The car sped up quickly moving from 30 to 60 mph in seconds", "The vehicle accelerated rapidly", "ENTAILMENT", "entailment"),
        DirectNliTestCase(
            "Golden Retrievers, Poodles, and German Shepherds are all warm-blooded vertebrates that nurse their young",
            "Dogs are mammals",
            "ENTAILMENT",
            "entailment",
        ),
        DirectNliTestCase(
            "Regular physical activity strengthens the heart muscle and improves blood circulation",
            "Exercise improves cardiovascular health",
            "ENTAILMENT",
            "entailment",
        ),
        DirectNliTestCase(
            "Plants convert carbon dioxide and water into glucose and O2 using sunlight",
            "Photosynthesis produces oxygen",
            "ENTAILMENT",
            "entailment",
        ),
        DirectNliTestCase(
            "Albert Einstein published his general relativity paper in 1915, revolutionizing physics",
            "Einstein developed the theory of relativity",
            "ENTAILMENT",
            "entailment",
        ),
    ]

    irrelevant_cases = [
        DirectNliTestCase("Bananas are rich in potassium and provide energy", "Quantum computing uses qubits for parallel computations", "NO_ENTAILMENT", "irrelevant"),
        DirectNliTestCase("The Great Wall of China is visible from space", "Machine learning models require training data", "NO_ENTAILMENT", "irrelevant"),
        DirectNliTestCase("Coffee contains caffeine which acts as a stimulant", "DNA stores genetic information", "NO_ENTAILMENT", "irrelevant"),
    ]

    return paraphrase_cases + contradiction_cases + partial_overlap_cases + entailment_cases + irrelevant_cases


def _word_overlap_heuristic(premise: str, hypothesis: str, threshold: float = 0.6) -> bool:
    import re

    premise_tokens = set(re.findall(r"\w+", premise.lower()))
    hypothesis_tokens = re.findall(r"\w+", hypothesis.lower())
    stop_words = {"the", "is", "at", "of", "on", "and", "a", "to", "in", "for", "with", "by", "from"}
    hypothesis_filtered = [w for w in hypothesis_tokens if w not in stop_words]

    if not hypothesis_filtered:
        hypothesis_filtered = hypothesis_tokens

    overlap = sum(1 for w in hypothesis_filtered if w in premise_tokens)
    overlap_ratio = overlap / len(hypothesis_filtered) if hypothesis_filtered else 0.0
    return overlap_ratio >= threshold


def _predict_nli_label(
    verifier: NLIVerifier,
    premise: str,
    hypothesis: str,
    entailment_threshold: float,
    contradiction_threshold: float,
) -> str:
    relation = verifier.compute_relation(premise, hypothesis)
    if relation["contradiction"] >= contradiction_threshold:
        return "CONTRADICTION"
    if relation["entailment"] >= entailment_threshold:
        return "ENTAILMENT"
    return "NO_ENTAILMENT"


def _compute_multi_class_metrics(
    labels: List[str],
    confusion: Dict[str, Dict[str, int]],
) -> Dict[str, Dict[str, float]]:
    per_label = {}
    precisions = []
    recalls = []
    f1s = []
    correct = 0
    total = 0

    for true_label in labels:
        row = confusion[true_label]
        total += sum(row.values())
        correct += row.get(true_label, 0)

    for label in labels:
        tp = confusion[label].get(label, 0)
        fp = sum(confusion[true_label].get(label, 0) for true_label in labels if true_label != label)
        fn = sum(confusion[label].get(other_label, 0) for other_label in labels if other_label != label)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        per_label[label] = {"precision": precision, "recall": recall, "f1": f1}
        precisions.append(precision)
        recalls.append(recall)
        f1s.append(f1)

    macro_precision = sum(precisions) / len(precisions) if precisions else 0.0
    macro_recall = sum(recalls) / len(recalls) if recalls else 0.0
    macro_f1 = sum(f1s) / len(f1s) if f1s else 0.0
    accuracy = correct / total if total > 0 else 0.0

    return {
        "macro_precision": macro_precision,
        "macro_recall": macro_recall,
        "macro_f1": macro_f1,
        "accuracy": accuracy,
        "per_label": per_label,
    }


def _benchmark_direct_method(
    method: str,
    test_cases: List[DirectNliTestCase],
    entailment_threshold: float = 0.60,
    contradiction_threshold: float = 0.20,
) -> DirectNliBenchmarkResult:
    if method == "nli":
        verifier = NLIVerifier()

    true_positives = 0
    false_positives = 0
    true_negatives = 0
    false_negatives = 0
    category_breakdown: Dict[str, Dict[str, int]] = {}
    category_accuracy: Dict[str, Dict[str, float]] = {}
    labels = ["ENTAILMENT", "CONTRADICTION", "NO_ENTAILMENT"]
    confusion = {label: {pred: 0 for pred in labels} for label in labels}

    start_time = time.time()
    for test_case in test_cases:
        if method == "nli":
            predicted_label = _predict_nli_label(
                verifier,
                test_case.premise,
                test_case.hypothesis,
                entailment_threshold,
                contradiction_threshold,
            )
            predicted_entailment = predicted_label == "ENTAILMENT"
        elif method == "heuristic":
            predicted_entailment = _word_overlap_heuristic(test_case.premise, test_case.hypothesis)
            predicted_label = "ENTAILMENT" if predicted_entailment else "NO_ENTAILMENT"
        else:
            raise ValueError(f"Unknown method: {method}")

        should_accept = test_case.ground_truth == "ENTAILMENT"
        true_label = test_case.ground_truth

        if should_accept and predicted_entailment:
            true_positives += 1
        elif not should_accept and predicted_entailment:
            false_positives += 1
        elif should_accept and not predicted_entailment:
            false_negatives += 1
        else:
            true_negatives += 1

        category = test_case.category
        if category not in category_breakdown:
            category_breakdown[category] = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}

        if should_accept and predicted_entailment:
            category_breakdown[category]["tp"] += 1
        elif not should_accept and predicted_entailment:
            category_breakdown[category]["fp"] += 1
        elif should_accept and not predicted_entailment:
            category_breakdown[category]["fn"] += 1
        else:
            category_breakdown[category]["tn"] += 1

        if true_label not in confusion:
            confusion[true_label] = {pred: 0 for pred in labels}
        if predicted_label not in confusion[true_label]:
            confusion[true_label][predicted_label] = 0
        confusion[true_label][predicted_label] += 1

        if category not in category_accuracy:
            category_accuracy[category] = {
                "correct": 0,
                "total": 0,
                "accuracy": 0.0,
                "predictions": {label: 0 for label in labels},
            }
        category_accuracy[category]["total"] += 1
        category_accuracy[category]["predictions"][predicted_label] += 1
        if predicted_label == true_label:
            category_accuracy[category]["correct"] += 1

    end_time = time.time()
    processing_time_ms = (end_time - start_time) * 1000

    precision = (
        true_positives / (true_positives + false_positives)
        if (true_positives + false_positives) > 0
        else 0.0
    )
    recall = (
        true_positives / (true_positives + false_negatives)
        if (true_positives + false_negatives) > 0
        else 0.0
    )
    f1_score = (
        2 * (precision * recall) / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )

    for category, stats in category_accuracy.items():
        if stats["total"] > 0:
            stats["accuracy"] = stats["correct"] / stats["total"]

    multi_class_metrics = _compute_multi_class_metrics(labels, confusion)

    return DirectNliBenchmarkResult(
        method=method,
        true_positives=true_positives,
        false_positives=false_positives,
        true_negatives=true_negatives,
        false_negatives=false_negatives,
        precision=precision,
        recall=recall,
        f1_score=f1_score,
        avg_processing_time_ms=processing_time_ms,
        category_breakdown=category_breakdown,
        multi_class_metrics=multi_class_metrics,
        category_accuracy=category_accuracy,
    )


def run_direct_nli_benchmark(
    output_path: str = None,
    entailment_threshold: float = None,
    contradiction_threshold: float = None,
) -> Dict:
    print("=" * 80)
    print("DIRECT NLI BENCHMARK - Testing NLI Verifier in Isolation")
    print("=" * 80)
    print()

    print("Generating adversarial test cases...")
    test_cases = _create_direct_test_cases()
    print(f"Created {len(test_cases)} test cases:")

    category_counts: Dict[str, int] = {}
    for tc in test_cases:
        category_counts[tc.category] = category_counts.get(tc.category, 0) + 1
    for category, count in category_counts.items():
        print(f"  - {category}: {count} cases")
    print()

    print("Benchmarking word overlap heuristic...")
    settings = get_settings()
    nli_settings = settings.nli
    entailment_threshold = (
        nli_settings.entailment_threshold if entailment_threshold is None else entailment_threshold
    )
    contradiction_threshold = (
        nli_settings.contradiction_threshold
        if contradiction_threshold is None
        else contradiction_threshold
    )

    heuristic_result = _benchmark_direct_method(
        "heuristic",
        test_cases,
        entailment_threshold=entailment_threshold,
        contradiction_threshold=contradiction_threshold,
    )
    print(
        f"  Precision: {heuristic_result.precision:.2%}, "
        f"Recall: {heuristic_result.recall:.2%}, "
        f"F1: {heuristic_result.f1_score:.2%}, "
        f"Time: {heuristic_result.avg_processing_time_ms:.1f}ms"
    )
    print()

    print("Benchmarking NLI verifier...")
    nli_result = _benchmark_direct_method(
        "nli",
        test_cases,
        entailment_threshold=entailment_threshold,
        contradiction_threshold=contradiction_threshold,
    )
    print(
        f"  Precision: {nli_result.precision:.2%}, "
        f"Recall: {nli_result.recall:.2%}, "
        f"F1: {nli_result.f1_score:.2%}, "
        f"Time: {nli_result.avg_processing_time_ms:.1f}ms"
    )
    print()
    print("Multi-class (3-way) metrics:")
    print(
        f"  Accuracy: {nli_result.multi_class_metrics['accuracy']:.2%}, "
        f"Macro Precision: {nli_result.multi_class_metrics['macro_precision']:.2%}, "
        f"Macro Recall: {nli_result.multi_class_metrics['macro_recall']:.2%}, "
        f"Macro F1: {nli_result.multi_class_metrics['macro_f1']:.2%}"
    )
    for label, metrics in nli_result.multi_class_metrics["per_label"].items():
        print(
            f"  {label:14s} Precision: {metrics['precision']:.2%}, "
            f"Recall: {metrics['recall']:.2%}, "
            f"F1: {metrics['f1']:.2%}"
        )
    print()

    print("=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)

    f1_improvement = nli_result.f1_score - heuristic_result.f1_score
    precision_improvement = nli_result.precision - heuristic_result.precision
    recall_improvement = nli_result.recall - heuristic_result.recall
    print("\nOverall Performance:")
    print(
        f"  Heuristic - Precision: {heuristic_result.precision:.2%}, "
        f"Recall: {heuristic_result.recall:.2%}, "
        f"F1: {heuristic_result.f1_score:.2%}"
    )
    print(
        f"  NLI       - Precision: {nli_result.precision:.2%}, "
        f"Recall: {nli_result.recall:.2%}, "
        f"F1: {nli_result.f1_score:.2%}"
    )
    print(
        f"  Improvement - F1: {f1_improvement:+.2%}, "
        f"Precision: {precision_improvement:+.2%}, "
        f"Recall: {recall_improvement:+.2%}"
    )

    print("\nCategory Performance:")
    all_categories = set()
    for tc in test_cases:
        all_categories.add(tc.category)
    for category in sorted(all_categories):
        print(f"\n  {category.upper()}:")
        for method, result in [("Heuristic", heuristic_result), ("NLI", nli_result)]:
            metrics = result.category_breakdown.get(category, {"tp": 0, "fp": 0, "tn": 0, "fn": 0})
            tp, fp, tn, fn = metrics["tp"], metrics["fp"], metrics["tn"], metrics["fn"]
            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * (prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
            print(
                f"    [{method:10s}] Binary Entailment - "
                f"Precision: {prec:.2%}, Recall: {rec:.2%}, F1: {f1:.2%}"
            )

            accuracy = result.category_accuracy.get(category, {}).get("accuracy", 0.0)
            prediction_counts = result.category_accuracy.get(category, {}).get("predictions", {})
            preds = ", ".join(
                f"{label}:{prediction_counts.get(label, 0)}"
                for label in ["ENTAILMENT", "CONTRADICTION", "NO_ENTAILMENT"]
            )
            print(f"    [{method:10s}] 3-way Accuracy: {accuracy:.2%} (Pred: {preds})")

    f1_improvement_pct = (
        (f1_improvement / heuristic_result.f1_score * 100)
        if heuristic_result.f1_score > 0
        else 0
    )
    target_met = f1_improvement > 0.10
    print("\n" + "=" * 80)
    print("TARGET: >10% absolute F1 improvement")
    print(f"RESULT: {f1_improvement:+.2%} - {'PASS' if target_met else 'FAIL'}")
    print("=" * 80 + "\n")

    output = {
        "timestamp": datetime.now().isoformat(),
        "test_cases_count": len(test_cases),
        "category_counts": category_counts,
        "heuristic_results": asdict(heuristic_result),
        "nli_results": asdict(nli_result),
        "improvements": {
            "f1": f1_improvement,
            "precision": precision_improvement,
            "recall": recall_improvement,
        },
        "thresholds": {
            "entailment": entailment_threshold,
            "contradiction": contradiction_threshold,
        },
        "target_met": target_met,
    }

    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as handle:
            json.dump(output, handle, indent=2)
        print(f"Results saved to: {output_file}")

    return output


# ----------------------------
# SciFact NLI benchmark
# ----------------------------

LABELS = ["CONTRADICTION", "NO_ENTAILMENT", "ENTAILMENT"]


def _read_jsonl(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def _score_to_label(scores: Dict[str, float]) -> str:
    mapping = {
        "entailment": "ENTAILMENT",
        "contradiction": "CONTRADICTION",
        "neutral": "NO_ENTAILMENT",
    }
    best = max(scores.items(), key=lambda item: item[1])[0]
    return mapping.get(best, "NO_ENTAILMENT")


def _evaluate_model(model_name: str, rows: List[dict]) -> Dict[str, object]:
    verifier = NLIVerifier(model_name=model_name)
    confusion = defaultdict(Counter)

    for row in rows:
        gold = row.get("label")
        if gold not in LABELS:
            continue
        relation = verifier.compute_relation(
            premise=row.get("premise", ""),
            hypothesis=row.get("hypothesis", ""),
        )
        pred = _score_to_label(relation)
        confusion[gold][pred] += 1

    metrics = {}
    for label in LABELS:
        tp = confusion[label][label]
        fp = sum(confusion[other][label] for other in LABELS if other != label)
        fn = sum(confusion[label][other] for other in LABELS if other != label)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        metrics[label] = {"precision": precision, "recall": recall, "f1": f1}

    macro_f1 = sum(metrics[label]["f1"] for label in LABELS) / len(LABELS)
    accuracy = sum(confusion[label][label] for label in LABELS) / max(
        1, sum(sum(confusion[label].values()) for label in LABELS)
    )

    return {
        "model_name": model_name,
        "accuracy": accuracy,
        "macro_f1": macro_f1,
        "per_label": metrics,
        "confusion": {k: dict(v) for k, v in confusion.items()},
    }


def run_scifact_benchmark(
    test_file: str,
    baseline_model: str,
    tuned_model: str,
    output_report: str,
) -> Dict[str, object]:
    rows = list(_read_jsonl(Path(test_file)))
    if not rows:
        raise ValueError("No test rows found.")

    results = []
    if baseline_model:
        results.append(_evaluate_model(baseline_model, rows))
    if tuned_model:
        results.append(_evaluate_model(tuned_model, rows))

    report = {"results": results}
    if output_report:
        Path(output_report).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return report


# ----------------------------
# CLI
# ----------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unified HDRP benchmark runner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    pipeline = subparsers.add_parser(
        "pipeline",
        help="Pipeline benchmarks and ReActAgent sanity checks",
    )
    pipeline.add_argument("--queries", "-n", type=int, default=10, help="Number of queries to run")
    pipeline.add_argument("--provider", "-p", default="simulated", help="Search provider to use")
    pipeline.add_argument("--api-key", "-k", help="API key for search provider")
    pipeline.add_argument("--output", "-o", help="Output file for results (JSON)")
    pipeline.add_argument(
        "--compare",
        "-c",
        nargs=2,
        metavar=("BASELINE", "OPTIMIZED"),
        help="Compare two result files",
    )
    pipeline.add_argument(
        "--question",
        help="If set, run a single ReActAgent episode instead of the latency benchmark",
    )
    pipeline.add_argument(
        "--search-provider",
        choices=["simulated", "tavily"],
        default=None,
        help="Search provider for ReActAgent (falls back to env vars or simulated)",
    )
    pipeline.add_argument(
        "--max-results",
        type=int,
        default=None,
        help="Max search results for ReActAgent (defaults to provider default)",
    )

    nli = subparsers.add_parser("nli", help="NLI verification benchmarks")
    nli.add_argument(
        "--mode",
        choices=["critic", "direct"],
        default="critic",
        help="Benchmark mode: critic (pipeline) or direct (verifier only)",
    )
    nli.add_argument(
        "--output-report",
        type=str,
        default=None,
        help="Path to save benchmark results JSON",
    )
    nli.add_argument("--entailment-threshold", type=float, default=None)
    nli.add_argument("--contradiction-threshold", type=float, default=None)

    scifact = subparsers.add_parser("scifact", help="SciFact NLI benchmark")
    scifact.add_argument("--test-file", required=True, help="Path to SciFact test.jsonl")
    scifact.add_argument("--baseline-model", help="Baseline model name or path")
    scifact.add_argument("--tuned-model", help="Fine-tuned model name or path")
    scifact.add_argument("--output-report", help="Write report JSON to this file")

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "pipeline":
        if args.compare and args.question:
            parser.error("--compare cannot be used with --question")
        if args.question:
            run_react_agent_benchmark(args.search_provider, args.max_results, args.question)
        elif args.compare:
            compare_results(args.compare[0], args.compare[1])
        else:
            run_pipeline_benchmark(
                num_queries=args.queries,
                provider=args.provider,
                api_key=args.api_key,
                output_file=args.output,
            )
        return

    if args.command == "nli":
        if args.mode == "critic":
            if args.entailment_threshold is not None or args.contradiction_threshold is not None:
                parser.error("Threshold flags are only valid with --mode direct")
            run_critic_nli_benchmark(output_path=args.output_report)
        else:
            run_direct_nli_benchmark(
                output_path=args.output_report,
                entailment_threshold=args.entailment_threshold,
                contradiction_threshold=args.contradiction_threshold,
            )
        return

    if args.command == "scifact":
        run_scifact_benchmark(
            test_file=args.test_file,
            baseline_model=args.baseline_model,
            tuned_model=args.tuned_model,
            output_report=args.output_report,
        )
        return

    parser.error("Unknown command")


if __name__ == "__main__":
    main()
