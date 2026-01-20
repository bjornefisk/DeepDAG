#!/usr/bin/env python3
"""
Direct NLI Benchmark - Test NLI verifier in isolation

This script evaluates the NLI verifier's ability to detect entailment
without the complexity of the full CriticService pipeline. It compares
NLI-based semantic scoring against simple word overlap heuristics.

Usage:
    python HDRP/tools/eval/benchmark_nli_direct.py --output-report artifacts/nli_direct_benchmark.json
"""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict
from dataclasses import dataclass, asdict

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from HDRP.services.critic.nli_verifier import NLIVerifier


@dataclass
class TestCase:
    """Test case with ground truth label."""
    premise: str
    hypothesis: str
    ground_truth: str  # "ENTAILMENT", "CONTRADICTION", or "NO_ENTAILMENT"
    category: str  # Test case category


@dataclass
class BenchmarkResult:
    """Results for a single method."""
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


def create_adversarial_test_cases() -> List[TestCase]:
    """Generate adversarial test cases for NLI evaluation."""
    
    # Paraphrases - semantic equivalence without lexical overlap
    paraphrase_cases = [
        TestCase(
            premise="The computational complexity is O(n)",
            hypothesis="The algorithm runs in linear time",
            ground_truth="ENTAILMENT",
            category="paraphrase"
        ),
        TestCase(
            premise="H2O becomes solid at 0°C",
            hypothesis="Water freezes at zero degrees Celsius",
            ground_truth="ENTAILMENT",
            category="paraphrase"
        ),
        TestCase(
            premise="Corporate earnings grew by one quarter",
            hypothesis="The company's revenue increased by 25 percent",
            ground_truth="ENTAILMENT",
            category="paraphrase"
        ),
        TestCase(
            premise="The method outputs true or false",
            hypothesis="The function returns a boolean value",
            ground_truth="ENTAILMENT",
            category="paraphrase"
        ),
        TestCase(
            premise="Triangle angles total π radians",
            hypothesis="The sum of angles in a triangle equals 180 degrees",
            ground_truth="ENTAILMENT",
            category="paraphrase"
        ),
    ]
    
    # Contradictions - high word overlap but opposite meaning
    contradiction_cases = [
        TestCase(
            premise="Python is an interpreted language",
            hypothesis="Python is a compiled language",
            ground_truth="CONTRADICTION",
            category="contradiction"
        ),
        TestCase(
            premise="The temperature is decreasing",
            hypothesis="The temperature is increasing",
            ground_truth="CONTRADICTION",
            category="contradiction"
        ),
        TestCase(
            premise="The system is offline and inaccessible",
            hypothesis="The system is online and operational",
            ground_truth="CONTRADICTION",
            category="contradiction"
        ),
        TestCase(
            premise="Sound travels faster than lightning",
            hypothesis="Lightning travels faster than sound",
            ground_truth="CONTRADICTION",
            category="contradiction"
        ),
        TestCase(
            premise="The event occurred in the evening",
            hypothesis="The event happened in the morning",
            ground_truth="CONTRADICTION",
            category="contradiction"
        ),
    ]
    
    # Partial overlap - high word overlap but different meaning
    partial_overlap_cases = [
        TestCase(
            premise="Apple trees produce fruit in autumn",
            hypothesis="Apple released a new iPhone model",
            ground_truth="NO_ENTAILMENT",
            category="partial_overlap"
        ),
        TestCase(
            premise="The river bank was eroded by flooding",
            hypothesis="The bank approved the loan application",
            ground_truth="NO_ENTAILMENT",
            category="partial_overlap"
        ),
        TestCase(
            premise="Machine learning uses classical algorithms while quantum computing leverages quantum mechanics",
            hypothesis="Machine learning is quantum computing",
            ground_truth="NO_ENTAILMENT",
            category="partial_overlap"
        ),
        TestCase(
            premise="Neural networks in the brain consist of neurons",
            hypothesis="Neural networks require GPU acceleration",
            ground_truth="NO_ENTAILMENT",
            category="partial_overlap"
        ),
        TestCase(
            premise="The research focuses on climate change prediction",
            hypothesis="The research focuses on climate change mitigation",
            ground_truth="NO_ENTAILMENT",
            category="partial_overlap"
        ),
    ]
    
    # True entailment - varied expression
    entailment_cases = [
        TestCase(
            premise="The car sped up quickly moving from 30 to 60 mph in seconds",
            hypothesis="The vehicle accelerated rapidly",
            ground_truth="ENTAILMENT",
            category="entailment"
        ),
        TestCase(
            premise="Golden Retrievers, Poodles, and German Shepherds are all warm-blooded vertebrates that nurse their young",
            hypothesis="Dogs are mammals",
            ground_truth="ENTAILMENT",
            category="entailment"
        ),
        TestCase(
            premise="Regular physical activity strengthens the heart muscle and improves blood circulation",
            hypothesis="Exercise improves cardiovascular health",
            ground_truth="ENTAILMENT",
            category="entailment"
        ),
        TestCase(
            premise="Plants convert carbon dioxide and water into glucose and O2 using sunlight",
            hypothesis="Photosynthesis produces oxygen",
            ground_truth="ENTAILMENT",
            category="entailment"
        ),
        TestCase(
            premise="Albert Einstein published his general relativity paper in 1915, revolutionizing physics",
            hypothesis="Einstein developed the theory of relativity",
            ground_truth="ENTAILMENT",
            category="entailment"
        ),
    ]
    
    # Irrelevant - control group
    irrelevant_cases = [
        TestCase(
            premise="Bananas are rich in potassium and provide energy",
            hypothesis="Quantum computing uses qubits for parallel computations",
            ground_truth="NO_ENTAILMENT",
            category="irrelevant"
        ),
        TestCase(
            premise="The Great Wall of China is visible from space",
            hypothesis="Machine learning models require training data",
            ground_truth="NO_ENTAILMENT",
            category="irrelevant"
        ),
        TestCase(
            premise="Coffee contains caffeine which acts as a stimulant",
            hypothesis="DNA stores genetic information",
            ground_truth="NO_ENTAILMENT",
            category="irrelevant"
        ),
    ]
    
    all_cases = []
    all_cases.extend(paraphrase_cases)
    all_cases.extend(contradiction_cases)
    all_cases.extend(partial_overlap_cases)
    all_cases.extend(entailment_cases)
    all_cases.extend(irrelevant_cases)
    
    return all_cases


