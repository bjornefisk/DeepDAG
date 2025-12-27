import unittest
from HDRP.services.synthesizer.service import SynthesizerService
from HDRP.services.shared.claims import AtomicClaim, CritiqueResult

class TestVerifiedClaimsEnforcement(unittest.TestCase):
    def setUp(self):
        self.synthesizer = SynthesizerService()

    def test_synthesizer_rejects_unverified_claims(self):
        """Test that the synthesizer strictly ignores claims marked as invalid."""
        
        # 1. Create a Valid Claim
        valid_claim = AtomicClaim(
            statement="Quantum computers use qubits.",
            support_text="Quantum computers use qubits which can be 0 and 1 at the same time.",
            source_url="https://example.com/quantum",
            confidence=0.9
        )
        valid_result = CritiqueResult(claim=valid_claim, is_valid=True, reason="Verified")

        # 2. Create an Invalid Claim (Unverified)
        invalid_claim = AtomicClaim(
            statement="The earth is flat.",
            support_text="Some people say the earth is flat.",
            source_url="https://example.com/flat",
            confidence=0.1
        )
        invalid_result = CritiqueResult(claim=invalid_claim, is_valid=False, reason="REJECTED: False information")

        # 3. Pass both to synthesizer
        report = self.synthesizer.synthesize([valid_result, invalid_result])
        
        # 4. Assertions
        print("\nGenerated Report:\n", report)
        
        # The valid statement MUST be present
        self.assertIn("Quantum computers use qubits.", report)
        
        # The invalid statement MUST NOT be present
        self.assertNotIn("The earth is flat.", report)
        
        # The invalid source URL MUST NOT be present (unless it happened to be the same as valid one, which it isn't)
        self.assertNotIn("https://example.com/flat", report)

    def test_synthesizer_handles_all_unverified(self):
        """Test behavior when NO claims are verified."""
        invalid_claim = AtomicClaim(statement="Fake news", support_text="None", source_url="http://fake", confidence=0.0)
        invalid_result = CritiqueResult(claim=invalid_claim, is_valid=False, reason="Rejected")
        
        report = self.synthesizer.synthesize([invalid_result])
        
        self.assertEqual(report, "No verified information found.")

if __name__ == "__main__":
    unittest.main()
