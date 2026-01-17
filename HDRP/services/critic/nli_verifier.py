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
from sentence_transformers import CrossEncoder


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
        model_name: str = "cross-encoder/nli-deberta-v3-base",
        cache_size: int = 10000,
        device: Optional[str] = None
    ):
        """Initialize NLI verifier with specified cross-encoder model.
        
        Args:
            model_name: Cross-encoder model name
                       Default: cross-encoder/nli-deberta-v3-base (400MB, accurate NLI)
                       Alternative: microsoft/deberta-v3-base (fine-tuned for NLI)
            cache_size: Maximum number of cached predictions
            device: Device to run model on ('cuda', 'cpu', or None for auto)
        """
        self.model_name = model_name
        self.cache_size = cache_size
        self._prediction_cache: Dict[str, float] = {}
        
        # Load model (lazy initialization on first use)
        self._model: Optional[CrossEncoder] = None
        self._device = device
        
        # Statistics tracking
        self.cache_hits = 0
        self.cache_misses = 0
    
    def _ensure_model_loaded(self) -> None:
        """Lazy load the model on first use."""
        if self._model is None:
            self._model = CrossEncoder(self.model_name, device=self._device)
    
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
            We convert to softmax probabilities and return the entailment probability.
        """
        # Check cache first
        cached_score = self._get_cached_prediction(premise, hypothesis)
        if cached_score is not None:
            return cached_score
        
        # Ensure model is loaded
        self._ensure_model_loaded()
        
        # Predict using cross-encoder
        # Model returns logits for [contradiction, neutral, entailment]
        logits = self._model.predict([(premise, hypothesis)], convert_to_numpy=True)
        
        # Convert logits to probabilities using softmax
        if isinstance(logits, np.ndarray):
            if logits.ndim > 1:
                logits = logits[0]  # Get first (and only) prediction
        
        # Apply softmax to get probabilities
        exp_logits = np.exp(logits - np.max(logits))  # Numerical stability
        probabilities = exp_logits / np.sum(exp_logits)
        
        # Extract entailment probability (index 1)
        # Model labels: {0: 'contradiction', 1: 'entailment', 2: 'neutral'}
        entailment_score = float(probabilities[1])
        
        # Clamp to [0, 1] to avoid floating point precision issues
        entailment_score = float(np.clip(entailment_score, 0.0, 1.0))
        
        # Cache the result
        self._cache_prediction(premise, hypothesis, entailment_score)
        
        return entailment_score
    
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
            # Get logits for all pairs
            logits_batch = self._model.predict(uncached_pairs, convert_to_numpy=True)
            
            # Process each prediction
            for i, logits in enumerate(logits_batch):
                # Apply softmax to get probabilities
                exp_logits = np.exp(logits - np.max(logits))
                probabilities = exp_logits / np.sum(exp_logits)
                
                # Extract entailment probability (index 1)
                # Model labels: {0: 'contradiction', 1: 'entailment', 2: 'neutral'}
                entailment_score = float(probabilities[1])
                entailment_score = float(np.clip(entailment_score, 0.0, 1.0))
                
                # Store in results
                original_idx = uncached_indices[i]
                scores[original_idx] = entailment_score
                
                # Cache the result
                premise, hypothesis = uncached_pairs[i]
                self._cache_prediction(premise, hypothesis, entailment_score)
        
        return scores
    
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
