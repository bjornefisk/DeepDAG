"""NLI inference backends for configurable high-performance execution."""

from __future__ import annotations

from typing import List, Tuple, Optional

import numpy as np


def _resolve_torch_device(device: Optional[str]) -> str:
    if device is None or device == "" or device == "auto":
        try:
            import torch
        except Exception:
            return "cpu"
        return "cuda" if torch.cuda.is_available() else "cpu"
    return device


class TorchCrossEncoderBackend:
    """PyTorch backend using sentence-transformers CrossEncoder."""

    def __init__(
        self,
        model_name: str,
        device: Optional[str],
        batch_size: int,
        max_length: int,
    ) -> None:
        from sentence_transformers import CrossEncoder

        resolved_device = _resolve_torch_device(device)
        self.model = CrossEncoder(
            model_name,
            device=resolved_device,
            max_length=max_length,
        )
        self.batch_size = batch_size

    def predict_logits(self, pairs: List[Tuple[str, str]]) -> np.ndarray:
        logits = self.model.predict(
            pairs,
            convert_to_numpy=True,
            batch_size=self.batch_size,
        )
        return np.asarray(logits)


class OnnxRuntimeBackend:
    """ONNX Runtime backend for CPU/GPU inference."""

    def __init__(
        self,
        model_name: str,
        onnx_model_path: str,
        providers: List[str],
        batch_size: int,
        max_length: int,
        tokenizer_name: Optional[str] = None,
    ) -> None:
        if not onnx_model_path:
            raise ValueError("onnx_model_path is required for onnxruntime backend")

        try:
            import onnxruntime as ort
        except Exception as exc:
            raise ImportError("onnxruntime is required for ONNX backend") from exc

        from transformers import AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(
            tokenizer_name or model_name,
            use_fast=True,
        )
        available = ort.get_available_providers()
        if providers:
            selected = [p for p in providers if p in available]
        else:
            selected = available
        if not selected:
            selected = available

        self.session = ort.InferenceSession(onnx_model_path, providers=selected)
        self.input_names = [inp.name for inp in self.session.get_inputs()]
        self.batch_size = batch_size
        self.max_length = max_length

    def _prepare_inputs(self, premises: List[str], hypotheses: List[str]) -> dict:
        encoded = self.tokenizer(
            premises,
            hypotheses,
            padding=True,
            truncation=True,
            max_length=self.max_length,
            return_tensors="np",
        )
        if "token_type_ids" in self.input_names and "token_type_ids" not in encoded:
            encoded["token_type_ids"] = np.zeros_like(encoded["input_ids"])
        return {name: encoded[name] for name in self.input_names if name in encoded}

    def predict_logits(self, pairs: List[Tuple[str, str]]) -> np.ndarray:
        if not pairs:
            return np.array([], dtype=np.float32)

        all_logits = []
        for i in range(0, len(pairs), self.batch_size):
            batch_pairs = pairs[i:i + self.batch_size]
            premises = [p for p, _ in batch_pairs]
            hypotheses = [h for _, h in batch_pairs]
            inputs = self._prepare_inputs(premises, hypotheses)
            outputs = self.session.run(None, inputs)
            logits = outputs[0]
            all_logits.append(np.asarray(logits))

        return np.concatenate(all_logits, axis=0)
