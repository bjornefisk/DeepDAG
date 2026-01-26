#!/usr/bin/env python3
"""
Evaluate NLI models on SciFact JSONL data and compare baseline vs fine-tuned.

Usage:
  python HDRP/tools/eval/benchmark_scifact_nli.py \
    --test-file artifacts/scifact_nli/test.jsonl \
    --baseline-model cross-encoder/nli-deberta-v3-base \
    --tuned-model artifacts/nli_scifact
"""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from HDRP.services.critic.nli_verifier import NLIVerifier


LABELS = ["CONTRADICTION", "NO_ENTAILMENT", "ENTAILMENT"]


def read_jsonl(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def score_to_label(scores: Dict[str, float]) -> str:
    mapping = {
        "entailment": "ENTAILMENT",
        "contradiction": "CONTRADICTION",
        "neutral": "NO_ENTAILMENT",
    }
    best = max(scores.items(), key=lambda item: item[1])[0]
    return mapping.get(best, "NO_ENTAILMENT")


def evaluate_model(model_name: str, rows: List[dict]) -> Dict[str, object]:
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
        pred = score_to_label(relation)
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark NLI models on SciFact data.")
    parser.add_argument("--test-file", required=True, help="Path to SciFact test.jsonl")
    parser.add_argument("--baseline-model", help="Baseline model name or path")
    parser.add_argument("--tuned-model", help="Fine-tuned model name or path")
    parser.add_argument("--output-report", help="Write report JSON to this file")
    args = parser.parse_args()

    rows = list(read_jsonl(Path(args.test_file)))
    if not rows:
        raise ValueError("No test rows found.")

    results = []
    if args.baseline_model:
        results.append(evaluate_model(args.baseline_model, rows))
    if args.tuned_model:
        results.append(evaluate_model(args.tuned_model, rows))

    report = {"results": results}
    if args.output_report:
        Path(args.output_report).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
