#!/usr/bin/env python3
"""
Re-split SciFact NLI data into train/dev/test with claim-level separation.

This ensures that the same claim never appears in multiple splits, which is
critical for evaluating generalization to genuinely unseen scientific claims.
"""

import argparse
import json
import random
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple


def read_jsonl(path: Path) -> List[dict]:
    """Read all lines from a JSONL file."""
    examples = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            examples.append(json.loads(line))
    return examples


def write_jsonl(path: Path, rows: List[dict]) -> None:
    """Write examples to a JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def group_by_claim(examples: List[dict]) -> Dict[int, List[dict]]:
    """Group examples by claim_id."""
    grouped = defaultdict(list)
    for example in examples:
        claim_id = example.get("claim_id")
        if claim_id is not None:
            grouped[claim_id].append(example)
    return dict(grouped)


def determine_claim_label(examples: List[dict]) -> str:
    """Determine the majority label for a claim's examples."""
    labels = [ex["label"] for ex in examples]
    label_counts = Counter(labels)
    # Return the most common label
    return label_counts.most_common(1)[0][0]


def stratified_split_claims(
    claims_by_label: Dict[str, List[int]],
    train_ratio: float,
    dev_ratio: float,
    test_ratio: float,
    rng: random.Random,
) -> Tuple[List[int], List[int], List[int]]:
    """
    Perform stratified split of claim IDs by label.
    
    Returns (train_claims, dev_claims, test_claims)
    """
    train_claims = []
    dev_claims = []
    test_claims = []
    
    for label, claim_ids in claims_by_label.items():
        # Shuffle claims within this label
        shuffled = list(claim_ids)
        rng.shuffle(shuffled)
        
        # Calculate split points
        n = len(shuffled)
        train_end = int(n * train_ratio)
        dev_end = train_end + int(n * dev_ratio)
        
        # Split
        train_claims.extend(shuffled[:train_end])
        dev_claims.extend(shuffled[train_end:dev_end])
        test_claims.extend(shuffled[dev_end:])
    
    return train_claims, dev_claims, test_claims


