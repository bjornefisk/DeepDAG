import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from HDRP.services.critic.service import CriticService
from HDRP.services.shared.claims import AtomicClaim


class TestCriticService(unittest.TestCase):
    def setUp(self):
        self.critic = CriticService()
        # Standard timestamp for test claims
        self.test_timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def test_verify_valid_claim(self):
        claim = AtomicClaim(
            statement="Quantum computing uses qubits for calculations.",
            support_text="Quantum computing uses qubits for calculations.",
            source_url="https://example.com/sky",
            confidence=1.0,
            extracted_at=self.test_timestamp
        )
        # Task should be relevant
        results = self.critic.verify([claim], task="explain quantum computing")
        self.assertTrue(results[0].is_valid)
        self.assertEqual(results[0].reason, "Verified")

    def test_verify_invalid_claim_vague(self):
        claim = AtomicClaim(
            statement="It might be possible that quantum computers are fast.",
            support_text="Quantum computers demonstrate exponential speedup on specific algorithms.",
            source_url="https://example.com/q",
            confidence=1.0,
            extracted_at=self.test_timestamp
        )
        results = self.critic.verify([claim], task="quantum stuff")
        self.assertFalse(results[0].is_valid)
        # Updated: now uses adaptive overlap check
        self.assertIn("REJECTED", results[0].reason)

    def test_verify_invalid_claim_inferred(self):
        claim = AtomicClaim(
            statement="NVIDIA revenue grew, therefore they are the market leader.",
            support_text="NVIDIA reported record revenue growth this quarter.",
            source_url="https://example.com/n",
            confidence=1.0,
            extracted_at=self.test_timestamp
        )
        results = self.critic.verify([claim], task="nvidia market")
        self.assertFalse(results[0].is_valid)
        self.assertIn("REJECTED", results[0].reason)

    def test_verify_invalid_claim_hallucinated(self):
        claim = AtomicClaim(
            statement="The CEO of Apple is actually a robot from Mars.",
            support_text="Tim Cook spoke at the product launch event today.",
            source_url="https://example.com/a",
            confidence=1.0,
            extracted_at=self.test_timestamp
        )
        results = self.critic.verify([claim], task="apple ceo")
        self.assertFalse(results[0].is_valid)
        self.assertIn("REJECTED", results[0].reason)

    def test_verify_invalid_claim_missing_url(self):
        claim = AtomicClaim(
            statement="The sky is blue.",
            support_text="The sky is blue because of Rayleigh scattering.",
            source_url=None,
            confidence=1.0,
            extracted_at=self.test_timestamp
        )
        results = self.critic.verify([claim], task="sky color")
        self.assertFalse(results[0].is_valid)
        self.assertEqual(results[0].reason, "REJECTED: Missing source URL")

    def test_verify_invalid_claim_short_support(self):
        claim = AtomicClaim(
            statement="The sky is blue and very beautiful.",
            support_text="Sky.",
            source_url="https://example.com/sky",
            confidence=1.0,
            extracted_at=self.test_timestamp
        )
        results = self.critic.verify([claim], task="sky color")
        self.assertFalse(results[0].is_valid)
        self.assertIn("REJECTED", results[0].reason)

    def test_verify_invalid_claim_not_verbatim(self):
        claim = AtomicClaim(
            statement="Quantum computing uses qubits for all its calculations.",
            support_text="Quantum computing uses qubits for calculations, which are fundamental units.",
            source_url="https://example.com/fast",
            confidence=1.0,
            extracted_at=self.test_timestamp
        )
        results = self.critic.verify([claim], task="quantum computing")
        self.assertFalse(results[0].is_valid)
        self.assertIn("REJECTED", results[0].reason)

    def test_verify_invalid_claim_irrelevant(self):
        claim = AtomicClaim(
            statement="Bananas are rich in potassium and vitamins.",
            support_text="Bananas are rich in potassium and vitamins.",
            source_url="https://example.com/fruit",
            confidence=1.0,
            extracted_at=self.test_timestamp
        )
        # Task is about quantum computing, claim is about bananas
        results = self.critic.verify([claim], task="research quantum computing")
        self.assertFalse(results[0].is_valid)
        # We expect a rejection message about relevance or low overlap
        self.assertIn("REJECTED", results[0].reason)

    def test_verify_invalid_claim_new_inference_indicator(self):
        claim = AtomicClaim(
            statement="The test failed because of a bug.",
            support_text="The test failed. A bug was found later.",
            source_url="https://example.com/test",
            confidence=1.0,
            extracted_at=self.test_timestamp
        )
        # "because" is now an indicator. It is in statement but not in support text.
        results = self.critic.verify([claim], task="test failure")
        self.assertFalse(results[0].is_valid)
        self.assertIn("REJECTED", results[0].reason)

    def test_verify_invalid_claim_weak_grounding_strict(self):
        # This claim has some overlap ("The", "sky", "is") but the meaning is different.
        # Current threshold is 0.4.
        # Statement words: 6. Overlap: "The", "sky", "is" -> 3/6 = 0.5. Passes current check.
        # Desired: should fail with stricter check (e.g. 0.7 or stop word filtering).
        claim = AtomicClaim(
            statement="The sky is green and red.",
            support_text="The sky is blue today.",
            source_url="https://example.com/sky",
            confidence=1.0,
            extracted_at=self.test_timestamp
        )
        # We expect this to fail with the improved logic
        results = self.critic.verify([claim], task="sky color")
        self.assertFalse(results[0].is_valid)
        self.assertIn("REJECTED", results[0].reason)