def word_overlap_heuristic(premise: str, hypothesis: str, threshold: float = 0.6) -> bool:
    """Simple word overlap heuristic classifier.
    
    Returns True if overlap ratio >= threshold (predicts entailment).
    """
    import re
    
    # Tokenize
    premise_tokens = set(re.findall(r'\w+', premise.lower()))
    hypothesis_tokens = re.findall(r'\w+', hypothesis.lower())
    
    # Remove stop words
    stop_words = {"the", "is", "at", "of", "on", "and", "a", "to", "in", "for", "with", "by", "from"}
    hypothesis_filtered = [w for w in hypothesis_tokens if w not in stop_words]
    
    if not hypothesis_filtered:
        hypothesis_filtered = hypothesis_tokens
    
    # Calculate overlap
    overlap = sum(1 for w in hypothesis_filtered if w in premise_tokens)
    overlap_ratio = overlap / len(hypothesis_filtered) if hypothesis_filtered else 0.0
    
    return overlap_ratio >= threshold


def benchmark_method(method: str, test_cases: List[TestCase], nli_threshold: float = 0.60) -> BenchmarkResult:
    """Benchmark a single method."""
    
    if method == "nli":
        verifier = NLIVerifier()
    
    true_positives = 0
    false_positives = 0
    true_negatives = 0
    false_negatives = 0
    
    category_breakdown = {}
    
    start_time = time.time()
    
    for test_case in test_cases:
        # Determine prediction
        if method == "nli":
            score = verifier.compute_entailment(test_case.premise, test_case.hypothesis)
            predicted_entailment = (score >= nli_threshold)
        elif method == "heuristic":
            predicted_entailment = word_overlap_heuristic(test_case.premise, test_case.hypothesis)
        else:
            raise ValueError(f"Unknown method: {method}")
        
        # Determine ground truth
        should_accept = (test_case.ground_truth == "ENTAILMENT")
        
        # Update confusion matrix
        if should_accept and predicted_entailment:
            true_positives += 1
        elif not should_accept and predicted_entailment:
            false_positives += 1
        elif should_accept and not predicted_entailment:
            false_negatives += 1
        elif not should_accept and not predicted_entailment:
            true_negatives += 1
        
        # Track by category
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
    
    end_time = time.time()
    processing_time_ms = (end_time - start_time) * 1000
    
    # Calculate metrics
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    return BenchmarkResult(
        method=method,
        true_positives=true_positives,
        false_positives=false_positives,
        true_negatives=true_negatives,
        false_negatives=false_negatives,
        precision=precision,
        recall=recall,
        f1_score=f1_score,
        avg_processing_time_ms=processing_time_ms,
        category_breakdown=category_breakdown
    )