def summarize_split(examples: List[dict]) -> Dict[str, int]:
    """Generate statistics for a split."""
    label_counts = Counter(ex["label"] for ex in examples)
    claim_ids = set(ex["claim_id"] for ex in examples)
    
    return {
        "total_examples": len(examples),
        "unique_claims": len(claim_ids),
        "label_distribution": dict(label_counts),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Re-split SciFact NLI data with claim-level separation."
    )
    parser.add_argument(
        "--input-dir",
        default="artifacts/scifact_nli",
        help="Directory containing current train.jsonl and dev.jsonl",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/scifact_nli",
        help="Directory for new split files",
    )
    parser.add_argument(
        "--backup-dir",
        help="Optional directory to backup original files before overwriting",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible splits",
    )
    parser.add_argument(
        "--train-ratio",
        type=float,
        default=0.65,
        help="Proportion of claims for training",
    )
    parser.add_argument(
        "--dev-ratio",
        type=float,
        default=0.15,
        help="Proportion of claims for development",
    )
    parser.add_argument(
        "--test-ratio",
        type=float,
        default=0.20,
        help="Proportion of claims for testing",
    )
    args = parser.parse_args()
    
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    
    # Validate ratios
    total_ratio = args.train_ratio + args.dev_ratio + args.test_ratio
    if abs(total_ratio - 1.0) > 0.001:
        raise ValueError(f"Ratios must sum to 1.0, got {total_ratio}")
    
    # Create backup if requested
    if args.backup_dir:
        backup_dir = Path(args.backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)
        for filename in ["train.jsonl", "dev.jsonl", "test.jsonl", "stats.json"]:
            src = input_dir / filename
            if src.exists():
                shutil.copy2(src, backup_dir / filename)
        print(f"Backed up original files to {backup_dir}")
    
    # Load all existing examples
    print("Loading existing data...")
    all_examples = []
    
    train_file = input_dir / "train.jsonl"
    if train_file.exists():
        train_examples = read_jsonl(train_file)
        all_examples.extend(train_examples)
        print(f"  Loaded {len(train_examples)} examples from train.jsonl")
    
    dev_file = input_dir / "dev.jsonl"
    if dev_file.exists():
        dev_examples = read_jsonl(dev_file)
        all_examples.extend(dev_examples)
        print(f"  Loaded {len(dev_examples)} examples from dev.jsonl")
    
    if not all_examples:
        raise ValueError(f"No examples found in {input_dir}")
    
    print(f"Total examples loaded: {len(all_examples)}")
    
    # Group examples by claim
    print("\nGrouping examples by claim_id...")
    claim_groups = group_by_claim(all_examples)
    print(f"Found {len(claim_groups)} unique claims")
    
    # Determine majority label for each claim (for stratification)
    print("\nDetermining majority label for each claim...")
    claims_by_label = defaultdict(list)
    for claim_id, examples in claim_groups.items():
        majority_label = determine_claim_label(examples)
        claims_by_label[majority_label].append(claim_id)
    
    print("Claims by label:")
    for label, claim_ids in claims_by_label.items():
        print(f"  {label}: {len(claim_ids)} claims")
    
    # Perform stratified split at claim level
    print(f"\nPerforming stratified split (train={args.train_ratio:.0%}, dev={args.dev_ratio:.0%}, test={args.test_ratio:.0%})...")
    rng = random.Random(args.seed)
    train_claims, dev_claims, test_claims = stratified_split_claims(
        claims_by_label,
        args.train_ratio,
        args.dev_ratio,
        args.test_ratio,
        rng,
    )
    
    print(f"  Train: {len(train_claims)} claims")
    print(f"  Dev: {len(dev_claims)} claims")
    print(f"  Test: {len(test_claims)} claims")
    
    # Verify no overlap
    train_set = set(train_claims)
    dev_set = set(dev_claims)
    test_set = set(test_claims)
    
    assert len(train_set & dev_set) == 0, "Train/dev overlap detected!"
    assert len(train_set & test_set) == 0, "Train/test overlap detected!"
    assert len(dev_set & test_set) == 0, "Dev/test overlap detected!"
    print("  ✓ No claim overlap between splits")
    
    # Collect examples for each split
    print("\nCollecting examples for each split...")
    train_examples = []
    dev_examples = []
    test_examples = []
    
    for claim_id, examples in claim_groups.items():
        if claim_id in train_set:
            train_examples.extend(examples)
        elif claim_id in dev_set:
            dev_examples.extend(examples)
        elif claim_id in test_set:
            test_examples.extend(examples)
    
    # Write splits to output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\nWriting new splits to {output_dir}...")
    write_jsonl(output_dir / "train.jsonl", train_examples)
    print(f"  train.jsonl: {len(train_examples)} examples")
    
    write_jsonl(output_dir / "dev.jsonl", dev_examples)
    print(f"  dev.jsonl: {len(dev_examples)} examples")
    
    write_jsonl(output_dir / "test.jsonl", test_examples)
    print(f"  test.jsonl: {len(test_examples)} examples")
    
    # Generate statistics
    print("\nGenerating statistics...")
    stats = {
        "train": summarize_split(train_examples),
        "dev": summarize_split(dev_examples),
        "test": summarize_split(test_examples),
    }
    
    stats_path = output_dir / "stats.json"
    stats_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(f"  stats.json written")
    
    # Print summary
    print("\n" + "="*60)
    print("SPLIT SUMMARY")
    print("="*60)
    for split_name in ["train", "dev", "test"]:
        split_stats = stats[split_name]
        print(f"\n{split_name.upper()}:")
        print(f"  Examples: {split_stats['total_examples']}")
        print(f"  Unique claims: {split_stats['unique_claims']}")
        print(f"  Label distribution:")
        for label, count in split_stats['label_distribution'].items():
            pct = 100 * count / split_stats['total_examples']
            print(f"    {label}: {count} ({pct:.1f}%)")
    
    print("\n" + "="*60)
    print("Re-split completed successfully!")
    print("="*60)


if __name__ == "__main__":
    main()
