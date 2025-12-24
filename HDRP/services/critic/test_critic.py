import unittest
from HDRP.services.critic.service import CriticService
from HDRP.services.shared.claims import AtomicClaim

class TestCriticService(unittest.TestCase):
    def setUp(self):
        self.critic = CriticService()

    def test_verify_valid_claim(self):
        claim = AtomicClaim(
            statement="The sky is blue.",
            support_text="The sky is blue because of Rayleigh scattering.",
            source_url="https://example.com/sky",
            confidence=1.0
        )
        results = self.critic.verify([claim])
        self.assertTrue(results[0][1])
        self.assertEqual(results[0][2], "Verified: Source and support text present")

    def test_verify_invalid_claim_missing_url(self):
        claim = AtomicClaim(
            statement="The sky is blue.",
            support_text="The sky is blue because of Rayleigh scattering.",
            source_url=None,
            confidence=1.0
        )
        results = self.critic.verify([claim])
        self.assertFalse(results[0][1])
        self.assertEqual(results[0][2], "Missing source URL")

    def test_verify_invalid_claim_short_support(self):
        claim = AtomicClaim(
            statement="The sky is blue.",
            support_text="Too short",
            source_url="https://example.com/sky",
            confidence=1.0
        )
        results = self.critic.verify([claim])
        self.assertFalse(results[0][1])
        self.assertEqual(results[0][2], "Support text too short to be credible")

if __name__ == "__main__":
    unittest.main()