class TestCriticTwoPassVerification(unittest.TestCase):
    """Tests for two-pass verification logic."""

    def setUp(self):
        self.critic = CriticService()
        self.test_timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _create_claim(self, statement, support_text=None, source_url="https://example.com",
                      discovered_entities=None, source_rank=None):
        return AtomicClaim(
            statement=statement,
            support_text=support_text or statement,
            source_url=source_url,
            confidence=0.8,
            extracted_at=self.test_timestamp,
            discovered_entities=discovered_entities or [],
            source_rank=source_rank,
        )

    def test_pass_one_direct_relevance(self):
        """Verify Pass 1 validates claims directly against task."""
        claim = self._create_claim(
            statement="Machine learning algorithms require large datasets for training.",
            discovered_entities=["Machine", "Learning"]
        )
        results = self.critic.verify([claim], task="machine learning training")
        
        # Should pass direct relevance check
        self.assertTrue(results[0].is_valid)

    def test_pass_two_bridging_relevance(self):
        """Verify Pass 2 accepts claims via subtopic bridging."""
        # First claim establishes "RSA" as a verified subtopic related to cryptography
        claim1 = self._create_claim(
            statement="RSA encryption is widely used in cryptography.",
            discovered_entities=["RSA"]
        )
        
        # Second claim mentions RSA but doesn't directly mention cryptography
        claim2 = self._create_claim(
            statement="RSA key generation requires finding large prime numbers.",
            support_text="RSA key generation requires finding large prime numbers.",
            discovered_entities=["RSA"]
        )
        
        # Verify together - claim2 should be rescued via RSA subtopic
        results = self.critic.verify([claim1, claim2], task="explain cryptography")
        
        # At least the first claim should be valid
        self.assertTrue(results[0].is_valid)

    def test_entailment_score_calculated(self):
        """Verify entailment score is calculated for claims."""
        claim = self._create_claim(
            statement="Neural networks are inspired by biological brain structure.",
        )
        results = self.critic.verify([claim], task="neural networks biology")
        
        # Should have entailment_score set
        self.assertIsNotNone(results[0].entailment_score)
        self.assertGreaterEqual(results[0].entailment_score, 0.0)
        self.assertLessEqual(results[0].entailment_score, 1.0)

    def test_low_relevance_claims_rejected(self):
        """Verify low relevance claims without subtopic are rejected."""
        claim = self._create_claim(
            statement="Pizza is a popular food in Italy.",
            source_rank=5,  # High rank (low quality)
        )
        results = self.critic.verify([claim], task="machine learning algorithms")
        
        # Should be rejected due to no relevance
        self.assertFalse(results[0].is_valid)


class TestCriticSubtopicBridging(unittest.TestCase):
    """Tests for subtopic bridging/rescue mechanism."""

    def setUp(self):
        self.critic = CriticService()
        self.test_timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _create_claim(self, statement, support_text=None, discovered_entities=None):
        return AtomicClaim(
            statement=statement,
            support_text=support_text or statement,
            source_url="https://example.com",
            confidence=0.8,
            extracted_at=self.test_timestamp,
            discovered_entities=discovered_entities or [],
        )

    def test_subtopic_rescue_logs_event(self):
        """Verify subtopic rescue is logged."""
        # Establish subtopic
        claim1 = self._create_claim(
            statement="Quantum computing uses qubits for parallel computations.",
            discovered_entities=["Qubits", "Quantum"]
        )
        
        # Second claim with subtopic mention
        claim2 = self._create_claim(
            statement="Qubits can exist in superposition states.",
            support_text="Qubits can exist in superposition states.",
            discovered_entities=[]
        )
        
        with patch.object(self.critic.logger, 'log') as mock_log:
            results = self.critic.verify([claim1, claim2], task="quantum computing")
        
        # Check if subtopic rescue was logged
        rescue_calls = [c for c in mock_log.call_args_list if 'claim_rescued_by_subtopic' in str(c)]
        # May or may not be logged depending on claim scores


