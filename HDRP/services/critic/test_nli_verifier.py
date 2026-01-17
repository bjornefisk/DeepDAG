"""
Unit tests for NLI-based claim verification module.

Tests cover:
- Entailment scoring for positive/negative pairs
- Embedding cache performance
- Batch processing correctness
"""

import unittest
from HDRP.services.critic.nli_verifier import NLIVerifier


class TestNLIVerifier(unittest.TestCase):
    """Tests for NLI verifier core functionality."""
    
    def setUp(self):
        """Initialize verifier for tests."""
        self.verifier = NLIVerifier()
    
    def test_entailment_positive_exact_match(self):
        """Verify high score for identical premise and hypothesis."""
        premise = "Quantum computing uses qubits for calculations."
        hypothesis = "Quantum computing uses qubits for calculations."
        
        score = self.verifier.compute_entailment(premise, hypothesis)
        
        # Identical texts should have very high similarity
        self.assertGreater(score, 0.95, 
                         f"Expected high score for identical texts, got {score:.3f}")
    
    def test_entailment_positive_paraphrase(self):
        """Verify reasonable score for paraphrased entailment."""
        premise = "Machine learning algorithms require large datasets for training."
        hypothesis = "ML models need big data to learn effectively."
        
        score = self.verifier.compute_entailment(premise, hypothesis)
        
        # Paraphrases should have moderate to high similarity
        self.assertGreater(score, 0.60, 
                         f"Expected moderate score for paraphrase, got {score:.3f}")
    
    def test_entailment_positive_subset(self):
        """Verify high score when hypothesis is subset of premise."""
        premise = "Python is a high-level, interpreted programming language with dynamic typing."
        hypothesis = "Python is a programming language."
        
        score = self.verifier.compute_entailment(premise, hypothesis)
        
        # Subset should have high similarity
        self.assertGreater(score, 0.75,
                         f"Expected high score for subset relation, got {score:.3f}")
    
    def test_entailment_negative_contradiction(self):
        """Verify low score for contradictory pairs."""
        premise = "The sky is blue during daytime."
        hypothesis = "The sky is green during daytime."
        
        score = self.verifier.compute_entailment(premise, hypothesis)
        
        # Cross-encoder should properly detect contradiction (low entailment score)
        self.assertLess(score, 0.4,
                       f"Expected low score for contradiction, got {score:.3f}")
    
    def test_entailment_negative_unrelated(self):
        """Verify low score for completely unrelated texts."""
        premise = "Quantum computing uses qubits for parallel computations."
        hypothesis = "Bananas are rich in potassium and vitamins."
        
        score = self.verifier.compute_entailment(premise, hypothesis)
        
        # Unrelated texts should have low similarity
        self.assertLess(score, 0.65,
                       f"Expected low score for unrelated texts, got {score:.3f}")
    
    def test_prediction_cache_functionality(self):
        """Verify prediction cache stores and retrieves correctly."""
        text1 = "Test sentence for caching."
        text2 = "Another test sentence."
        
        # Clear cache and stats
        self.verifier.clear_cache()
        
        # First call - cache miss
        self.verifier.compute_entailment(text1, text2)
        stats1 = self.verifier.get_cache_stats()
        self.assertEqual(stats1['cache_misses'], 1)  # Pair is new
        self.assertEqual(stats1['cache_hits'], 0)
        
        # Second call with same pair - cache hit
        self.verifier.compute_entailment(text1, text2)
        stats2 = self.verifier.get_cache_stats()
        self.assertEqual(stats2['cache_hits'], 1)  # Pair is cached
        self.assertEqual(stats2['cache_misses'], 1)  # Still only 1 miss
    
    def test_prediction_cache_hit_rate(self):
        """Verify cache achieves high hit rate with repeated queries."""
        texts = [
            "First test sentence.",
            "Second test sentence.",
            "Third test sentence."
        ]
        
        self.verifier.clear_cache()
        
        # Compute all pairs twice
        for _ in range(2):
            for i, text1 in enumerate(texts):
                for text2 in texts[i+1:]:
                    self.verifier.compute_entailment(text1, text2)
        
        stats = self.verifier.get_cache_stats()
        
        # After first round: 3 unique pairs = 3 misses
        # After second round: all pairs cached = 3 hits
        # Total calls = 2 * 3 pairs = 6 predictions
        # Expected: 3 misses + 3 hits = 50% hit rate
        self.assertGreater(stats['hit_rate'], 0.4,
                          f"Expected high cache hit rate, got {stats['hit_rate']:.2f}")
    
    def test_batch_processing_correctness(self):
        """Verify batch processing produces same results as individual calls."""
        pairs = [
            ("Quantum computing uses qubits.", "Qubits are used in quantum computing."),
            ("Python is a programming language.", "Java is a programming language."),
            ("The sky is blue.", "Bananas are yellow.")
        ]
        
        # Compute individually
        individual_scores = [
            self.verifier.compute_entailment(premise, hypothesis)
            for premise, hypothesis in pairs
        ]
        
        # Clear cache to ensure fair comparison
        self.verifier.clear_cache()
        
        # Compute in batch
        batch_scores = self.verifier.compute_entailment_batch(pairs)
        
        # Verify same results
        self.assertEqual(len(individual_scores), len(batch_scores))
        for i, (ind_score, batch_score) in enumerate(zip(individual_scores, batch_scores)):
            self.assertAlmostEqual(ind_score, batch_score, places=5,
                                 msg=f"Batch score differs at index {i}")
    
    def test_batch_processing_empty_list(self):
        """Verify batch processing handles empty input."""
        scores = self.verifier.compute_entailment_batch([])
        self.assertEqual(scores, [])
    
    def test_score_range(self):
        """Verify all scores are in valid [0, 1] range."""
        test_pairs = [
            ("Test sentence one.", "Test sentence two."),
            ("Completely different.", "Another unrelated text."),
            ("Identical text.", "Identical text."),
        ]
        
        for premise, hypothesis in test_pairs:
            score = self.verifier.compute_entailment(premise, hypothesis)
            self.assertGreaterEqual(score, 0.0,
                                   f"Score below 0: {score}")
            self.assertLessEqual(score, 1.0,
                                f"Score above 1: {score}")
    
    def test_cache_stats_structure(self):
        """Verify cache stats returns expected structure."""
        stats = self.verifier.get_cache_stats()
        
        required_keys = {
            'cache_size', 'cache_max_size', 'cache_hits', 
            'cache_misses', 'hit_rate', 'utilization'
        }
        
        self.assertEqual(set(stats.keys()), required_keys)
        self.assertIsInstance(stats['cache_size'], int)
        self.assertIsInstance(stats['cache_max_size'], int)
        self.assertIsInstance(stats['hit_rate'], float)
    
    def test_clear_cache_resets_stats(self):
        """Verify clear_cache resets statistics."""
        # Generate some cache activity
        self.verifier.compute_entailment("Test 1", "Test 2")
        self.verifier.compute_entailment("Test 1", "Test 2")
        
        # Clear cache
        self.verifier.clear_cache()
        
        stats = self.verifier.get_cache_stats()
        self.assertEqual(stats['cache_size'], 0)
        self.assertEqual(stats['cache_hits'], 0)
        self.assertEqual(stats['cache_misses'], 0)
        self.assertEqual(stats['hit_rate'], 0.0)


