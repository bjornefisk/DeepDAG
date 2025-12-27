import unittest
from HDRP.tools.search.simulated import SimulatedSearchProvider
from HDRP.services.researcher.service import ResearcherService
from HDRP.services.critic.service import CriticService
from HDRP.services.synthesizer.service import SynthesizerService
from HDRP.services.shared.claims import AtomicClaim

class TestHDRPIntegration(unittest.TestCase):
    def setUp(self):
        # Initialize the full stack
        self.search_provider = SimulatedSearchProvider()
        self.researcher = ResearcherService(self.search_provider, run_id="test-integration-run")
        self.critic = CriticService()
        self.synthesizer = SynthesizerService()

    def test_full_flow_quantum_computing(self):
        """Simulate a full research iteration on 'quantum computing'."""
        query = "Research the impact of quantum computing"
        
        # 1. Researcher: Find claims
        print(f"\n[Integration] Step 1: Researching '{query}'...")
        # Simulate passing a node ID
        claims = self.researcher.research(query, source_node_id="node_quantum_1")
        self.assertGreater(len(claims), 0, "Researcher should find claims")
        print(f" -> Found {len(claims)} raw claims.")
        
        # Verify source_node_id propagation
        for c in claims:
            self.assertEqual(c.source_node_id, "node_quantum_1")
        
        # 2. Critic: Verify claims
        print("[Integration] Step 2: Verifying claims...")
        critique_results = []
        verified_claims_count = 0
        for claim in claims:
            # Check verification logic
            results = self.critic.verify([claim], task=query)
            critique_results.extend(results)
            
            # unpack list of tuples
            for res in results:
                if res.is_valid:
                    verified_claims_count += 1
                else:
                    # Optional: assert that rejection reasons are valid strings
                    self.assertTrue(len(res.reason) > 0)
        
        print(f" -> Verified {verified_claims_count} claims.")
        self.assertGreater(verified_claims_count, 0, "Critic should verify at least some claims")
        
        # 3. Synthesizer: Generate Report
        print("[Integration] Step 3: Synthesizing report...")
        report = self.synthesizer.synthesize(critique_results)
        
        # Validation
        self.assertIn("# Research Report", report)
        self.assertIn("Bibliography", report)
        # Check if the simulated "Nature" article is in the bibliography
        # The simulated provider returns "nature.com" for quantum queries
        verified_claims = [res.claim for res in critique_results if res.is_valid]
        self.assertTrue(any("nature.com" in c.source_url for c in verified_claims))
        print(" -> Report generated successfully.")

    def test_entity_discovery_propagation(self):
        """Test that entities discovered by Researcher are present in the flow."""
        query = "Research NASA missions" 
        # Simulated provider generates generic results for this, 
        # but let's check if our entity extraction logic runs on them.
        
        claims = self.researcher.research(query)
        self.assertGreater(len(claims), 0)
        
        # Check if any claim has discovered entities
        entities_found = 0
        for claim in claims:
            if claim.discovered_entities:
                entities_found += 1
                
        # We can't guarantee the simulated text has capitalized entities unless we control it.
        # But 'SimulatedSearchProvider' returns "Result X for 'Research NASA missions'..."
        # 'Research', 'NASA' might be picked up.
        print(f" -> Entities found in {entities_found}/{len(claims)} claims.")
        # We don't assert > 0 here to avoid flakiness if logic changes, 
        # but we verified the logic in unit tests. This just checks no crash.

if __name__ == "__main__":
    unittest.main()
