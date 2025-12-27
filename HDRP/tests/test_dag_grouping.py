import unittest
from HDRP.services.synthesizer.service import SynthesizerService
from HDRP.services.shared.claims import AtomicClaim, CritiqueResult

class TestDAGGrouping(unittest.TestCase):
    def setUp(self):
        self.synthesizer = SynthesizerService()

    def test_synthesizer_groups_by_node_id(self):
        """Test that the synthesizer groups claims by their source DAG node ID."""
        
        # Claims from Node A
        claim_a1 = AtomicClaim(
            statement="Node A finding 1.",
            support_text="Support A1",
            source_url="http://a1.com",
            source_node_id="node_a",
            confidence=0.9
        )
        result_a1 = CritiqueResult(claim=claim_a1, is_valid=True, reason="Verified")

        claim_a2 = AtomicClaim(
            statement="Node A finding 2.",
            support_text="Support A2",
            source_url="http://a2.com",
            source_node_id="node_a",
            confidence=0.9
        )
        result_a2 = CritiqueResult(claim=claim_a2, is_valid=True, reason="Verified")

        # Claims from Node B
        claim_b1 = AtomicClaim(
            statement="Node B finding 1.",
            support_text="Support B1",
            source_url="http://b1.com",
            source_node_id="node_b",
            confidence=0.9
        )
        result_b1 = CritiqueResult(claim=claim_b1, is_valid=True, reason="Verified")

        # Claim with no Node ID
        claim_gen = AtomicClaim(
            statement="General finding.",
            support_text="Support Gen",
            source_url="http://gen.com",
            source_node_id=None,
            confidence=0.9
        )
        result_gen = CritiqueResult(claim=claim_gen, is_valid=True, reason="Verified")

        # Synthesize
        report = self.synthesizer.synthesize([result_a1, result_b1, result_a2, result_gen])
        
        print("\nGenerated Report:\n", report)

        # Check for Section Headers
        self.assertIn("## Node: node_a", report)
        self.assertIn("## Node: node_b", report)
        self.assertIn("## General Findings", report)
        
        # Check Content Placement
        # We can't strictly rely on string index order across sections without parsing,
        # but we can check if content appears.
        self.assertIn("Node A finding 1.", report)
        self.assertIn("Node A finding 2.", report)
        self.assertIn("Node B finding 1.", report)
        self.assertIn("General finding.", report)

        # Check that Node A content follows Node A header and precedes Node B header (assuming alphabetical sort of keys)
        # Keys sorted: "General Findings", "node_a", "node_b" ? 
        # Actually "General Findings" < "node_a" (G < n) 
        
        idx_gen_header = report.find("## General Findings")
        idx_node_a_header = report.find("## Node: node_a")
        idx_node_b_header = report.find("## Node: node_b")
        
        self.assertTrue(idx_gen_header != -1)
        self.assertTrue(idx_node_a_header != -1)
        self.assertTrue(idx_node_b_header != -1)
        
        # Verify content is roughly under headers
        # Finding 1 should be after Node A header
        self.assertTrue(report.find("Node A finding 1.") > idx_node_a_header)
        
        # Finding B1 should be after Node B header
        self.assertTrue(report.find("Node B finding 1.") > idx_node_b_header)


if __name__ == "__main__":
    unittest.main()
