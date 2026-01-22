#!/usr/bin/env python3
"""Export and optionally quantize NLI model to ONNX for low-latency inference.

Usage:
  python HDRP/tools/eval/export_nli_onnx.py \
    --model cross-encoder/nli-deberta-v3-base \
    --output-dir artifacts/nli_onnx \
    --int8
"""

import argparse
from pathlib import Path

from transformers import AutoModelForSequenceClassification, AutoTokenizer
from transformers.onnx import FeaturesManager, export


def export_onnx(model_name: str, output_dir: Path, opset: int) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    onnx_path = output_dir / "model.onnx"

    model = AutoModelForSequenceClassification.from_pretrained(model_name)
    tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)

    feature = "sequence-classification"
    model_kind, onnx_config_class = FeaturesManager.check_supported_model_or_raise(
        model, feature=feature
    )
    onnx_config = onnx_config_class(model.config)

    export(tokenizer, model, onnx_config, opset, onnx_path)
    return onnx_path


def quantize_int8(onnx_path: Path) -> Path:
    try:
        from onnxruntime.quantization import quantize_dynamic, QuantType
    except Exception as exc:
        raise ImportError("onnxruntime is required for quantization") from exc

    int8_path = onnx_path.parent / "model.int8.onnx"
    quantize_dynamic(
        model_input=str(onnx_path),
        model_output=str(int8_path),
        weight_type=QuantType.QInt8,
    )
    return int8_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Export NLI model to ONNX")
    parser.add_argument(
        "--model",
        default="cross-encoder/nli-deberta-v3-base",
        help="Hugging Face model name",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/nli_onnx",
        help="Output directory for ONNX files",
    )
    parser.add_argument(
        "--opset",
        type=int,
        default=17,
        help="ONNX opset version",
    )
    parser.add_argument(
        "--int8",
        action="store_true",
        help="Also export an INT8-quantized ONNX model",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    onnx_path = export_onnx(args.model, output_dir, args.opset)
    print(f"Exported ONNX model: {onnx_path}")

    if args.int8:
        int8_path = quantize_int8(onnx_path)
        print(f"Exported INT8 model: {int8_path}")


if __name__ == "__main__":
    main()
