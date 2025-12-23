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

if __name__ == '__main__':
    unittest.main()
