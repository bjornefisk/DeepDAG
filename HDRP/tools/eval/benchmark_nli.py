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
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from HDRP.services.critic.service import CriticService
from HDRP.services.shared.claims import AtomicClaim
from HDRP.tools.eval.test_queries import ALL_QUERIES, QueryComplexity, get_queries_by_complexity


@dataclass
class TestClaim:
    """Test claim with ground truth label for evaluation."""
    claim: AtomicClaim
    ground_truth: str  # "ENTAILMENT", "CONTRADICTION", or "NO_ENTAILMENT"
    category: str  # Test case category


@dataclass
class BenchmarkResult:
    """Results for a single benchmark run."""
    method: str  # "nli" or "heuristic"
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


def create_paraphrase_cases() -> List[TestClaim]:
    """Create semantic paraphrases with minimal lexical overlap.
    
    These test NLI's ability to recognize semantic equivalence
    without relying on word matching.
    """
    test_timestamp = datetime.now().isoformat() + "Z"
    cases = []
    
    paraphrase_pairs = [
        # Technical domain
        ("The algorithm runs in linear time complexity", 
         "The computational complexity is O(n)"),
        
        # Scientific domain
        ("Water freezes at zero degrees Celsius", 
         "H2O becomes solid at 0°C"),
        
        # Business domain
        ("The company's revenue increased by 25 percent", 
         "Corporate earnings grew by one quarter"),
        
        # Computer science
        ("The function returns a boolean value", 
         "The method outputs true or false"),
        
        # Mathematics
        ("The sum of angles in a triangle equals 180 degrees",
         "Triangle angles total π radians"),
    ]
    
    for i, (statement, support) in enumerate(paraphrase_pairs):
        claim = AtomicClaim(
            statement=statement,
            support_text=support,
            source_url=f"https://example.com/paraphrase_{i}",
            confidence=0.9,
            extracted_at=test_timestamp,
            discovered_entities=[]
        )
        cases.append(TestClaim(claim, "ENTAILMENT", "paraphrase"))
    
    return cases


def create_contradiction_cases() -> List[TestClaim]:
    """Create contradictions and negations.
    
    These test NLI's ability to detect semantic opposition,
    even when there's high word overlap.
    """
    test_timestamp = datetime.now().isoformat() + "Z"
    cases = []
    
    contradiction_pairs = [
        # Direct negation
        ("Python is a compiled language",
         "Python is an interpreted language"),
        
        # Opposite values
        ("The temperature is increasing",
         "The temperature is decreasing"),
        
        # Mutually exclusive
        ("The system is online and operational",
         "The system is offline and inaccessible"),
        
        # Contradictory properties
        ("Lightning travels faster than sound",
         "Sound travels faster than lightning"),
        
        # Temporal contradiction
        ("The event happened in the morning",
         "The event occurred in the evening"),
    ]
    
    for i, (statement, support) in enumerate(contradiction_pairs):
        claim = AtomicClaim(
            statement=statement,
            support_text=support,
            source_url=f"https://example.com/contradiction_{i}",
            confidence=0.8,
            extracted_at=test_timestamp,
            discovered_entities=[]
        )
        cases.append(TestClaim(claim, "CONTRADICTION", "contradiction"))
    
    return cases


def create_partial_overlap_cases() -> List[TestClaim]:
    """Create cases with high word overlap but different meanings.
    
    These expose weaknesses in word-overlap heuristics.
    """
    test_timestamp = datetime.now().isoformat() + "Z"
    cases = []
    
    partial_overlap_pairs = [
        # Homonym confusion
        ("Apple released a new iPhone model",
         "Apple trees produce fruit in autumn"),
        
        # Different context, same words
        ("The bank approved the loan application",
         "The river bank was eroded by flooding"),
        
        # Keyword stuffing
        ("Machine learning is quantum computing",
         "Machine learning uses classical algorithms while quantum computing leverages quantum mechanics"),
        
        # Topic drift
        ("Neural networks require GPU acceleration",
         "Neural networks in the brain consist of neurons"),
        
        # Similar words, different claims
        ("The research focuses on climate change mitigation",
         "The research focuses on climate change prediction"),
    ]
    
    for i, (statement, support) in enumerate(partial_overlap_pairs):
        claim = AtomicClaim(
            statement=statement,
            support_text=support,
            source_url=f"https://example.com/partial_overlap_{i}",
            confidence=0.7,
            extracted_at=test_timestamp,
            discovered_entities=[]
        )
        cases.append(TestClaim(claim, "NO_ENTAILMENT", "partial_overlap"))
    
    return cases


