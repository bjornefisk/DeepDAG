#!/usr/bin/env python3
"""
Benchmark NLI Verifier vs Heuristic Word Overlap

Compares the performance of NLI-based verification against the original
heuristic word overlap method on test queries of varying complexity.

Metrics:
- Precision: Of accepted claims, how many are truly valid?
- Recall: Of truly valid claims, how many are accepted?
- F1 Score: Harmonic mean of precision and recall

Usage:
    python HDRP/tools/eval/benchmark_nli.py --output-report artifacts/nli_benchmark.json
"""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass, asdict

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from HDRP.services.critic.service import CriticService
from HDRP.services.shared.claims import AtomicClaim
from HDRP.tools.eval.test_queries import ALL_QUERIES, QueryComplexity, get_queries_by_complexity


@dataclass
class BenchmarkResult:
    """Results for a single benchmark run."""
    method: str  # "nli" or "heuristic"
    query_id: str
    query_complexity: str
    total_claims: int
    accepted_claims: int
    rejected_claims: int
    avg_processing_time_ms: float
    precision_estimate: float
    cache_hit_rate: float = 0.0


def create_test_claims(query: str, num_claims: int = 20) -> List[AtomicClaim]:
    """Generate synthetic test claims for benchmarking.
    
    Creates a mix of:
    - Valid, relevant claims (should be accepted)
    - Valid but irrelevant claims (should be rejected)
    - Invalid claims with poor support (should be rejected)
    """
    test_timestamp = datetime.now().isoformat() + "Z"
    claims = []
    
    # Extract topic from query for creating relevant/irrelevant claims
    topic_words = [w for w in query.lower().split() if len(w) > 3][:3]
    topic = " ".join(topic_words) if topic_words else "technology"
    
    # 40% valid + relevant claims
    for i in range(int(num_claims * 0.4)):
        statement = f"{topic.title()} involves advanced computational techniques and systems."
        claims.append(AtomicClaim(
            statement=statement,
            support_text=statement,  # Perfect match
            source_url=f"https://example.com/valid_{i}",
            confidence=0.9,
            extracted_at=test_timestamp,
            discovered_entities=[topic.title()]
        ))
    
    # 30% valid but less relevant claims
    for i in range(int(num_claims * 0.3)):
        statement = f"Research in {topic} has shown significant progress in recent years."
        support_text = f"Studies indicate that {topic} research has advanced considerably."
        claims.append(AtomicClaim(
            statement=statement,
            support_text=support_text,  # Paraphrased
            source_url=f"https://example.com/paraphrase_{i}",
            confidence=0.8,
            extracted_at=test_timestamp,
            discovered_entities=[topic.title()]
        ))
    
    # 20% irrelevant claims (wrong topic)
    for i in range(int(num_claims * 0.2)):
        statement = "Bananas are rich in potassium and provide energy."
        claims.append(AtomicClaim(
            statement=statement,
            support_text=statement,
            source_url=f"https://example.com/irrelevant_{i}",
            confidence=0.7,
            extracted_at=test_timestamp,
            discovered_entities=["Bananas"]
        ))
    
    # 10% invalid claims (poor support)
    for i in range(int(num_claims * 0.1)):
        statement = f"{topic.title()} enables breakthrough discoveries in all scientific fields."
        support_text = f"{topic.title()} is used in some research."  # Weak support
        claims.append(AtomicClaim(
            statement=statement,
            support_text=support_text,
            source_url=f"https://example.com/weak_{i}",
            confidence=0.6,
            extracted_at=test_timestamp,
            discovered_entities=[topic.title()]
        ))
    
    return claims


def benchmark_method(
    method: str,
    test_query: any,
    claims: List[AtomicClaim]
) -> BenchmarkResult:
    """Benchmark a single verification method on a query.
    
    Args:
        method: "nli" or "heuristic"
        test_query: Query object from test_queries
        claims: List of claims to verify
        
    Returns:
        BenchmarkResult with performance metrics
    """
    use_nli = (method == "nli")
    critic = CriticService(use_nli=use_nli, nli_threshold=0.65)
    
    start_time = time.time()
    results = critic.verify(claims, task=test_query.question)
    end_time = time.time()
    
    processing_time_ms = (end_time - start_time) * 1000
    
    accepted = sum(1 for r in results if r.is_valid)
    rejected = sum(1 for r in results if not r.is_valid)
    
    # Precision estimate: for synthetic data, we know ground truth
    # Valid claims: first 70% (40% perfect + 30% paraphrased)
    # Invalid claims: last 30% (20% irrelevant + 10% weak)
    total_valid = int(len(claims) * 0.7)
    
    # Count how many accepted claims are actually valid
    true_positives = 0
    for i, result in enumerate(results):
        if result.is_valid and i < total_valid:
            true_positives += 1
    
    precision = true_positives / accepted if accepted > 0 else 0.0
    
    # Get cache stats if using NLI
    cache_hit_rate = 0.0
    if use_nli and hasattr(critic, '_nli_verifier') and critic._nli_verifier:
        cache_stats = critic._nli_verifier.get_cache_stats()
        cache_hit_rate = cache_stats.get('hit_rate', 0.0)
    
    return BenchmarkResult(
        method=method,
        query_id=test_query.id,
        query_complexity=test_query.complexity.value,
        total_claims=len(claims),
        accepted_claims=accepted,
        rejected_claims=rejected,
        avg_processing_time_ms=processing_time_ms,
        precision_estimate=precision,
        cache_hit_rate=cache_hit_rate
    )


