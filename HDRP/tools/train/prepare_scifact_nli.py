#!/usr/bin/env python3
"""
Prepare SciFact dataset for NLI fine-tuning.

Expected SciFact layout (downloaded separately):
  - corpus.jsonl
  - claims_train.jsonl
  - claims_dev.jsonl (or claims_val.jsonl)
  - claims_test.jsonl

Output JSONL format:
  {"premise": "...", "hypothesis": "...", "label": "ENTAILMENT|CONTRADICTION|NO_ENTAILMENT", ...}
"""

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


LABEL_MAP = {
    "SUPPORT": "ENTAILMENT",
    "SUPPORTS": "ENTAILMENT",
    "REFUTE": "CONTRADICTION",
    "REFUTES": "CONTRADICTION",
    "CONTRADICT": "CONTRADICTION",
    "CONTRADICTS": "CONTRADICTION",
    "NOT_ENOUGH_INFO": "NO_ENTAILMENT",
    "NOT_ENOUGH": "NO_ENTAILMENT",
    "NEI": "NO_ENTAILMENT",
}


def read_jsonl(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def load_corpus(corpus_path: Path) -> Dict[str, List[str]]:
    corpus = {}
    for record in read_jsonl(corpus_path):
        doc_id = record.get("doc_id") or record.get("docid") or record.get("id")
        abstract = record.get("abstract") or []
        if doc_id is None:
            continue
        corpus[str(doc_id)] = list(abstract)
    return corpus


def resolve_claim_label(raw_label: Optional[str]) -> Optional[str]:
    if raw_label is None:
        return None
    normalized = str(raw_label).strip().upper().replace(" ", "_")
    return LABEL_MAP.get(normalized)


def extract_evidence_sets(evidence: object) -> List[Tuple[str, List[int], Optional[str]]]:
    """Extract evidence sets with labels from the evidence dictionary.
    
    Returns a list of (doc_id, sentence_ids, label) tuples.
    """
    evidence_sets: List[Tuple[str, List[int], Optional[str]]] = []
    if isinstance(evidence, dict):
        for doc_id, doc_sets in evidence.items():
            if not isinstance(doc_sets, list):
                continue
            for evidence_item in doc_sets:
                # Handle both old format (list of ints) and new format (dict with 'sentences' and 'label')
                if isinstance(evidence_item, dict):
                    sent_ids = evidence_item.get("sentences", [])
                    label = evidence_item.get("label")
                    if sent_ids:
                        evidence_sets.append((str(doc_id), [int(x) for x in sent_ids], label))
                elif isinstance(evidence_item, list):
                    evidence_sets.append((str(doc_id), [int(x) for x in evidence_item], None))
    return evidence_sets


def build_premise(
    corpus: Dict[str, List[str]],
    doc_id: Optional[str],
    sentence_ids: List[int],
    max_sentences: int,
) -> Optional[str]:
    if doc_id is None:
        return None
    sentences = corpus.get(doc_id)
    if not sentences:
        return None
    chosen = []
    for idx in sentence_ids:
        if 0 <= idx < len(sentences):
            chosen.append(sentences[idx])
        if len(chosen) >= max_sentences:
            break
    if not chosen:
        return None
    return " ".join(chosen)


def sample_random_premise(
    corpus: Dict[str, List[str]],
    rng: random.Random,
    max_sentences: int,
) -> Optional[Tuple[str, List[int]]]:
    if not corpus:
        return None
    doc_id = rng.choice(list(corpus.keys()))
    sentences = corpus.get(doc_id, [])
    if not sentences:
        return None
    start_idx = rng.randrange(0, len(sentences))
    sentence_ids = list(range(start_idx, min(start_idx + max_sentences, len(sentences))))
    premise = " ".join(sentences[i] for i in sentence_ids)
    if not premise:
        return None
    return doc_id, sentence_ids


def build_examples_for_claim(
    claim_record: dict,
    corpus: Dict[str, List[str]],
    rng: random.Random,
    max_sentences: int,
) -> List[dict]:
    claim_id = claim_record.get("id")
    hypothesis = claim_record.get("claim") or claim_record.get("statement")
    if not hypothesis:
        return []

    # Check for simple format with top-level evidence fields
    if "evidence_doc_id" in claim_record or "evidence_sentences" in claim_record:
        doc_id = claim_record.get("evidence_doc_id")
        sent_ids = claim_record.get("evidence_sentences") or []
        label = resolve_claim_label(claim_record.get("evidence_label") or claim_record.get("label"))
        if label is None:
            return []
        evidence_sets = [(str(doc_id), [int(x) for x in sent_ids], label)] if doc_id is not None else []
    else:
        # Extract evidence with labels
        evidence = claim_record.get("evidence", {})
        evidence_sets = extract_evidence_sets(evidence)
    
    examples = []

    if evidence_sets:
        for item in evidence_sets:
            if len(item) == 3:
                doc_id, sent_ids, evidence_label = item
            else:
                doc_id, sent_ids = item
                evidence_label = None
            
            # Use evidence-specific label if available, otherwise fall back to claim-level label
            if evidence_label:
                label = resolve_claim_label(evidence_label)
            else:
                label = resolve_claim_label(claim_record.get("evidence_label") or claim_record.get("label"))
            
            if label is None:
                continue
                
            premise = build_premise(corpus, doc_id, sent_ids, max_sentences)
            if not premise:
                continue
            examples.append(
                {
                    "premise": premise,
                    "hypothesis": hypothesis,
                    "label": label,
                    "claim_id": claim_id,
                    "doc_id": doc_id,
                    "sentence_ids": sent_ids,
                }
            )
        return examples

    # If no evidence, try to create negative examples
    claim_label = resolve_claim_label(claim_record.get("evidence_label") or claim_record.get("label"))
    if claim_label == "NO_ENTAILMENT":
        sampled = sample_random_premise(corpus, rng, max_sentences)
        if sampled is None:
            return []
        doc_id, sent_ids = sampled
        premise = build_premise(corpus, doc_id, sent_ids, max_sentences)
        if not premise:
            return []
        return [
            {
                "premise": premise,
                "hypothesis": hypothesis,
                "label": claim_label,
                "claim_id": claim_id,
                "doc_id": doc_id,
                "sentence_ids": sent_ids,
            }
        ]

    return []


def write_jsonl(path: Path, rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def summarize(rows: List[dict]) -> Dict[str, int]:
    counter = Counter(row["label"] for row in rows)
    return dict(counter)


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare SciFact NLI JSONL files.")
    parser.add_argument(
        "--scifact-dir",
        help="Path to SciFact dataset directory (optional if using datasets download)",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/scifact_nli",
        help="Directory for prepared JSONL files",
    )
    parser.add_argument(
        "--dataset-name",
        default="allenai/scifact",
        help="Hugging Face dataset name to download if scifact-dir is missing",
    )
    parser.add_argument("--seed", type=int, default=13, help="Random seed for sampling")
    parser.add_argument(
        "--max-sentences",
        type=int,
        default=3,
        help="Maximum number of evidence sentences to include",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    stats = {}
    rng = random.Random(args.seed)

    corpus = None
    scifact_dir = Path(args.scifact_dir) if args.scifact_dir else None
    corpus_path = scifact_dir / "corpus.jsonl" if scifact_dir else None

    if corpus_path and corpus_path.exists():
        corpus = load_corpus(corpus_path)

        split_files = {
            "train": scifact_dir / "claims_train.jsonl",
            "dev": scifact_dir / "claims_dev.jsonl",
            "test": scifact_dir / "claims_test.jsonl",
        }
        if not split_files["dev"].exists():
            split_files["dev"] = scifact_dir / "claims_val.jsonl"

        for split_name, split_path in split_files.items():
            if not split_path.exists():
                continue
            rows = []
            for record in read_jsonl(split_path):
                rows.extend(
                    build_examples_for_claim(
                        record,
                        corpus,
                        rng=rng,
                        max_sentences=args.max_sentences,
                    )
                )
            write_jsonl(output_dir / f"{split_name}.jsonl", rows)
            stats[split_name] = summarize(rows)
    else:
        # Download SciFact data files from S3
        import urllib.request
        import tempfile
        import tarfile
        
        data_url = "https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz"
        
        # Create a temporary directory for downloaded files
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Download and extract the tarball
            tarball_path = temp_path / "data.tar.gz"
            print(f"Downloading SciFact dataset from {data_url}...")
            urllib.request.urlretrieve(data_url, tarball_path)
            
            print("Extracting data...")
            with tarfile.open(tarball_path, "r:gz") as tar:
                tar.extractall(temp_path)
            
            # The data is extracted to a 'data' subdirectory
            data_path = temp_path / "data"
            corpus_path = data_path / "corpus.jsonl"
            
            if not corpus_path.exists():
                raise FileNotFoundError(f"corpus.jsonl not found in extracted data at {data_path}")
            
            corpus = load_corpus(corpus_path)
            
            # Process claims files
            claims_files = {
                "train": data_path / "claims_train.jsonl",
                "dev": data_path / "claims_dev.jsonl",
                "test": data_path / "claims_test.jsonl",
            }
            
            for split_name, local_path in claims_files.items():
                if not local_path.exists():
                    print(f"Warning: {split_name} split not found at {local_path}")
                    continue
                
                rows = []
                for record in read_jsonl(local_path):
                    rows.extend(
                        build_examples_for_claim(
                            record,
                            corpus,
                            rng=rng,
                            max_sentences=args.max_sentences,
                        )
                    )
                write_jsonl(output_dir / f"{split_name}.jsonl", rows)
                stats[split_name] = summarize(rows)

    stats_path = output_dir / "stats.json"
    stats_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")

    print(f"Prepared SciFact NLI data at {output_dir}")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
