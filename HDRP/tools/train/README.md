# NLI Fine-Tuning (SciFact)

This directory contains scripts to prepare SciFact data and fine-tune the NLI
cross-encoder used by the Critic.

## 1) Prepare SciFact NLI JSONL

SciFact is distributed separately. You can either download it manually or let
the script fetch it via Hugging Face datasets.

```bash
# Manual download
python HDRP/tools/train/prepare_scifact_nli.py \
  --scifact-dir /path/to/scifact \
  --output-dir artifacts/scifact_nli

# Automatic download via Hugging Face Hub
python HDRP/tools/train/prepare_scifact_nli.py \
  --output-dir artifacts/scifact_nli \
  --dataset-name allenai/scifact
```

Outputs:
- `artifacts/scifact_nli/train.jsonl`
- `artifacts/scifact_nli/dev.jsonl`
- `artifacts/scifact_nli/test.jsonl`
- `artifacts/scifact_nli/stats.json`

Label mapping:
- `SUPPORTS` → `ENTAILMENT`
- `REFUTES` → `CONTRADICTION`
- `NOT_ENOUGH_INFO` → `NO_ENTAILMENT`

## 2) Fine-tune the cross-encoder

```bash
python HDRP/tools/train/train_scifact_nli.py \
  --train-file artifacts/scifact_nli/train.jsonl \
  --dev-file artifacts/scifact_nli/dev.jsonl \
  --output-dir artifacts/nli_scifact \
  --epochs 1
```

The model will be saved to `artifacts/nli_scifact/` with a `label_map.json`
documenting class indices.

## 3) Benchmark against the baseline

```bash
python benchmark.py scifact \
  --test-file artifacts/scifact_nli/test.jsonl \
  --baseline-model cross-encoder/nli-deberta-v3-base \
  --tuned-model artifacts/nli_scifact \
  --output-report artifacts/scifact_nli_benchmark.json
```

## 4) Switch the Critic to the tuned model

```bash
export HDRP_NLI_MODEL_NAME="artifacts/nli_scifact"
```

If you export to ONNX, also set `HDRP_NLI_ONNX_PATH` and switch the backend
to `onnxruntime`.
