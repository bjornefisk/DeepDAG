# SciFact NLI Fine-Tuned Model

This directory contains a cross-encoder fine-tuned on SciFact for NLI.

## Label Mapping
{
  "CONTRADICTION": 0,
  "NO_ENTAILMENT": 1,
  "ENTAILMENT": 2
}

## Notes
- Use `HDRP_NLI_MODEL_NAME` to point the Critic to this model.
- Export to ONNX with `HDRP/tools/eval/export_nli_onnx.py` if needed.