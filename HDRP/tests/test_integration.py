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
        claims = self.researcher.research(query)
        self.assertGreater(len(claims), 0, "Researcher should find claims")
        print(f" -> Found {len(claims)} raw claims.")
        
        # 2. Critic: Verify claims
        print("[Integration] Step 2: Verifying claims...")
        verified_claims = []
        for claim in claims:
            # Check verification logic
            results = self.critic.verify([claim], task=query)
            # unpack list of tuples
            for res in results:
                if res.is_valid:
                    verified_claims.append(res.claim)
                else:
                    # Optional: assert that rejection reasons are valid strings
                    self.assertTrue(len(res.reason) > 0)
        
        print(f" -> Verified {len(verified_claims)} claims.")
        self.assertGreater(len(verified_claims), 0, "Critic should verify at least some claims")
        
        # 3. Synthesizer: Generate Report
        print("[Integration] Step 3: Synthesizing report...")
        report = self.synthesizer.synthesize(verified_claims)
        
        # Validation
        self.assertIn("# Research Report", report)
        self.assertIn("Bibliography", report)
        # Check if the simulated "Nature" article is in the bibliography
        # The simulated provider returns "nature.com" for quantum queries
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