class TestNLIVerifierEdgeCases(unittest.TestCase):
    """Tests for edge cases and error handling."""
    
    def setUp(self):
        """Initialize verifier for tests."""
        self.verifier = NLIVerifier()
    
    def test_empty_strings(self):
        """Verify handling of empty strings."""
        score = self.verifier.compute_entailment("", "")
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)
    
    def test_very_long_text(self):
        """Verify handling of very long texts."""
        long_text = "This is a test sentence. " * 200  # Very long text
        short_text = "This is a test sentence."
        
        score = self.verifier.compute_entailment(long_text, short_text)
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)
    
    def test_special_characters(self):
        """Verify handling of special characters."""
        text1 = "Test with special chars: @#$%^&*()!"
        text2 = "Test with special chars: @#$%^&*()!"
        
        score = self.verifier.compute_entailment(text1, text2)
        self.assertGreater(score, 0.9)  # Should be very similar
    
    def test_unicode_text(self):
        """Verify handling of unicode characters."""
        text1 = "Test avec des caractères spéciaux: café, naïve, résumé"
        text2 = "Test avec des caractères spéciaux: café, naïve, résumé"
        
        score = self.verifier.compute_entailment(text1, text2)
        self.assertGreater(score, 0.9)  # Should be very similar


if __name__ == "__main__":
    unittest.main()
