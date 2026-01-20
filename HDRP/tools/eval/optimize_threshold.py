#!/usr/bin/env python3
"""
NLI Threshold Optimization via Grid Search

Finds the optimal NLI entailment threshold by maximizing F1 score on a validation set.
The current fixed threshold of 0.65 has no empirical validation, which can lead to:
- High false negatives (threshold too strict)
- High false positives (threshold too lenient)

This script:
1. Generates labeled validation claims with ground truth
2. Runs grid search over threshold values (0.50 to 0.85)
3. Calculates precision, recall, F1 for each threshold
4. Identifies optimal threshold that maximizes F1 score
5. Saves detailed results for analysis

Usage:
    python HDRP/tools/eval/optimize_threshold.py --output artifacts/threshold_optimization.json
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

from HDRP.services.critic.nli_verifier import NLIVerifier
from HDRP.services.shared.claims import AtomicClaim
from HDRP.tools.eval.test_queries import ALL_QUERIES


@dataclass
class LabeledClaim:
    """A claim with ground truth label for validation."""
    claim: AtomicClaim
    is_valid: bool  # Ground truth: should this claim be accepted?
    label_reason: str  # Why this is valid/invalid


@dataclass
class ThresholdMetrics:
    """Performance metrics for a single threshold value."""
    threshold: float
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float
    accuracy: float


def create_labeled_validation_set() -> List[LabeledClaim]:
    """Create a validation set with labeled ground truth claims.
    
    Generates claims across multiple categories:
    - Valid + relevant (TRUE POSITIVE targets)
    - Valid + marginally relevant (EDGE CASE targets)
    - Invalid due to poor grounding (FALSE POSITIVE targets)
    - Invalid due to contradiction (FALSE POSITIVE targets)
    - Irrelevant but well-grounded (FALSE POSITIVE targets)
    
    Returns:
        List of labeled claims with ground truth
    """
    test_timestamp = datetime.now().isoformat() + "Z"
    labeled_claims = []
    
    # Sample queries for diversity
    sample_queries = ALL_QUERIES[:5]  # Use first 5 queries for validation
    
    for query in sample_queries:
        query_topic = query.question.lower()
        
        # Extract key topic words
        topic_words = [w for w in query_topic.split() if len(w) > 3][:2]
        topic = " ".join(topic_words) if topic_words else "technology"
        
        # 1. VALID + HIGHLY RELEVANT (should be accepted)
        # Perfect entailment: statement is directly in support text
        statement = f"{topic.title()} is a critical field with significant applications."
        labeled_claims.append(LabeledClaim(
            claim=AtomicClaim(
                statement=statement,
                support_text=statement,  # Perfect match
                source_url="https://example.com/valid_1",
                confidence=0.9,
                extracted_at=test_timestamp,
                discovered_entities=[topic.title()]
            ),
            is_valid=True,
            label_reason="Perfect entailment - statement matches support exactly"
        ))
        
        # 2. VALID + PARAPHRASED (should be accepted)
        # Strong semantic entailment but different wording
        statement = f"Research shows that {topic} has advanced rapidly in recent years."
        support_text = f"Studies indicate significant progress in {topic} development over the past decade."
        labeled_claims.append(LabeledClaim(
            claim=AtomicClaim(
                statement=statement,
                support_text=support_text,
                source_url="https://example.com/valid_2",
                confidence=0.85,
                extracted_at=test_timestamp,
                discovered_entities=[topic.title()]
            ),
            is_valid=True,
            label_reason="Strong semantic entailment - paraphrased but well-supported"
        ))
        
        # 3. MARGINALLY RELEVANT (edge case - may accept or reject)
        # Weak but not contradictory entailment
        statement = f"{topic.title()} systems require specialized expertise."
        support_text = f"Working with {topic} often involves complex knowledge."
        labeled_claims.append(LabeledClaim(
            claim=AtomicClaim(
                statement=statement,
                support_text=support_text,
                source_url="https://example.com/marginal_1",
                confidence=0.75,
                extracted_at=test_timestamp,
                discovered_entities=[topic.title()]
            ),
            is_valid=True,  # Weakly valid
            label_reason="Weak entailment but semantically aligned"
        ))
        
        # 4. INVALID - POOR GROUNDING (should be rejected)
        # Claim makes strong assertion not supported by weak evidence
        statement = f"{topic.title()} will revolutionize all aspects of modern society within 5 years."
        support_text = f"{topic.title()} is being studied by researchers."
        labeled_claims.append(LabeledClaim(
            claim=AtomicClaim(
                statement=statement,
                support_text=support_text,
                source_url="https://example.com/invalid_1",
                confidence=0.6,
                extracted_at=test_timestamp,
                discovered_entities=[topic.title()]
            ),
            is_valid=False,
            label_reason="Weak grounding - claim far exceeds support"
        ))
        
        # 5. INVALID - CONTRADICTION (should be rejected)
        # Support text contradicts or refutes the claim
        statement = f"{topic.title()} is simple and easy to understand."
        support_text = f"{topic.title()} is highly complex and difficult to master."
        labeled_claims.append(LabeledClaim(
            claim=AtomicClaim(
                statement=statement,
                support_text=support_text,
                source_url="https://example.com/invalid_2",
                confidence=0.5,
                extracted_at=test_timestamp,
                discovered_entities=[topic.title()]
            ),
            is_valid=False,
            label_reason="Contradiction - support refutes claim"
        ))
        
        # 6. INVALID - IRRELEVANT (should be rejected)
        # Well-grounded but completely irrelevant to query
        statement = "The Pacific Ocean is the largest ocean on Earth."
        support_text = "The Pacific Ocean covers approximately 165 million square kilometers."
        labeled_claims.append(LabeledClaim(
            claim=AtomicClaim(
                statement=statement,
                support_text=statement,
                source_url="https://example.com/invalid_3",
                confidence=0.9,
                extracted_at=test_timestamp,
                discovered_entities=["Pacific Ocean"]
            ),
            is_valid=False,
            label_reason="Irrelevant - not related to query topic"
        ))
    
    print(f"Created validation set: {len(labeled_claims)} labeled claims")
    print(f"  - Valid claims: {sum(1 for lc in labeled_claims if lc.is_valid)}")
    print(f"  - Invalid claims: {sum(1 for lc in labeled_claims if not lc.is_valid)}")
    
    return labeled_claims


def evaluate_threshold(
    threshold: float,
    labeled_claims: List[LabeledClaim],
    nli_verifier: NLIVerifier
) -> ThresholdMetrics:
    """Evaluate NLI performance at a specific threshold.
    
    Args:
        threshold: NLI entailment threshold to test
        labeled_claims: Validation set with ground truth labels
        nli_verifier: NLI verifier instance
        
    Returns:
        Performance metrics for this threshold
    """
    true_positives = 0
    false_positives = 0
    true_negatives = 0
    false_negatives = 0
    
    for labeled_claim in labeled_claims:
        claim = labeled_claim.claim
        ground_truth = labeled_claim.is_valid
        
        # Compute NLI entailment score
        nli_score = nli_verifier.compute_entailment(
            premise=claim.support_text,
            hypothesis=claim.statement
        )
        
        # Make prediction based on threshold
        predicted_valid = nli_score >= threshold
        
        # Update confusion matrix
        if ground_truth and predicted_valid:
            true_positives += 1
        elif not ground_truth and predicted_valid:
            false_positives += 1
        elif not ground_truth and not predicted_valid:
            true_negatives += 1
        elif ground_truth and not predicted_valid:
            false_negatives += 1
    
    # Calculate metrics
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (true_positives + true_negatives) / len(labeled_claims) if len(labeled_claims) > 0 else 0.0
    
    return ThresholdMetrics(
        threshold=threshold,
        true_positives=true_positives,
        false_positives=false_positives,
        true_negatives=true_negatives,
        false_negatives=false_negatives,
        precision=precision,
        recall=recall,
        f1_score=f1_score,
        accuracy=accuracy
    )


def grid_search_threshold(
    labeled_claims: List[LabeledClaim],
    min_threshold: float = 0.50,
    max_threshold: float = 0.85,
    step: float = 0.01
) -> Tuple[ThresholdMetrics, List[ThresholdMetrics]]:
    """Run grid search to find optimal threshold.
    
    Args:
        labeled_claims: Validation set with ground truth
        min_threshold: Minimum threshold to test
        max_threshold: Maximum threshold to test
        step: Increment step size
        
    Returns:
        Tuple of (optimal_metrics, all_metrics)
    """
    print("\n" + "=" * 80)
    print("RUNNING GRID SEARCH FOR OPTIMAL THRESHOLD")
    print("=" * 80)
    print(f"Range: [{min_threshold:.2f}, {max_threshold:.2f}], Step: {step:.2f}")
    print(f"Validation set size: {len(labeled_claims)} claims")
    print()
    
    # Initialize NLI verifier
    nli_verifier = NLIVerifier()
    
    # Test each threshold
    all_metrics = []
    thresholds = []
    current = min_threshold
    while current <= max_threshold:
        thresholds.append(current)
        current = round(current + step, 2)
    
    for i, threshold in enumerate(thresholds):
        metrics = evaluate_threshold(threshold, labeled_claims, nli_verifier)
        all_metrics.append(metrics)
        
        # Progress indicator
        if (i + 1) % 5 == 0 or i == 0 or i == len(thresholds) - 1:
            print(f"Threshold {threshold:.2f}: P={metrics.precision:.3f}, R={metrics.recall:.3f}, F1={metrics.f1_score:.3f}")
    
    # Find optimal threshold (maximize F1)
    optimal_metrics = max(all_metrics, key=lambda m: m.f1_score)
    
    print("\n" + "=" * 80)
    print("OPTIMIZATION RESULTS")
    print("=" * 80)
    print(f"Optimal Threshold: {optimal_metrics.threshold:.2f}")
    print(f"  - Precision: {optimal_metrics.precision:.3f}")
    print(f"  - Recall:    {optimal_metrics.recall:.3f}")
    print(f"  - F1 Score:  {optimal_metrics.f1_score:.3f}")
    print(f"  - Accuracy:  {optimal_metrics.accuracy:.3f}")
    print(f"\nConfusion Matrix:")
    print(f"  - True Positives:  {optimal_metrics.true_positives}")
    print(f"  - False Positives: {optimal_metrics.false_positives}")
    print(f"  - True Negatives:  {optimal_metrics.true_negatives}")
    print(f"  - False Negatives: {optimal_metrics.false_negatives}")
    print("=" * 80)
    
    # Get cache stats
    cache_stats = nli_verifier.get_cache_stats()
    print(f"\nNLI Cache Statistics:")
    print(f"  - Cache Hit Rate: {cache_stats['hit_rate']:.1%}")
    print(f"  - Cache Size: {cache_stats['cache_size']}/{cache_stats['cache_max_size']}")
    
    return optimal_metrics, all_metrics


def save_optimization_results(
    optimal_metrics: ThresholdMetrics,
    all_metrics: List[ThresholdMetrics],
    output_path: str
) -> None:
    """Save optimization results to JSON file.
    
    Args:
        optimal_metrics: Best threshold metrics
        all_metrics: Metrics for all tested thresholds
        output_path: Path to save results JSON
    """
    output = {
        "timestamp": datetime.now().isoformat(),
        "optimization_method": "grid_search",
        "objective": "maximize_f1_score",
        "optimal_threshold": optimal_metrics.threshold,
        "optimal_metrics": asdict(optimal_metrics),
        "previous_threshold": 0.65,
        "previous_threshold_note": "Hardcoded value with no empirical validation",
        "all_thresholds": [asdict(m) for m in all_metrics],
        "summary": {
            "threshold_range": f"[{all_metrics[0].threshold:.2f}, {all_metrics[-1].threshold:.2f}]",
            "num_thresholds_tested": len(all_metrics),
            "optimal_f1": optimal_metrics.f1_score,
            "optimal_precision": optimal_metrics.precision,
            "optimal_recall": optimal_metrics.recall,
        }
    }
    
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\nResults saved to: {output_file}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Optimize NLI threshold via grid search on validation set"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="artifacts/threshold_optimization.json",
        help="Path to save optimization results JSON"
    )
    parser.add_argument(
        "--min-threshold",
        type=float,
        default=0.50,
        help="Minimum threshold to test"
    )
    parser.add_argument(
        "--max-threshold",
        type=float,
        default=0.85,
        help="Maximum threshold to test"
    )
    parser.add_argument(
        "--step",
        type=float,
        default=0.01,
        help="Threshold increment step"
    )
    
    args = parser.parse_args()
    
    # Create validation set
    labeled_claims = create_labeled_validation_set()
    
    # Run grid search
    start_time = time.time()
    optimal_metrics, all_metrics = grid_search_threshold(
        labeled_claims,
        min_threshold=args.min_threshold,
        max_threshold=args.max_threshold,
        step=args.step
    )
    elapsed_time = time.time() - start_time
    
    print(f"\nTotal optimization time: {elapsed_time:.2f}s")
    
    # Save results
    save_optimization_results(optimal_metrics, all_metrics, args.output)
    
    print("\n✓ Threshold optimization complete!")
    print(f"  → Use threshold {optimal_metrics.threshold:.2f} in CriticService")


if __name__ == "__main__":
    main()
