#!/usr/bin/env python3
"""
Fine-tune a cross-encoder on SciFact NLI data.

Input JSONL format (from prepare_scifact_nli.py):
  {"premise": "...", "hypothesis": "...", "label": "ENTAILMENT|CONTRADICTION|NO_ENTAILMENT"}
"""

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List

from torch.utils.data import DataLoader
from sentence_transformers import CrossEncoder, InputExample
from sentence_transformers.cross_encoder.evaluation import CESoftmaxAccuracyEvaluator


LABEL_TO_ID = {
    "CONTRADICTION": 0,
    "NO_ENTAILMENT": 1,
    "ENTAILMENT": 2,
}


def read_jsonl(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def load_examples(path: Path) -> List[InputExample]:
    examples = []
    for row in read_jsonl(path):
        label = LABEL_TO_ID.get(row.get("label"))
        if label is None:
            continue
        premise = row.get("premise")
        hypothesis = row.get("hypothesis")
        if not premise or not hypothesis:
            continue
        examples.append(InputExample(texts=[premise, hypothesis], label=label))
    return examples


def main() -> None:
    parser = argparse.ArgumentParser(description="Fine-tune NLI cross-encoder on SciFact data.")
    parser.add_argument("--train-file", required=True, help="Path to train.jsonl")
    parser.add_argument("--dev-file", help="Path to dev.jsonl")
    parser.add_argument(
        "--model-name",
        default="cross-encoder/nli-deberta-v3-base",
        help="Base model to fine-tune",
    )
    parser.add_argument("--output-dir", default="artifacts/nli_scifact", help="Output directory")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--warmup-steps", type=int, default=200)
    args = parser.parse_args()

    train_examples = load_examples(Path(args.train_file))
    if not train_examples:
        raise ValueError("No training examples found.")

    train_dataloader = DataLoader(train_examples, shuffle=True, batch_size=args.batch_size)

    model = CrossEncoder(
        args.model_name,
        num_labels=3,
        max_length=args.max_length,
    )

    evaluator = None
    if args.dev_file:
        dev_examples = load_examples(Path(args.dev_file))
        if dev_examples:
            evaluator = CESoftmaxAccuracyEvaluator.from_input_examples(
                dev_examples,
                name="scifact-dev",
            )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    model.fit(
        train_dataloader=train_dataloader,
        evaluator=evaluator,
        epochs=args.epochs,
        warmup_steps=args.warmup_steps,
        output_path=str(output_dir),
        show_progress_bar=True,
    )

    # Explicitly save the model
    model.save(str(output_dir))
    print(f"Model saved to {output_dir}")

    label_map_path = output_dir / "label_map.json"
    label_map_path.write_text(json.dumps(LABEL_TO_ID, indent=2), encoding="utf-8")

    readme_path = output_dir / "README.md"
    readme_path.write_text(
        "\n".join(
            [
                "# SciFact NLI Fine-Tuned Model",
                "",
                "This directory contains a cross-encoder fine-tuned on SciFact for NLI.",
                "",
                "## Label Mapping",
                json.dumps(LABEL_TO_ID, indent=2),
                "",
                "## Notes",
                "- Use `HDRP_NLI_MODEL_NAME` to point the Critic to this model.",
                "- Export to ONNX with `HDRP/tools/eval/export_nli_onnx.py` if needed.",
            ]
        ),
        encoding="utf-8",
    )

    print(f"Saved fine-tuned model to {output_dir}")


if __name__ == "__main__":
    main()
