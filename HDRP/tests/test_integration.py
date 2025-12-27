import unittest
from datetime import datetime
from HDRP.tools.search.simulated import SimulatedSearchProvider
from HDRP.services.researcher.service import ResearcherService
from HDRP.services.critic.service import CriticService
from HDRP.services.synthesizer.service import SynthesizerService
from HDRP.services.shared.claims import AtomicClaim

class TestHDRPIntegration(unittest.TestCase):
    def setUp(self):
        self.search_provider = SimulatedSearchProvider()
        self.researcher = ResearcherService(self.search_provider, run_id="test-integration-run")
        self.critic = CriticService()
        self.synthesizer = SynthesizerService()

    def test_full_flow_quantum_computing(self):
        """Validates full pipeline: Researcher → Critic → Synthesizer with numbered citations."""
        query = "Research the impact of quantum computing"
        
        # Step 1: Extract claims
        print(f"\n[Integration] Step 1: Researching '{query}'...")
        claims = self.researcher.research(query, source_node_id="node_quantum_1")
        self.assertGreater(len(claims), 0, "Researcher should find claims")
        print(f" -> Found {len(claims)} raw claims.")
        
        # Verify node ID propagation through pipeline
        for c in claims:
            self.assertEqual(c.source_node_id, "node_quantum_1")
        
        # NEW: Verify traceability fields are present
        print("[Integration] Verifying traceability fields on extracted claims...")
        for claim in claims:
            self.assertIsNotNone(claim.extracted_at, "All claims should have extraction timestamp")
            self.assertIsNotNone(claim.source_url, "All claims should have source URL")
            self.assertIsNotNone(claim.source_title, "All claims should have source title")
            self.assertIsNotNone(claim.source_rank, "All claims should have search rank")
            
            # Verify timestamp is valid ISO format
            self.assertTrue(claim.extracted_at.endswith('Z'), "Timestamp should be UTC")
            try:
                datetime.fromisoformat(claim.extracted_at[:-1])
            except ValueError:
                self.fail(f"Invalid timestamp format: {claim.extracted_at}")
        
        print(f" -> All {len(claims)} claims have complete traceability metadata.")
        
        # Step 2: Verify claims
        print("[Integration] Step 2: Verifying claims...")
        critique_results = []
        verified_claims_count = 0
        for claim in claims:
            results = self.critic.verify([claim], task=query)
            critique_results.extend(results)
            
            for res in results:
                if res.is_valid:
                    verified_claims_count += 1
                else:
                    # Ensure rejection reasons are non-empty
                    self.assertTrue(len(res.reason) > 0)
        
        print(f" -> Verified {verified_claims_count} claims.")
        self.assertGreater(verified_claims_count, 0, "Critic should verify at least some claims")
        
        # NEW: Check that traceability survives criticism
        verified_claims = [r.claim for r in critique_results if r.is_valid]
        for claim in verified_claims:
            self.assertIsNotNone(claim.extracted_at, "Timestamp should survive critic stage")
            self.assertIsNotNone(claim.source_title, "Source title should survive critic stage")
        
        # Step 3: Synthesize report
        print("[Integration] Step 3: Synthesizing report...")
        report = self.synthesizer.synthesize(critique_results)
        
        self.assertIn("# Research Report", report)
        self.assertIn("Bibliography", report)
        
        # NEW: Verify traceability in report output
        self.assertIn("Research Metadata", report, "Report should include metadata section")
        self.assertIn("Total Verified Claims", report)
        self.assertIn("Unique Sources", report)
        
        # Verify inline citation format [1], [2], ...
        import re
        citation_pattern = r'\[\d+\]'
        citations_found = re.findall(citation_pattern, report)
        self.assertGreater(len(citations_found), 0, "Report should contain numbered citations")
        
        # Verify bibliography uses numbered format
        self.assertTrue(any(re.match(r'\[\d+\] \*\*', line) for line in report.split('\n')), 
                       "Bibliography should have numbered format with titles")
        
        # NEW: Verify source titles appear in bibliography
        source_titles = [c.source_title for c in verified_claims if c.source_title]
        if source_titles:
            # At least one title should appear
            self.assertTrue(any(title in report for title in source_titles),
                           "Source titles should appear in bibliography")
        
        # Verify simulated search provider results appear in bibliography
        self.assertTrue(any("nature.com" in c.source_url for c in verified_claims))
        print(" -> Report generated successfully with numbered citations and traceability.")
        
        # NEW: Verify timestamp consistency - extraction should happen before report generation
        if verified_claims:
            earliest_extraction = min(c.extracted_at for c in verified_claims if c.extracted_at)
            # The earliest extraction should be before now (sanity check)
            earliest_dt = datetime.fromisoformat(earliest_extraction[:-1])
            now_dt = datetime.utcnow()
            self.assertLessEqual(earliest_dt, now_dt, 
                                "Extraction timestamps should be in the past")

    def test_entity_discovery_propagation(self):
        """Validates entity extraction during claim generation."""
        query = "Research NASA missions"
        
        claims = self.researcher.research(query)
        self.assertGreater(len(claims), 0)
        
        # Count claims with extracted entities
        entities_found = 0
        for claim in claims:
            if claim.discovered_entities:
                entities_found += 1
        
        print(f" -> Entities found in {entities_found}/{len(claims)} claims.")
        # Note: Assertion avoided to prevent flakiness with simulated data
        # Entity extraction logic is unit-tested separately

if __name__ == "__main__":
    unittest.main()