def run_benchmark(output_path: str = None) -> Dict:
    """Run direct NLI benchmark."""
    
    print("=" * 80)
    print("DIRECT NLI BENCHMARK - Testing NLI Verifier in Isolation")
    print("=" * 80)
    print()
    
    # Generate test cases
    print("Generating adversarial test cases...")
    test_cases = create_adversarial_test_cases()
    print(f"Created {len(test_cases)} test cases:")
    
    # Count by category
    category_counts = {}
    for tc in test_cases:
        category_counts[tc.category] = category_counts.get(tc.category, 0) + 1
    
    for category, count in category_counts.items():
        print(f"  - {category}: {count} cases")
    print()
    
    # Benchmark heuristic
    print("Benchmarking word overlap heuristic...")
    heuristic_result = benchmark_method("heuristic", test_cases)
    print(f"  Precision: {heuristic_result.precision:.2%}, "
          f"Recall: {heuristic_result.recall:.2%}, "
          f"F1: {heuristic_result.f1_score:.2%}, "
          f"Time: {heuristic_result.avg_processing_time_ms:.1f}ms")
    print()
    
    # Benchmark NLI
    print("Benchmarking NLI verifier...")
    nli_result = benchmark_method("nli", test_cases)
    print(f"  Precision: {nli_result.precision:.2%}, "
          f"Recall: {nli_result.recall:.2%}, "
          f"F1: {nli_result.f1_score:.2%}, "
          f"Time: {nli_result.avg_processing_time_ms:.1f}ms")
    print()
    
    # Summary
    print("=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    
    f1_improvement = nli_result.f1_score - heuristic_result.f1_score
    precision_improvement = nli_result.precision - heuristic_result.precision
    recall_improvement = nli_result.recall - heuristic_result.recall
    
    print(f"\nOverall Performance:")
    print(f"  Heuristic - Precision: {heuristic_result.precision:.2%}, Recall: {heuristic_result.recall:.2%}, F1: {heuristic_result.f1_score:.2%}")
    print(f"  NLI       - Precision: {nli_result.precision:.2%}, Recall: {nli_result.recall:.2%}, F1: {nli_result.f1_score:.2%}")
    print(f"  Improvement - F1: {f1_improvement:+.2%}, Precision: {precision_improvement:+.2%}, Recall: {recall_improvement:+.2%}")
    
    # Category breakdown
    print("\nCategory Performance:")
    all_categories = set(test_cases[0].category for _ in [0])  # Get unique categories
    for tc in test_cases:
        all_categories |= {tc.category}
    
    for category in sorted(all_categories):
        print(f"\n  {category.upper()}:")
        for method, result in [("Heuristic", heuristic_result), ("NLI", nli_result)]:
            metrics = result.category_breakdown.get(category, {"tp": 0, "fp": 0, "tn": 0, "fn": 0})
            tp, fp, tn, fn = metrics["tp"], metrics["fp"], metrics["tn"], metrics["fn"]
            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * (prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
            print(f"    [{method:10s}] Precision: {prec:.2%}, Recall: {rec:.2%}, F1: {f1:.2%}")
    
    # Check target
    f1_improvement_pct = (f1_improvement / heuristic_result.f1_score * 100) if heuristic_result.f1_score > 0 else 0
    target_met = f1_improvement > 0.10  # Absolute improvement > 10%
    
    print(f"\n{'='*80}")
    print(f"TARGET: >10% absolute F1 improvement")
    print(f"RESULT: {f1_improvement:+.2%} - {'✓ PASS' if target_met else '✗ FAIL'}")
    print(f"{'='*80}\n")
    
    # Prepare output
    output = {
        "timestamp": datetime.now().isoformat(),
        "test_cases_count": len(test_cases),
        "category_counts": category_counts,
        "heuristic_results": asdict(heuristic_result),
        "nli_results": asdict(nli_result),
        "improvements": {
            "f1": f1_improvement,
            "precision": precision_improvement,
            "recall": recall_improvement
        },
        "target_met": target_met
    }
    
    # Save to file
    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2)
        print(f"Results saved to: {output_file}")
    
    return output


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Direct NLI benchmark")
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
