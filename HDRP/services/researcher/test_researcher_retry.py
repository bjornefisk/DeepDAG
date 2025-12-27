import unittest
from unittest.mock import Mock, patch
from HDRP.services.researcher.service import ResearcherService
from HDRP.tools.search.base import SearchError
from HDRP.tools.search.simulated import SimulatedSearchProvider

class TestResearcherServiceRetry(unittest.TestCase):
    def setUp(self):
        self.search_provider = SimulatedSearchProvider()
        self.researcher = ResearcherService(self.search_provider)

    @patch('time.sleep') # Mock sleep to speed up tests
    def test_research_retry_success(self, mock_sleep):
        # Fail twice, then succeed
        # Mock return value needs to mimic SearchResponse
        success_response = Mock()
        success_result = Mock()
        success_result.snippet = "Success snippet"
        success_result.url = "http://success.com"
        success_response.results = [success_result]

        self.search_provider.search = Mock(side_effect=[
            SearchError("Fail 1"),
            SearchError("Fail 2"),
            success_response
        ])
        
        claims = self.researcher.research("retry query")
        
        # Should have called search 3 times (initial + 2 retries)
        self.assertEqual(self.search_provider.search.call_count, 3)
        # Should have slept twice
        self.assertEqual(mock_sleep.call_count, 2)
        
    @patch('time.sleep')
    def test_research_retry_exhausted(self, mock_sleep):
        # Fail 3 times (initial + 2 retries)
        self.search_provider.search = Mock(side_effect=[
            SearchError("Fail 1"),
            SearchError("Fail 2"),
            SearchError("Fail 3")
        ])
        
        with self.assertRaises(SearchError):
            self.researcher.research("fail query")
            
        self.assertEqual(self.search_provider.search.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    def test_research_other_exception_no_retry(self):
        # Fail with generic Exception
        self.search_provider.search = Mock(side_effect=ValueError("Bad Input"))
        
        with self.assertRaises(ValueError):
            self.researcher.research("error query")
            
        # Should have called search only once
        self.assertEqual(self.search_provider.search.call_count, 1)

if __name__ == "__main__":
    unittest.main()
