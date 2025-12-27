import unittest
from HDRP.services.synthesizer.service import SynthesizerService
from HDRP.services.shared.claims import AtomicClaim, CritiqueResult

class TestReportSections(unittest.TestCase):
    def setUp(self):
        self.synthesizer = SynthesizerService()

    def test_custom_report_sections(self):
        """Validates section mapping, TOC generation, and numbered citations."""
        
        # Construct test claims from distinct DAG nodes
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

        context = {
            "report_title": "State of Quantum Computing 2025",
            "introduction": "This report summarizes key findings.",
            "section_headers": {
                "node_1": "Milestones",
                "node_2": "Challenges"
            }
        }

        report = self.synthesizer.synthesize([res_a, res_b], context=context)
        
        print("\nGenerated Sectioned Report:\n", report)

        # Verify report structure and citation format
        # Title and introduction
        self.assertIn("# State of Quantum Computing 2025", report)
        self.assertIn("This report summarizes key findings.", report)
        
        # TOC with anchor links
        self.assertIn("## Table of Contents", report)
        self.assertIn("- [Milestones](#milestones)", report)
        self.assertIn("- [Challenges](#challenges)", report)
        
        # Section headers from node mapping
        self.assertIn("## Milestones", report)
        self.assertIn("## Challenges", report)
        
        # Inline citations embedded in claims (updated format: no period after citation)
        self.assertIn("Quantum supremacy achieved. [1]", report)
        self.assertIn("Qubits are fragile. [2]", report)
        self.assertIn("[1]", report)
        self.assertIn("[2]", report)
        
        # Numbered bibliography entries with titles (updated format)
        self.assertIn("## Bibliography", report)
        self.assertIn("http://google.com/quantum", report)
        self.assertIn("http://ibm.com/quantum", report)

    def test_default_fallback(self):
        """Validates default behavior when no context is provided."""
        claim = AtomicClaim(statement="A fact.", source_url="http://example.com/source", source_node_id="node_x", confidence=1.0)
        res = CritiqueResult(claim=claim, is_valid=True, reason="ok")
        
        report = self.synthesizer.synthesize([res])
        
        self.assertIn("# Research Report", report)
        self.assertIn("## Node: node_x", report)
        self.assertNotIn("## Table of Contents", report)  # Single section: no TOC
        # Updated format: no period after citation
        self.assertIn("A fact. [1]", report)
        self.assertIn("http://example.com/source", report)

if __name__ == "__main__":
    unittest.main()