def create_entailment_cases() -> List[TestClaim]:
    """Create true entailment cases with varied expression.
    
    Support provides strong evidence for the claim using different vocabulary.
    """
    test_timestamp = datetime.now().isoformat() + "Z"
    cases = []
    
    entailment_pairs = [
        # General to specific
        ("The vehicle accelerated rapidly",
         "The car sped up quickly moving from 30 to 60 mph in seconds"),
        
        # Specific to general
        ("Dogs are mammals",
         "Golden Retrievers, Poodles, and German Shepherds are all warm-blooded vertebrates that nurse their young"),
        
        # Causal relationship
        ("Exercise improves cardiovascular health",
         "Regular physical activity strengthens the heart muscle and improves blood circulation"),
        
        # Definitional
        ("Photosynthesis produces oxygen",
         "Plants convert carbon dioxide and water into glucose and O2 using sunlight"),
        
        # Factual support
        ("Einstein developed the theory of relativity",
         "Albert Einstein published his general relativity paper in 1915, revolutionizing physics"),
    ]
    
    for i, (statement, support) in enumerate(entailment_pairs):
        claim = AtomicClaim(
            statement=statement,
            support_text=support,
            source_url=f"https://example.com/entailment_{i}",
            confidence=0.95,
            extracted_at=test_timestamp,
            discovered_entities=[]
        )
        cases.append(TestClaim(claim, "ENTAILMENT", "entailment"))
    
    return cases


def create_irrelevant_cases() -> List[TestClaim]:
    """Create obviously irrelevant cases (control group).
    
    These should be rejected by both methods.
    """
    test_timestamp = datetime.now().isoformat() + "Z"
    cases = []
    
    irrelevant_pairs = [
        ("Quantum computing uses qubits for parallel computations",
         "Bananas are rich in potassium and provide energy"),
        
        ("Machine learning models require training data",
         "The Great Wall of China is visible from space"),
        
        ("DNA stores genetic information",
         "Coffee contains caffeine which acts as a stimulant"),
    ]
    
    for i, (statement, support) in enumerate(irrelevant_pairs):
        claim = AtomicClaim(
            statement=statement,
            support_text=support,
            source_url=f"https://example.com/irrelevant_{i}",
            confidence=0.5,
            extracted_at=test_timestamp,
            discovered_entities=[]
        )
        cases.append(TestClaim(claim, "NO_ENTAILMENT", "irrelevant"))
    
    return cases


def create_adversarial_test_claims() -> List[TestClaim]:
    """Generate adversarial test claims for rigorous NLI evaluation.
    
    Returns a diverse set of test cases designed to expose differences
    between word-overlap heuristics and semantic understanding.
    """
    all_cases = []
    
    # Combine all test case categories
    all_cases.extend(create_paraphrase_cases())      # ~5 cases
    all_cases.extend(create_contradiction_cases())   # ~5 cases
    all_cases.extend(create_partial_overlap_cases()) # ~5 cases
    all_cases.extend(create_entailment_cases())      # ~5 cases
    all_cases.extend(create_irrelevant_cases())      # ~3 cases
    
    return all_cases  # ~23 adversarial test cases total


def benchmark_method(
    method: str,
    test_query: any,
    test_claims: List[TestClaim]
) -> BenchmarkResult:
    """Benchmark a single verification method on a query.
    
    Args:
        method: "nli" or "heuristic"
        test_query: Query object from test_queries
        test_claims: List of TestClaim objects with ground truth labels
        
    Returns:
        BenchmarkResult with performance metrics
    """
    use_nli = (method == "nli")
    # Use empirically optimized threshold (0.60) instead of arbitrary 0.65
    # See artifacts/threshold_optimization.json for grid search results
    critic = CriticService(use_nli=use_nli, nli_threshold=0.60)
    
    # Extract AtomicClaim objects for verification
    claims = [tc.claim for tc in test_claims]
    
    start_time = time.time()
    results = critic.verify(claims, task=test_query.question)
    end_time = time.time()
    
    processing_time_ms = (end_time - start_time) * 1000
    
    # Calculate metrics using ground truth
    true_positives = 0
    false_positives = 0
    true_negatives = 0
    false_negatives = 0
    
    category_breakdown = {}
    
    for test_claim, result in zip(test_claims, results):
        # For NLI evaluation, ENTAILMENT means claim is supported
        # CONTRADICTION and NO_ENTAILMENT mean claim should be rejected
        should_accept = (test_claim.ground_truth == "ENTAILMENT")
        was_accepted = result.is_valid
        
        # Update confusion matrix
        if should_accept and was_accepted:
            true_positives += 1
        elif not should_accept and was_accepted:
            false_positives += 1
        elif should_accept and not was_accepted:
            false_negatives += 1
        elif not should_accept and not was_accepted:
            true_negatives += 1
        
        # Track by category
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
    
    # Calculate metrics
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    accepted = sum(1 for r in results if r.is_valid)
    rejected = sum(1 for r in results if not r.is_valid)
    
    # Get cache stats if using NLI
    cache_hit_rate = 0.0
    if use_nli and hasattr(critic, '_nli_verifier') and critic._nli_verifier:
        cache_stats = critic._nli_verifier.get_cache_stats()
        cache_hit_rate = cache_stats.get('hit_rate', 0.0)
    
    return BenchmarkResult(
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
        category_breakdown=category_breakdown
    )



