import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime
from HDRP.services.critic.service import CriticService
from HDRP.services.shared.claims import AtomicClaim

class TestCriticStatistics(unittest.TestCase):
    def setUp(self):
        self.critic = CriticService()
        # Mock the logger to verify calls
        self.critic.logger = MagicMock()
        # Standard timestamp for test claims
        self.test_timestamp = datetime.utcnow().isoformat() + "Z"

    def test_log_rejection_missing_source(self):
        claim = AtomicClaim(
            statement="Valid statement",
            support_text="Valid statement",
            source_url=None, # Missing URL
            extracted_at=self.test_timestamp
        )
        
        self.critic.verify([claim], "task")
        
        # Should be called with updated fields including source_url and source_title
        self.critic.logger.log.assert_called_with(
            "claim_rejected", 
            {
                "claim_id": claim.claim_id,
                "reason": "REJECTED: Missing source URL",
                "statement": "Valid statement",
                "source_url": None,
                "source_title": None
            }
        )

    def test_log_rejection_low_grounding(self):
        claim = AtomicClaim(
            statement="The sky is very blue today indeed",
            support_text="The grass is extremely green right now", # Complete mismatch
            source_url="http://example.com",
            extracted_at=self.test_timestamp
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
            source_url="http://example.com",
            extracted_at=self.test_timestamp
        )
        
        self.critic.verify([claim], "The sky is very blue today indeed")
        
        # Should not log anything for successful verification
        self.critic.logger.log.assert_not_called()

if __name__ == "__main__":
    unittest.main()
