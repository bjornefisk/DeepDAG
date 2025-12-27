import unittest
from HDRP.services.synthesizer.service import SynthesizerService
from HDRP.services.shared.claims import AtomicClaim, CritiqueResult

class TestReportSections(unittest.TestCase):
    def setUp(self):
        self.synthesizer = SynthesizerService()

    def test_custom_report_sections(self):
        """Test customized report generation with mapped sections and TOC."""
        
        # Claims from different nodes
        claim_a = AtomicClaim(
            statement="Quantum supremacy achieved.",
            support_text="Google claimed quantum supremacy.",
            source_url="http://google.com/quantum",
            source_node_id="node_1",
            confidence=0.9
        )
        res_a = CritiqueResult(claim=claim_a, is_valid=True, reason="Verified")

        claim_b = AtomicClaim(
            statement="Qubits are fragile.",
            support_text="Decoherence is a problem.",
            source_url="http://ibm.com/quantum",
            source_node_id="node_2",
            confidence=0.9
        )
        res_b = CritiqueResult(claim=claim_b, is_valid=True, reason="Verified")

        # Context for synthesis
        context = {
            "report_title": "State of Quantum Computing 2025",
            "introduction": "This report summarizes key findings.",
            "section_headers": {
                "node_1": "Milestones",
                "node_2": "Challenges"
            }
        }

        # Synthesize
        report = self.synthesizer.synthesize([res_a, res_b], context=context)
        
        print("\nGenerated Sectioned Report:\n", report)

        # Assertions
        # 1. Title
        self.assertIn("# State of Quantum Computing 2025", report)
        
        # 2. Introduction
        self.assertIn("This report summarizes key findings.", report)
        
        # 3. Table of Contents
        self.assertIn("## Table of Contents", report)
        self.assertIn("- [Milestones](#milestones)", report)
        self.assertIn("- [Challenges](#challenges)", report)
        
        # 4. Section Headers
        self.assertIn("## Milestones", report)
        self.assertIn("## Challenges", report)
        
        # 5. Content
        self.assertIn("Quantum supremacy achieved.", report)
        self.assertIn("Qubits are fragile.", report)

    def test_default_fallback(self):
        """Test that it behaves reasonably without context."""
        claim = AtomicClaim(statement="A fact.", source_node_id="node_x", confidence=1.0)
        res = CritiqueResult(claim=claim, is_valid=True, reason="ok")
        
        report = self.synthesizer.synthesize([res])
        
        self.assertIn("# Research Report", report)
        self.assertIn("## Node: node_x", report)
        self.assertNotIn("## Table of Contents", report) # Only 1 section

if __name__ == "__main__":
    unittest.main()