def run_benchmark(output_path: str = None) -> Dict:
    """Run full benchmark comparing NLI vs heuristic.
    
    Returns:
        Dictionary with benchmark results and summary statistics
    """
    print("=" * 80)
    print("NLI VERIFIER BENCHMARK")
    print("=" * 80)
    print()
    
    all_results = []
    
    for complexity in [QueryComplexity.SIMPLE, QueryComplexity.MEDIUM, QueryComplexity.COMPLEX]:
        queries = get_queries_by_complexity(complexity)
        
        print(f"\n{complexity.value.upper()} QUERIES ({len(queries)} queries)")
        print("-" * 80)
        
        for query in queries:
            print(f"\nQuery: {query.question}")
            
            # Generate test claims
            claims = create_test_claims(query.question, num_claims=20)
            
            # Benchmark heuristic method
            print(f"  [Heuristic] Running...")
            heuristic_result = benchmark_method("heuristic", query, claims)
            all_results.append(heuristic_result)
            print(f"  [Heuristic] Accepted: {heuristic_result.accepted_claims}/{heuristic_result.total_claims}, "
                  f"Precision: {heuristic_result.precision_estimate:.2%}, "
                  f"Time: {heuristic_result.avg_processing_time_ms:.1f}ms")
            
            # Benchmark NLI method
            print(f"  [NLI]       Running...")
            nli_result = benchmark_method("nli", query, claims)
            all_results.append(nli_result)
            print(f"  [NLI]       Accepted: {nli_result.accepted_claims}/{nli_result.total_claims}, "
                  f"Precision: {nli_result.precision_estimate:.2%}, "
                  f"Time: {nli_result.avg_processing_time_ms:.1f}ms, "
                  f"Cache Hit: {nli_result.cache_hit_rate:.1%}")
            
            # Compute improvement
            precision_improvement = nli_result.precision_estimate - heuristic_result.precision_estimate
            print(f"  [Δ]         Precision Δ: {precision_improvement:+.2%}")
    
    # Compute aggregate statistics
    print("\n" + "=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)
    
    summary = {}
    for complexity in [QueryComplexity.SIMPLE, QueryComplexity.MEDIUM, QueryComplexity.COMPLEX]:
        complexity_name = complexity.value
        
        heuristic_results = [r for r in all_results 
                           if r.query_complexity == complexity_name and r.method == "heuristic"]
        nli_results = [r for r in all_results 
                      if r.query_complexity == complexity_name and r.method == "nli"]
        
        if not heuristic_results or not nli_results:
            continue
        
        avg_heuristic_precision = sum(r.precision_estimate for r in heuristic_results) / len(heuristic_results)
        avg_nli_precision = sum(r.precision_estimate for r in nli_results) / len(nli_results)
        precision_improvement = avg_nli_precision - avg_heuristic_precision
        
        avg_nli_cache_hit = sum(r.cache_hit_rate for r in nli_results) / len(nli_results)
        
        summary[complexity_name] = {
            "heuristic_avg_precision": avg_heuristic_precision,
            "nli_avg_precision": avg_nli_precision,
            "precision_improvement": precision_improvement,
            "precision_improvement_pct": precision_improvement / avg_heuristic_precision if avg_heuristic_precision > 0 else 0,
            "nli_avg_cache_hit_rate": avg_nli_cache_hit
        }
        
        print(f"\n{complexity_name.upper()}:")
        print(f"  Heuristic Avg Precision: {avg_heuristic_precision:.2%}")
        print(f"  NLI Avg Precision:       {avg_nli_precision:.2%}")
        print(f"  Improvement:             {precision_improvement:+.2%} ({precision_improvement/avg_heuristic_precision:+.1%})")
        print(f"  NLI Cache Hit Rate:      {avg_nli_cache_hit:.1%}")
    
    # Check if we met the target
    complex_improvement = summary.get("complex", {}).get("precision_improvement_pct", 0)
    target_met = complex_improvement > 0.10
    
    print(f"\n{'='*80}")
    print(f"TARGET: >10% precision improvement on complex queries")
    print(f"RESULT: {complex_improvement:+.1%} - {'✓ PASS' if target_met else '✗ FAIL'}")
    print(f"{'='*80}\n")
    
    # Prepare output
    output = {
        "timestamp": datetime.now().isoformat(),
        "detailed_results": [asdict(r) for r in all_results],
        "summary": summary,
        "target_met": target_met
    }
    
    # Save to file if requested
    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2)
        print(f"Results saved to: {output_file}")
    
    return output


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Benchmark NLI verifier vs heuristic")
    parser.add_argument(
        "--output-report",
        type=str,
        default=None,
        help="Path to save benchmark results JSON"
    )
    
    args = parser.parse_args()
    
    run_benchmark(output_path=args.output_report)


if __name__ == "__main__":
    main()