def run_benchmark(output_path: str = None) -> Dict:
    """Run full benchmark comparing NLI vs heuristic on adversarial test set.
    
    Returns:
        Dictionary with benchmark results and summary statistics
    """
    print("=" * 80)
    print("NLI VERIFIER BENCHMARK - ADVERSARIAL TEST SET")
    print("=" * 80)
    print()
    
    all_results = []
    
    # Generate adversarial test claims once (query-independent)
    print("Generating adversarial test set...")
    test_claims = create_adversarial_test_claims()
    print(f"Created {len(test_claims)} adversarial test cases:")
    
    # Count by category
    category_counts = {}
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
            
            # Benchmark heuristic method
            print(f"  [Heuristic] Running...")
            heuristic_result = benchmark_method("heuristic", query, test_claims)
            all_results.append(heuristic_result)
            print(f"  [Heuristic] Precision: {heuristic_result.precision:.2%}, "
                  f"Recall: {heuristic_result.recall:.2%}, "
                  f"F1: {heuristic_result.f1_score:.2%}, "
                  f"Time: {heuristic_result.avg_processing_time_ms:.1f}ms")
            
            # Benchmark NLI method
            print(f"  [NLI]       Running...")
            nli_result = benchmark_method("nli", query, test_claims)
            all_results.append(nli_result)
            print(f"  [NLI]       Precision: {nli_result.precision:.2%}, "
                  f"Recall: {nli_result.recall:.2%}, "
                  f"F1: {nli_result.f1_score:.2%}, "
                  f"Time: {nli_result.avg_processing_time_ms:.1f}ms, "
                  f"Cache Hit: {nli_result.cache_hit_rate:.1%}")
            
            # Compute improvement
            f1_improvement = nli_result.f1_score - heuristic_result.f1_score
            precision_improvement = nli_result.precision - heuristic_result.precision
            recall_improvement = nli_result.recall - heuristic_result.recall
            print(f"  [Δ]         F1 Δ: {f1_improvement:+.2%}, "
                  f"Precision Δ: {precision_improvement:+.2%}, "
                  f"Recall Δ: {recall_improvement:+.2%}")
    
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
        
        # Calculate average metrics
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
            "nli_avg_cache_hit_rate": avg_nli_cache_hit
        }
        
        print(f"\n{complexity_name.upper()}:")
        print(f"  Heuristic - Precision: {avg_heuristic_precision:.2%}, Recall: {avg_heuristic_recall:.2%}, F1: {avg_heuristic_f1:.2%}")
        print(f"  NLI       - Precision: {avg_nli_precision:.2%}, Recall: {avg_nli_recall:.2%}, F1: {avg_nli_f1:.2%}")
        print(f"  Improvement - F1: {f1_improvement:+.2%} ({f1_improvement/avg_heuristic_f1:+.1%}), "
              f"Precision: {precision_improvement:+.2%}, Recall: {recall_improvement:+.2%}")
        print(f"  NLI Cache Hit Rate: {avg_nli_cache_hit:.1%}")
    
    # Category breakdown analysis
    print("\n" + "=" * 80)
    print("CATEGORY BREAKDOWN - NLI vs Heuristic")
    print("=" * 80)
    
    # Aggregate category performance across all queries
    category_stats = {}
    for result in all_results:
        if result.category_breakdown:
            for category, metrics in result.category_breakdown.items():
                if category not in category_stats:
                    category_stats[category] = {"nli": {"tp": 0, "fp": 0, "tn": 0, "fn": 0},
                                               "heuristic": {"tp": 0, "fp": 0, "tn": 0, "fn": 0}}
                
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
    
    # Check if we met the target
    complex_f1_improvement = summary.get("complex", {}).get("f1_improvement_pct", 0)
    target_met = complex_f1_improvement > 0.10
    
    print(f"\n{'='*80}")
    print(f"TARGET: >10% F1 improvement on complex queries")
    print(f"RESULT: {complex_f1_improvement:+.1%} - {'✓ PASS' if target_met else '✗ FAIL'}")
    print(f"{'='*80}\n")
    
    # Prepare output
    output = {
        "timestamp": datetime.now().isoformat(),
        "test_set_size": len(test_claims),
        "test_set_categories": category_counts,
        "detailed_results": [asdict(r) for r in all_results],
        "summary": summary,
        "category_analysis": category_stats,
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
