import unittest
from HDRP.services.researcher.service import ResearcherService
from HDRP.tools.search.simulated import SimulatedSearchProvider

class TestResearcherService(unittest.TestCase):
    def setUp(self):
        self.search_provider = SimulatedSearchProvider()
        self.researcher = ResearcherService(self.search_provider)

    def test_research_attaches_sources(self):
        query = "quantum computing"
        claims = self.researcher.research(query)
        
        self.assertGreater(len(claims), 0)
        for claim in claims:
            # Verify that each claim has a source URL and support text
            self.assertIsNotNone(claim.source_url)
            self.assertIsNotNone(claim.support_text)
            self.assertTrue(claim.source_url.startswith("http"))
            # In our MVP ClaimExtractor, support_text is the statement itself
            self.assertEqual(claim.statement, claim.support_text)
            print(f"Claim: {claim.statement}")
            print(f"Source: {claim.source_url}")
            print(f"Support: {claim.support_text}")
            print("-" * 20)

if __name__ == "__main__":
    unittest.main()
