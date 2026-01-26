"""
NLI-based Claim Verification Module

Uses cross-encoder for Natural Language Inference to compute entailment scores
between support text (premise) and claim statements (hypothesis).

This module provides:
- True NLI scoring using cross-encoder models (detects contradiction, negation, entailment)
- Prediction caching for performance optimization
- Configurable threshold tuning for precision/recall tradeoff
- Batch processing support
"""

from typing import List, Tuple, Dict, Optional
import hashlib
import numpy as np
from HDRP.services.shared.settings import get_settings


class NLIVerifier:
    """Natural Language Inference verifier for claim verification.
    
    Computes entailment score P(premise → hypothesis) where:
    - premise = support_text (source evidence)
    - hypothesis = statement (claim to verify)
    
    Uses cross-encoder models that process both texts together to predict
    contradiction/neutral/entailment relationship.
    
    Higher scores indicate stronger semantic entailment.
    """
    
    def __init__(
        self, 
        model_name: Optional[str] = None,
        cache_size: int = 10000,
        device: Optional[str] = None,
        backend: Optional[str] = None,
        batch_size: Optional[int] = None,
        max_length: Optional[int] = None,
        onnx_model_path: Optional[str] = None,
        onnx_providers: Optional[List[str]] = None,
        int8: Optional[bool] = None,
        chunking_enabled: Optional[bool] = None,
        chunk_tokens: Optional[int] = None,
        overlap_tokens: Optional[int] = None,
        chunk_aggregation: Optional[str] = None,
    ):
        """Initialize NLI verifier with specified cross-encoder model.
        
        Args:
            model_name: Cross-encoder model name
                       Default: cross-encoder/nli-deberta-v3-base (400MB, accurate NLI)
                       Alternative: microsoft/deberta-v3-base (fine-tuned for NLI)
            cache_size: Maximum number of cached predictions
            device: Device to run model on ('cuda', 'cpu', or None for auto)
        """
        settings = get_settings()
        nli_settings = settings.nli

        self.model_name = model_name or nli_settings.model_name
        self.cache_size = cache_size
        self._prediction_cache: Dict[str, float] = {}
        
        self.backend = (backend or nli_settings.backend).lower()
        self.device = device or nli_settings.device
        self.batch_size = batch_size or nli_settings.batch_size
        self.max_length = max_length or nli_settings.max_length
        self.onnx_model_path = onnx_model_path or nli_settings.onnx_model_path
        self.onnx_providers = onnx_providers or nli_settings.onnx_providers
        self.int8 = nli_settings.int8 if int8 is None else int8
        self.chunking_enabled = (
            nli_settings.chunking.enabled
            if chunking_enabled is None
            else chunking_enabled
        )
        self.chunk_tokens = chunk_tokens or nli_settings.chunking.chunk_tokens
        self.overlap_tokens = overlap_tokens or nli_settings.chunking.overlap_tokens
        self.chunk_aggregation = chunk_aggregation or nli_settings.chunking.aggregation

        # Load backend (lazy initialization on first use)
        self._backend = None
        self._label_index_map: Optional[Dict[str, int]] = None
        
        # Statistics tracking
        self.cache_hits = 0
        self.cache_misses = 0
    
    def _ensure_model_loaded(self) -> None:
        """Lazy load the model on first use."""
        if self._backend is None:
            if self.backend == "onnxruntime":
                from HDRP.services.critic.nli_backends import OnnxRuntimeBackend

                self._backend = OnnxRuntimeBackend(
                    model_name=self.model_name,
                    onnx_model_path=self.onnx_model_path,
                    providers=self.onnx_providers,
                    batch_size=self.batch_size,
                    max_length=self.max_length,
                )
            elif self.backend == "torch":
                from HDRP.services.critic.nli_backends import TorchCrossEncoderBackend

                self._backend = TorchCrossEncoderBackend(
                    model_name=self.model_name,
                    device=self.device,
                    batch_size=self.batch_size,
                    max_length=self.max_length,
                )
            else:
                raise ValueError(f"Unsupported NLI backend: {self.backend}")

    def _normalize_label(self, label: str) -> str:
        normalized = label.lower().strip()
        if "contradiction" in normalized or "contradict" in normalized:
            return "contradiction"
        if "entailment" in normalized or "entails" in normalized or "entail" in normalized:
            return "entailment"
        if "neutral" in normalized:
            return "neutral"
        return normalized

    def _get_label_index_map(self) -> Dict[str, int]:
        """Resolve label indices for contradiction/neutral/entailment."""
        if self._label_index_map is not None:
            return self._label_index_map

        default_map = {"contradiction": 0, "neutral": 1, "entailment": 2}
        id2label = None

        try:
            self._ensure_model_loaded()
            model = getattr(self._backend, "model", None)
            config = getattr(model, "config", None) if model is not None else None
            id2label = getattr(config, "id2label", None)
        except Exception:
            id2label = None

        if id2label is None:
            try:
                from transformers import AutoConfig

                config = AutoConfig.from_pretrained(self.model_name)
                id2label = getattr(config, "id2label", None)
            except Exception:
                id2label = None

        label_map = {}
        if isinstance(id2label, dict):
            for idx, label in id2label.items():
                normalized = self._normalize_label(str(label))
                if normalized in ("contradiction", "neutral", "entailment"):
                    label_map[normalized] = int(idx)

        if set(label_map.keys()) != set(default_map.keys()):
            self._label_index_map = default_map
            return default_map

        self._label_index_map = label_map
        return label_map

    def _get_tokenizer(self):
        self._ensure_model_loaded()
        tokenizer = getattr(self._backend, "tokenizer", None)
        if tokenizer is None:
            from transformers import AutoTokenizer

            tokenizer = AutoTokenizer.from_pretrained(self.model_name, use_fast=True)
        return tokenizer

    def _chunk_premise(self, premise: str, hypothesis: str) -> List[str]:
        if not self.chunking_enabled:
            return [premise]

        tokenizer = self._get_tokenizer()
        premise_tokens = tokenizer.encode(premise, add_special_tokens=False)
        hypothesis_tokens = tokenizer.encode(hypothesis, add_special_tokens=False)

        available_premise_tokens = max(self.max_length - len(hypothesis_tokens) - 3, 1)
        chunk_size = max(1, min(self.chunk_tokens, available_premise_tokens))
        if len(premise_tokens) <= chunk_size:
            return [premise]

        overlap = min(max(self.overlap_tokens, 0), chunk_size - 1)
        step = max(1, chunk_size - overlap)
        chunks = []
        for start in range(0, len(premise_tokens), step):
            window = premise_tokens[start:start + chunk_size]
            if not window:
                break
            chunk_text = tokenizer.decode(
                window, skip_special_tokens=True, clean_up_tokenization_spaces=True
            )
            chunks.append(chunk_text)
            if start + chunk_size >= len(premise_tokens):
                break

        return chunks or [premise]

    def _aggregate_scores(self, scores: List[float]) -> float:
        if not scores:
            return 0.0
        if self.chunk_aggregation == "mean":
            return float(np.mean(scores))
        if self.chunk_aggregation == "median":
            return float(np.median(scores))
        return float(np.max(scores))

    def _score_pairs_probabilities(
        self, pairs: List[Tuple[str, str]]
    ) -> List[Dict[str, float]]:
        logits = self._backend.predict_logits(pairs)
        logits = np.asarray(logits)
        if logits.ndim == 1:
            logits = np.expand_dims(logits, axis=0)

        label_map = self._get_label_index_map()
        scores = []
        for row in logits:
            exp_logits = np.exp(row - np.max(row))
            probabilities = exp_logits / np.sum(exp_logits)
            contradiction_score = float(np.clip(probabilities[label_map["contradiction"]], 0.0, 1.0))
            neutral_score = float(np.clip(probabilities[label_map["neutral"]], 0.0, 1.0))
            entailment_score = float(np.clip(probabilities[label_map["entailment"]], 0.0, 1.0))
            scores.append(
                {
                    "contradiction": contradiction_score,
                    "neutral": neutral_score,
                    "entailment": entailment_score,
                }
            )
        return scores

    def _score_pairs(self, pairs: List[Tuple[str, str]]) -> List[float]:
        probabilities = self._score_pairs_probabilities(pairs)
        return [entry["entailment"] for entry in probabilities]

    def _compute_entailment_uncached(self, premise: str, hypothesis: str) -> float:
        self._ensure_model_loaded()
        chunks = self._chunk_premise(premise, hypothesis)
        if len(chunks) == 1:
            scores = self._score_pairs([(premise, hypothesis)])
            return scores[0]

        pairs = [(chunk, hypothesis) for chunk in chunks]
        scores = self._score_pairs(pairs)
        return self._aggregate_scores(scores)
    
    def _get_pair_hash(self, premise: str, hypothesis: str) -> str:
        """Generate hash for (premise, hypothesis) pair cache key."""
        combined = f"{premise}|||{hypothesis}"
        return hashlib.md5(combined.encode('utf-8')).hexdigest()
    
    def _get_cached_prediction(self, premise: str, hypothesis: str) -> Optional[float]:
        """Get cached prediction if available.
        
        Args:
            premise: Support text
            hypothesis: Claim statement
            
        Returns:
            Cached entailment score or None if not cached
        """
        pair_hash = self._get_pair_hash(premise, hypothesis)
        
        if pair_hash in self._prediction_cache:
            self.cache_hits += 1
            return self._prediction_cache[pair_hash]
        
        self.cache_misses += 1
        return None
    
    def _cache_prediction(self, premise: str, hypothesis: str, score: float) -> None:
        """Store prediction in cache.
        
        Args:
            premise: Support text
            hypothesis: Claim statement
            score: Entailment score to cache
        """
        # Only cache if under size limit
        if len(self._prediction_cache) < self.cache_size:
            pair_hash = self._get_pair_hash(premise, hypothesis)
            self._prediction_cache[pair_hash] = score
    
    def compute_entailment(
        self, 
        premise: str, 
        hypothesis: str
    ) -> float:
        """Compute entailment score between premise and hypothesis.
        
        Args:
            premise: Support text (source evidence)
            hypothesis: Claim statement to verify
            
        Returns:
            Entailment score in [0, 1] range
            Higher scores indicate stronger entailment
            
        Note:
            Cross-encoder outputs logits for [contradiction, neutral, entailment].
            We convert to softmax probabilities and return the entailment probability
            using model-provided label mapping when available.
        """
        # Check cache first
        cached_score = self._get_cached_prediction(premise, hypothesis)
        if cached_score is not None:
            return cached_score
        
        entailment_score = self._compute_entailment_uncached(premise, hypothesis)
        
        # Cache the result
        self._cache_prediction(premise, hypothesis, entailment_score)
        
        return entailment_score

    def compute_relation(self, premise: str, hypothesis: str) -> Dict[str, float]:
        """Compute full NLI relation probabilities for a pair."""
        self._ensure_model_loaded()
        chunks = self._chunk_premise(premise, hypothesis)
        if len(chunks) == 1:
            scores = self._score_pairs_probabilities([(premise, hypothesis)])
            return scores[0]

        pairs = [(chunk, hypothesis) for chunk in chunks]
        scores = self._score_pairs_probabilities(pairs)
        entailment = self._aggregate_scores([s["entailment"] for s in scores])
        contradiction = self._aggregate_scores([s["contradiction"] for s in scores])
        neutral = self._aggregate_scores([s["neutral"] for s in scores])
        return {
            "contradiction": float(contradiction),
            "neutral": float(neutral),
            "entailment": float(entailment),
        }
    
    def compute_entailment_batch(
        self, 
        premise_hypothesis_pairs: List[Tuple[str, str]]
    ) -> List[float]:
        """Compute entailment scores for multiple pairs in batch.
        
        More efficient than calling compute_entailment repeatedly.
        
        Args:
            premise_hypothesis_pairs: List of (premise, hypothesis) tuples
            
        Returns:
            List of entailment scores
        """
        if not premise_hypothesis_pairs:
            return []
        
        self._ensure_model_loaded()
        
        # Separate cached vs uncached pairs
        scores = [None] * len(premise_hypothesis_pairs)
        uncached_indices = []
        uncached_pairs = []
        
        for i, (premise, hypothesis) in enumerate(premise_hypothesis_pairs):
            cached_score = self._get_cached_prediction(premise, hypothesis)
            if cached_score is not None:
                scores[i] = cached_score
            else:
                uncached_indices.append(i)
                uncached_pairs.append((premise, hypothesis))
        
        # Batch predict uncached pairs
        if uncached_pairs:
            simple_pairs = []
            simple_map = []
            chunked_pairs = []
            chunked_map = []

            for idx, (premise, hypothesis) in zip(uncached_indices, uncached_pairs):
                chunks = self._chunk_premise(premise, hypothesis)
                if len(chunks) == 1:
                    simple_pairs.append((premise, hypothesis))
                    simple_map.append(idx)
                else:
                    chunked_pairs.append((premise, hypothesis))
                    chunked_map.append(idx)

            if simple_pairs:
                simple_scores = self._score_pairs(simple_pairs)
                for idx, score in zip(simple_map, simple_scores):
                    scores[idx] = score
                    premise, hypothesis = premise_hypothesis_pairs[idx]
                    self._cache_prediction(premise, hypothesis, score)

            for idx in chunked_map:
                premise, hypothesis = premise_hypothesis_pairs[idx]
                score = self._compute_entailment_uncached(premise, hypothesis)
                scores[idx] = score
                self._cache_prediction(premise, hypothesis, score)
        
        return scores

    def compute_relation_batch(
        self,
        premise_hypothesis_pairs: List[Tuple[str, str]]
    ) -> List[Dict[str, float]]:
        """Compute full NLI relation probabilities for multiple pairs in batch."""
        if not premise_hypothesis_pairs:
            return []

        self._ensure_model_loaded()
        results = [None] * len(premise_hypothesis_pairs)
        simple_pairs = []
        simple_map = []
        chunked_map = []

        for idx, (premise, hypothesis) in enumerate(premise_hypothesis_pairs):
            chunks = self._chunk_premise(premise, hypothesis)
            if len(chunks) == 1:
                simple_pairs.append((premise, hypothesis))
                simple_map.append(idx)
            else:
                chunked_map.append(idx)

        if simple_pairs:
            simple_scores = self._score_pairs_probabilities(simple_pairs)
            for idx, score in zip(simple_map, simple_scores):
                results[idx] = score
                premise, hypothesis = premise_hypothesis_pairs[idx]
                self._cache_prediction(premise, hypothesis, score["entailment"])

        for idx in chunked_map:
            premise, hypothesis = premise_hypothesis_pairs[idx]
            score = self.compute_relation(premise, hypothesis)
            results[idx] = score
            self._cache_prediction(premise, hypothesis, score["entailment"])

        return results
    
    def get_cache_stats(self) -> Dict[str, any]:
        """Get cache performance statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = self.cache_hits / total_requests if total_requests > 0 else 0.0
        
        return {
            "cache_size": len(self._prediction_cache),
            "cache_max_size": self.cache_size,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": hit_rate,
            "utilization": len(self._prediction_cache) / self.cache_size
        }
    
    def clear_cache(self) -> None:
        """Clear prediction cache and reset statistics."""
        self._prediction_cache.clear()
        self.cache_hits = 0
        self.cache_misses = 0
