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
        results = self.critic.verify([claim])
        self.assertTrue(results[0][1])
        self.assertEqual(results[0][2], "Verified: Grounded and concrete")

    def test_verify_invalid_claim_vague(self):
        claim = AtomicClaim(
            statement="It might be possible that quantum computers are fast.",
            support_text="Quantum computers demonstrate exponential speedup on specific algorithms.",
            source_url="https://example.com/q",
            confidence=1.0
        )
        results = self.critic.verify([claim])
        self.assertFalse(results[0][1])
        self.assertEqual(results[0][2], "REJECTED: Statement is too vague/speculative")

    def test_verify_invalid_claim_inferred(self):
        claim = AtomicClaim(
            statement="NVIDIA revenue grew, therefore they are the market leader.",
            support_text="NVIDIA reported record revenue growth this quarter.",
            source_url="https://example.com/n",
            confidence=1.0
        )
        results = self.critic.verify([claim])
        self.assertFalse(results[0][1])
        self.assertEqual(results[0][2], "REJECTED: Detected inferred logical leap not present in source")

    def test_verify_invalid_claim_hallucinated(self):
        claim = AtomicClaim(
            statement="The CEO of Apple is actually a robot from Mars.",
            support_text="Tim Cook spoke at the product launch event today.",
            source_url="https://example.com/a",
            confidence=1.0
        )
        results = self.critic.verify([claim])
        self.assertFalse(results[0][1])
        self.assertEqual(results[0][2], "REJECTED: Low grounding - statement deviates significantly from support text")

    def test_verify_invalid_claim_missing_url(self):
        claim = AtomicClaim(
            statement="The sky is blue.",
            support_text="The sky is blue because of Rayleigh scattering.",
            source_url=None,
            confidence=1.0
        )
        results = self.critic.verify([claim])
        self.assertFalse(results[0][1])
        self.assertEqual(results[0][2], "REJECTED: Missing source URL")

    def test_verify_invalid_claim_short_support(self):
        claim = AtomicClaim(
            statement="The sky is blue and very beautiful.",
            support_text="Sky.",
            source_url="https://example.com/sky",
            confidence=1.0
        )
        results = self.critic.verify([claim])
        self.assertFalse(results[0][1])
        self.assertEqual(results[0][2], "REJECTED: Low grounding - statement deviates significantly from support text")

if __name__ == "__main__":
    unittest.main()
