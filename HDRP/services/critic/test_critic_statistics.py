import unittest
from unittest.mock import MagicMock, patch
from HDRP.services.critic.service import CriticService
from HDRP.services.shared.claims import AtomicClaim

class TestCriticStatistics(unittest.TestCase):
    def setUp(self):
        self.critic = CriticService()
        # Mock the logger to verify calls
        self.critic.logger = MagicMock()

    def test_log_rejection_missing_source(self):
        claim = AtomicClaim(
            statement="Valid statement",
            support_text="Valid statement",
            source_url=None # Missing URL
        )
        
        self.critic.verify([claim], "task")
        
        self.critic.logger.log.assert_called_with(
            "claim_rejected", 
            {
                "claim_id": claim.claim_id,
                "reason": "REJECTED: Missing source URL",
                "statement": "Valid statement"
            }
        )

    def test_log_rejection_low_grounding(self):
        claim = AtomicClaim(
            statement="The sky is very blue today indeed",
            support_text="The grass is extremely green right now", # Complete mismatch
            source_url="http://example.com"
        )
        
        self.critic.verify([claim], "The sky is very blue today indeed")
        
        # Verify call arguments contain expected reason substring
        call_args = self.critic.logger.log.call_args
        self.assertIsNotNone(call_args)
        self.assertEqual(call_args[0][0], "claim_rejected")
        self.assertIn("REJECTED: Low grounding", call_args[0][1]["reason"])

    def test_no_log_on_success(self):
        claim = AtomicClaim(
            statement="The sky is very blue today indeed",
            support_text="The sky is very blue today indeed",
            source_url="http://example.com"
        )
        
        self.critic.verify([claim], "The sky is very blue today indeed")
        
        self.critic.logger.log.assert_not_called()

if __name__ == "__main__":
    unittest.main()