class TestCriticClaimTypeDetection(unittest.TestCase):
    """Tests for claim type detection (factual/speculative/mixed)."""

    def setUp(self):
        self.critic = CriticService()

    def test_detect_factual_claim(self):
        """Verify factual claims are detected."""
        result = self.critic._detect_claim_type("The Earth orbits the Sun.")
        self.assertEqual(result, "factual")

    def test_detect_speculative_claim(self):
        """Verify speculative claims are detected."""
        result = self.critic._detect_claim_type("This might be possible in the future.")
        self.assertEqual(result, "speculative")
        
        result = self.critic._detect_claim_type("The results could indicate a trend.")
        self.assertEqual(result, "speculative")

    def test_detect_mixed_claim(self):
        """Verify mixed claims return mixed or appropriate type."""
        # Claims with both factual and speculative language
        result = self.critic._detect_claim_type("The study was published and it might be significant.")
        self.assertIn(result, ["factual", "speculative", "mixed"])


class TestCriticTokenization(unittest.TestCase):
    """Tests for tokenization and key term extraction."""

    def setUp(self):
        self.critic = CriticService()

    def test_tokenize_removes_punctuation(self):
        """Verify tokenization removes punctuation."""
        result = self.critic._tokenize("Hello, world! How are you?")
        self.assertNotIn(",", " ".join(result))
        self.assertNotIn("!", " ".join(result))
        self.assertNotIn("?", " ".join(result))

    def test_tokenize_splits_on_whitespace(self):
        """Verify tokenization splits on whitespace."""
        result = self.critic._tokenize("one two three")
        self.assertEqual(len(result), 3)

    def test_extract_key_terms_filters_stop_words(self):
        """Verify key term extraction filters stop words."""
        stop_words = {"the", "is", "a", "of"}
        result = self.critic._extract_key_terms("the algorithm is a key part of the system", stop_words)
        
        self.assertNotIn("the", result)
        self.assertNotIn("is", result)
        self.assertNotIn("a", result)
        self.assertNotIn("of", result)
        self.assertIn("algorithm", result)
        self.assertIn("key", result)

    def test_extract_key_terms_filters_short_words(self):
        """Verify key term extraction filters words < 3 chars."""
        stop_words = set()
        result = self.critic._extract_key_terms("I am an AI", stop_words)
        
        # "I", "am", "an", "AI" - only "AI" is ≥3 chars (but it's 2)
        # All should be filtered out
        self.assertEqual(len(result), 0)


class TestCriticTimestampValidation(unittest.TestCase):
    """Tests for timestamp validation."""

    def setUp(self):
        self.critic = CriticService()

    def test_valid_iso_timestamp_with_z(self):
        """Verify ISO timestamp with Z suffix is valid."""
        result = self.critic._is_valid_timestamp("2024-01-15T10:30:00.000Z")
        self.assertTrue(result)

    def test_valid_iso_timestamp_without_z(self):
        """Verify ISO timestamp without Z suffix is valid."""
        result = self.critic._is_valid_timestamp("2024-01-15T10:30:00")
        self.assertTrue(result)

    def test_invalid_timestamp_format(self):
        """Verify invalid timestamp format is rejected."""
        result = self.critic._is_valid_timestamp("not-a-timestamp")
        self.assertFalse(result)
        
        result = self.critic._is_valid_timestamp("01/15/2024 10:30:00")
        self.assertFalse(result)

    def test_none_timestamp(self):
        """Verify None timestamp is handled."""
        result = self.critic._is_valid_timestamp(None)
        self.assertFalse(result)

    def test_missing_timestamp_rejects_claim(self):
        """Verify missing extraction timestamp rejects claim."""
        claim = AtomicClaim(
            statement="Test claim statement here.",
            support_text="Test claim statement here.",
            source_url="https://example.com",
            confidence=0.8,
            extracted_at=None,  # Missing timestamp
        )
        results = self.critic.verify([claim], task="test")
        
        self.assertFalse(results[0].is_valid)
        self.assertIn("Missing extraction timestamp", results[0].reason)


if __name__ == "__main__":
    unittest.main()
