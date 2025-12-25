import unittest
from HDRP.services.critic.service import CriticService
from HDRP.services.shared.claims import AtomicClaim

class TestCriticService(unittest.TestCase):
    def setUp(self):
        self.critic = CriticService()

    def test_verify_valid_claim(self):
        claim = AtomicClaim(
            statement="Quantum computing uses qubits for calculations.",
            support_text="Quantum computing uses qubits for calculations.",
            source_url="https://example.com/sky",
            confidence=1.0
        )
        # Task should be relevant
        results = self.critic.verify([claim], task="explain quantum computing")
        self.assertTrue(results[0].is_valid)
        self.assertEqual(results[0].reason, "Verified: Grounded and concrete")

    def test_verify_invalid_claim_vague(self):
        claim = AtomicClaim(
            statement="It might be possible that quantum computers are fast.",
            support_text="Quantum computers demonstrate exponential speedup on specific algorithms.",
            source_url="https://example.com/q",
            confidence=1.0
        )
        results = self.critic.verify([claim], task="quantum stuff")
        self.assertFalse(results[0].is_valid)
        self.assertEqual(results[0].reason, "REJECTED: Statement is too vague/speculative")

    def test_verify_invalid_claim_inferred(self):
        claim = AtomicClaim(
            statement="NVIDIA revenue grew, therefore they are the market leader.",
            support_text="NVIDIA reported record revenue growth this quarter.",
            source_url="https://example.com/n",
            confidence=1.0
        )
        results = self.critic.verify([claim], task="nvidia market")
        self.assertFalse(results[0].is_valid)
        self.assertEqual(results[0].reason, "REJECTED: Detected inferred logical leap not present in source")

    def test_verify_invalid_claim_hallucinated(self):
        claim = AtomicClaim(
            statement="The CEO of Apple is actually a robot from Mars.",
            support_text="Tim Cook spoke at the product launch event today.",
            source_url="https://example.com/a",
            confidence=1.0
        )
        results = self.critic.verify([claim], task="apple ceo")
        self.assertFalse(results[0].is_valid)
        self.assertEqual(results[0].reason, "REJECTED: Low grounding - statement deviates significantly from support text")

    def test_verify_invalid_claim_missing_url(self):
        claim = AtomicClaim(
            statement="The sky is blue.",
            support_text="The sky is blue because of Rayleigh scattering.",
            source_url=None,
            confidence=1.0
        )
        results = self.critic.verify([claim], task="sky color")
        self.assertFalse(results[0].is_valid)
        self.assertEqual(results[0].reason, "REJECTED: Missing source URL")

    def test_verify_invalid_claim_short_support(self):
        claim = AtomicClaim(
            statement="The sky is blue and very beautiful.",
            support_text="Sky.",
            source_url="https://example.com/sky",
            confidence=1.0
        )
        results = self.critic.verify([claim], task="sky color")
        self.assertFalse(results[0].is_valid)
        self.assertEqual(results[0].reason, "REJECTED: Low grounding - statement deviates significantly from support text")

    def test_verify_invalid_claim_not_verbatim(self):
        claim = AtomicClaim(
            statement="Quantum computing uses qubits for all its calculations.",
            support_text="Quantum computing uses qubits for calculations, which are fundamental units.",
            source_url="https://example.com/fast",
            confidence=1.0
        )
        results = self.critic.verify([claim], task="quantum computing")
        self.assertFalse(results[0].is_valid)
        self.assertEqual(results[0].reason, "REJECTED: Claim statement not found verbatim in source text")

    def test_verify_invalid_claim_irrelevant(self):
        claim = AtomicClaim(
            statement="Bananas are rich in potassium and vitamins.",
            support_text="Bananas are rich in potassium and vitamins.",
            source_url="https://example.com/fruit",
            confidence=1.0
        )
        # Task is about quantum computing, claim is about bananas
        results = self.critic.verify([claim], task="research quantum computing")
        self.assertFalse(results[0].is_valid)
        # We expect a rejection message about relevance.
        # Note: 'research' is a stop word, so task tokens: 'quantum', 'computing'
        # Claim tokens: 'bananas', 'rich', 'potassium', 'vitamins'
        # Intersection: empty.
        self.assertIn("REJECTED: Claim not relevant to task", results[0].reason)

    def test_verify_invalid_claim_new_inference_indicator(self):
        claim = AtomicClaim(
            statement="The test failed because of a bug.",
            support_text="The test failed. A bug was found later.",
            source_url="https://example.com/test",
            confidence=1.0
        )
        # "because" is now an indicator. It is in statement but not in support text.
        results = self.critic.verify([claim], task="test failure")
        self.assertFalse(results[0].is_valid)
        self.assertEqual(results[0].reason, "REJECTED: Detected inferred logical leap not present in source")

    def test_verify_invalid_claim_weak_grounding_strict(self):
        # This claim has some overlap ("The", "sky", "is") but the meaning is different.
        # Current threshold is 0.4.
        # Statement words: 6. Overlap: "The", "sky", "is" -> 3/6 = 0.5. Passes current check.
        # Desired: should fail with stricter check (e.g. 0.7 or stop word filtering).
        claim = AtomicClaim(
            statement="The sky is green and red.",
            support_text="The sky is blue today.",
            source_url="https://example.com/sky",
            confidence=1.0
        )
        # We expect this to fail with the improved logic
        results = self.critic.verify([claim], task="sky color")
        self.assertFalse(results[0].is_valid)
        self.assertEqual(results[0].reason, "REJECTED: Low grounding - statement deviates significantly from support text")

if __name__ == "__main__":
    unittest.main()
