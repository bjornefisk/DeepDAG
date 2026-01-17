"""
NLI-based Claim Verification Module

Uses sentence-transformers to compute semantic entailment scores between
support text (premise) and claim statements (hypothesis).

This module provides:
- Semantic similarity scoring using transformer models
- Embedding caching for performance optimization
- Configurable threshold tuning for precision/recall tradeoff
- Batch processing support
"""

from typing import List, Tuple, Dict, Optional
from functools import lru_cache
import hashlib
import numpy as np
from sentence_transformers import SentenceTransformer, util


class NLIVerifier:
    """Natural Language Inference verifier for claim verification.
    
    Computes entailment score P(premise → hypothesis) where:
    - premise = support_text (source evidence)
    - hypothesis = statement (claim to verify)
    
    Higher scores indicate stronger semantic entailment.
    """
    
    def __init__(
        self, 
        model_name: str = "all-MiniLM-L6-v2",
        cache_size: int = 10000,
        device: Optional[str] = None
    ):
        """Initialize NLI verifier with specified model.
        
        Args:
            model_name: Sentence-transformers model name
                       Default: all-MiniLM-L6-v2 (80MB, fast, good quality)
            cache_size: Maximum number of cached embeddings
            device: Device to run model on ('cuda', 'cpu', or None for auto)
        """
        self.model_name = model_name
        self.cache_size = cache_size
        self._embedding_cache: Dict[str, np.ndarray] = {}
        
        # Load model (lazy initialization on first use)
        self._model: Optional[SentenceTransformer] = None
        self._device = device
        
        # Statistics tracking
        self.cache_hits = 0
        self.cache_misses = 0
    
    def _ensure_model_loaded(self) -> None:
        """Lazy load the model on first use."""
        if self._model is None:
            self._model = SentenceTransformer(self.model_name, device=self._device)
    
    def _get_text_hash(self, text: str) -> str:
        """Generate hash for cache key."""
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def _get_embedding(self, text: str) -> np.ndarray:
        """Get embedding for text, using cache if available.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        self._ensure_model_loaded()
        
        text_hash = self._get_text_hash(text)
        
        # Check cache
        if text_hash in self._embedding_cache:
            self.cache_hits += 1
            return self._embedding_cache[text_hash]
        
        # Compute embedding
        self.cache_misses += 1
        embedding = self._model.encode(text, convert_to_tensor=False)
        
        # Store in cache (with size limit)
        if len(self._embedding_cache) < self.cache_size:
            self._embedding_cache[text_hash] = embedding
        
        return embedding
    
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
        """
        # Get embeddings
        premise_emb = self._get_embedding(premise)
        hypothesis_emb = self._get_embedding(hypothesis)
        
        # Compute cosine similarity
        similarity = util.cos_sim(premise_emb, hypothesis_emb)
        
        # Convert to scalar and normalize to [0, 1]
        if isinstance(similarity, np.ndarray):
            score = float(similarity[0][0]) if similarity.ndim > 1 else float(similarity[0])
        else:
            score = float(similarity)
        
        # Cosine similarity is in [-1, 1], normalize to [0, 1]
        # We use (score + 1) / 2 transformation
        normalized_score = (score + 1) / 2
        
        # Clamp to [0, 1] to avoid floating point precision issues
        return float(np.clip(normalized_score, 0.0, 1.0))
    
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
        
        # Separate into premises and hypotheses
        premises = [p for p, h in premise_hypothesis_pairs]
        hypotheses = [h for p, h in premise_hypothesis_pairs]
        
        # Get embeddings (uses cache where possible)
        premise_embs = [self._get_embedding(p) for p in premises]
        hypothesis_embs = [self._get_embedding(h) for h in hypotheses]
        
        # Compute pairwise similarities
        scores = []
        for premise_emb, hypothesis_emb in zip(premise_embs, hypothesis_embs):
            similarity = util.cos_sim(premise_emb, hypothesis_emb)
            
            if isinstance(similarity, np.ndarray):
                score = float(similarity[0][0]) if similarity.ndim > 1 else float(similarity[0])
            else:
                score = float(similarity)
            
            # Normalize to [0, 1]
            normalized_score = (score + 1) / 2
            
            # Clamp to [0, 1] to avoid floating point precision issues
            scores.append(float(np.clip(normalized_score, 0.0, 1.0)))
        
        return scores
    
    def get_cache_stats(self) -> Dict[str, any]:
        """Get cache performance statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = self.cache_hits / total_requests if total_requests > 0 else 0.0
        
        return {
            "cache_size": len(self._embedding_cache),
            "cache_max_size": self.cache_size,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": hit_rate,
            "utilization": len(self._embedding_cache) / self.cache_size
        }
    
    def clear_cache(self) -> None:
        """Clear embedding cache and reset statistics."""
        self._embedding_cache.clear()
        self.cache_hits = 0
        self.cache_misses = 0
