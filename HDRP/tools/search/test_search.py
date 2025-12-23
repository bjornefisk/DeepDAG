import unittest
from HDRP.tools.search import SearchFactory, SearchResult

class TestSearchTool(unittest.TestCase):
    
    def setUp(self):
        self.provider = SearchFactory.get_provider("simulated")

    def test_factory_default(self):
        """Ensure factory returns the correct type."""
        self.assertEqual(self.provider.health_check(), True)

    def test_basic_search(self):
        """Test a general search query."""
        query = "test query"
        response = self.provider.search(query, max_results=3)
        
        self.assertEqual(response.query, query)
        self.assertEqual(len(response.results), 3)
        self.assertIsInstance(response.results[0], SearchResult)
        self.assertTrue(response.latency_ms > 0)

    def test_context_aware_results(self):
        """Test the simulated provider's ability to return relevant mock data."""
        response = self.provider.search("quantum computing")
        
        found_relevant = False
        for res in response.results:
            if "Crypt" in res.title or "NIST" in res.title:
                found_relevant = True
                break
        
        self.assertTrue(found_relevant, "Simulated provider should return context-aware results for 'quantum'")

    def test_search_limit_enforcement(self):
        """Verify that the tool strictly enforces source limits."""
        # 1. Hard cap check
        response = self.provider.search("test limit", max_results=20)
        self.assertLessEqual(len(response.results), 10, "Should clamp to HARD_LIMIT_SOURCES (10)")
        
        # 2. Diversity check (Simulated provider generates many 'example.com' results)
        # By default, the mock generator creates many 'example.com' links.
        # Our new logic should limit this to 2 per domain.
        
        # We need to request enough results to trigger the per-domain limit but stay under the hard cap
        response = self.provider.search("diversity test", max_results=5)
        
        domain_counts = {}
        for res in response.results:
            domain = res.url.split("//")[1].split("/")[0]
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
            
        for domain, count in domain_counts.items():
            self.assertLessEqual(count, 2, f"Domain {domain} exceeded max diversity limit")

if __name__ == '__main__':
    unittest.main()
