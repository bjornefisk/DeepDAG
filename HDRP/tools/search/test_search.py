import json
import unittest
from unittest.mock import MagicMock, patch

from HDRP.tools.search import (
    SearchFactory,
    SearchResult,
    SearchError,
    TavilySearchProvider,
)

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

    def test_factory_invalid_provider(self):
        with self.assertRaises(ValueError):
            SearchFactory.get_provider("invalid_provider_name")
            
    def test_factory_google_provider(self):
        """Test that factory can instantiate Google provider."""
        # This will fail validation without API key, but should not raise NotImplementedError
        with self.assertRaises(SearchError):
            SearchFactory.get_provider("google")
    
    def test_factory_bing_provider(self):
        """Test that factory can instantiate Bing provider."""
        # This will fail validation without API key, but should not raise NotImplementedError
        with self.assertRaises(SearchError):
            SearchFactory.get_provider("bing")


class TestTavilyProvider(unittest.TestCase):
    def _mock_urlopen(self, payload, status: int = 200):
        mock_resp = MagicMock()
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.getcode.return_value = status
        mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
        return mock_resp

    @patch("HDRP.tools.search.tavily.request.urlopen")
    def test_tavily_basic_mapping(self, mock_urlopen):
        payload = {
            "results": [
                {
                    "title": "Example title",
                    "url": "https://example.com",
                    "content": "Example content.",
                    "score": 0.99,
                    "published_date": "2024-01-01",
                }
            ],
            "response_time": 1.23,
        }
        mock_urlopen.return_value = self._mock_urlopen(payload)

        provider = TavilySearchProvider(api_key="test-key", validate_key=False)
        response = provider.search("test query", max_results=3)

        self.assertEqual(response.query, "test query")
        self.assertEqual(len(response.results), 1)

        result = response.results[0]
        self.assertEqual(result.title, "Example title")
        self.assertEqual(result.url, "https://example.com")
        self.assertEqual(result.snippet, "Example content.")
        self.assertEqual(result.source, "tavily")
        self.assertEqual(response.total_found, 1)
        self.assertIn("score", result.metadata)

    @patch("HDRP.tools.search.tavily.request.urlopen")
    def test_tavily_handles_empty_results(self, mock_urlopen):
        payload = {"results": []}
        mock_urlopen.return_value = self._mock_urlopen(payload)

        provider = TavilySearchProvider(api_key="test-key", validate_key=False)
        response = provider.search("no results", max_results=5)

        self.assertEqual(response.total_found, 0)
        self.assertEqual(len(response.results), 0)

    @patch("HDRP.tools.search.tavily.request.urlopen")
    def test_tavily_tolerates_partial_items(self, mock_urlopen):
        payload = {
            "results": [
                {
                    # Title intentionally omitted to exercise defaulting logic.
                    "url": "https://example.com/partial",
                    "content": "Partial content.",
                }
            ]
        }
        mock_urlopen.return_value = self._mock_urlopen(payload)

        provider = TavilySearchProvider(api_key="test-key", validate_key=False)
        response = provider.search("partial data", max_results=3)

        self.assertEqual(len(response.results), 1)
        result = response.results[0]
        self.assertEqual(result.title, "Untitled result")
        self.assertEqual(result.url, "https://example.com/partial")
        self.assertEqual(result.snippet, "Partial content.")

    @patch("HDRP.tools.search.tavily.request.urlopen")
    def test_tavily_http_error_raises_search_error(self, mock_urlopen):
        from urllib import error as urlerror

        mock_urlopen.side_effect = urlerror.HTTPError(
            url="https://api.tavily.com/search",
            code=500,
            msg="Server error",
            hdrs=None,
            fp=None,
        )

        provider = TavilySearchProvider(api_key="test-key", validate_key=False)
        with self.assertRaises(SearchError):
            provider.search("trigger error")


class TestGoogleProvider(unittest.TestCase):
    def _mock_urlopen(self, payload, status: int = 200):
        mock_resp = MagicMock()
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.getcode.return_value = status
        mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
        return mock_resp

    @patch("HDRP.tools.search.google.request.urlopen")
    def test_google_basic_mapping(self, mock_urlopen):
        from HDRP.tools.search import GoogleSearchProvider
        
        payload = {
            "items": [
                {
                    "title": "Example Google Result",
                    "link": "https://example.com/page",
                    "snippet": "This is an example snippet from Google.",
                    "pagemap": {
                        "metatags": [
                            {"article:published_time": "2024-01-15"}
                        ]
                    }
                }
            ]
        }
        mock_urlopen.return_value = self._mock_urlopen(payload)

        provider = GoogleSearchProvider(
            api_key="test-google-key", 
            cx="test-cx-id",
            validate_key=False
        )
        response = provider.search("test query", max_results=3)

        self.assertEqual(response.query, "test query")
        self.assertEqual(len(response.results), 1)

        result = response.results[0]
        self.assertEqual(result.title, "Example Google Result")
        self.assertEqual(result.url, "https://example.com/page")
        self.assertEqual(result.snippet, "This is an example snippet from Google.")
        self.assertEqual(result.source, "google")
        self.assertEqual(result.published_date, "2024-01-15")

    @patch("HDRP.tools.search.google.request.urlopen")
    def test_google_handles_empty_results(self, mock_urlopen):
        from HDRP.tools.search import GoogleSearchProvider
        
        payload = {}  # Google returns no 'items' key when no results
        mock_urlopen.return_value = self._mock_urlopen(payload)

        provider = GoogleSearchProvider(
            api_key="test-google-key",
            cx="test-cx-id",
            validate_key=False
        )
        response = provider.search("no results", max_results=5)

        self.assertEqual(response.total_found, 0)
        self.assertEqual(len(response.results), 0)

    @patch("HDRP.tools.search.google.request.urlopen")
    def test_google_tolerates_partial_items(self, mock_urlopen):
        from HDRP.tools.search import GoogleSearchProvider
        
        payload = {
            "items": [
                {
                    # Title intentionally omitted
                    "link": "https://example.com/partial",
                    "snippet": "Partial snippet.",
                }
            ]
        }
        mock_urlopen.return_value = self._mock_urlopen(payload)

        provider = GoogleSearchProvider(
            api_key="test-google-key",
            cx="test-cx-id",
            validate_key=False
        )
        response = provider.search("partial data", max_results=3)

        self.assertEqual(len(response.results), 1)
        result = response.results[0]
        self.assertEqual(result.title, "Untitled result")
        self.assertEqual(result.url, "https://example.com/partial")
        self.assertEqual(result.snippet, "Partial snippet.")

    @patch("HDRP.tools.search.google.request.urlopen")
    def test_google_http_error_raises_search_error(self, mock_urlopen):
        from HDRP.tools.search import GoogleSearchProvider
        from urllib import error as urlerror

        mock_urlopen.side_effect = urlerror.HTTPError(
            url="https://www.googleapis.com/customsearch/v1",
            code=403,
            msg="Forbidden",
            hdrs=None,
            fp=None,
        )

        provider = GoogleSearchProvider(
            api_key="test-google-key",
            cx="test-cx-id",
            validate_key=False
        )
        with self.assertRaises(SearchError):
            provider.search("trigger error")


class TestBingProvider(unittest.TestCase):
    def _mock_urlopen(self, payload, status: int = 200):
        mock_resp = MagicMock()
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.getcode.return_value = status
        mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
        return mock_resp

    @patch("HDRP.tools.search.bing.request.urlopen")
    def test_bing_basic_mapping(self, mock_urlopen):
        from HDRP.tools.search import BingSearchProvider
        
        payload = {
            "webPages": {
                "value": [
                    {
                        "name": "Example Bing Result",
                        "url": "https://example.com/bing-page",
                        "snippet": "This is an example snippet from Bing.",
                        "datePublished": "2024-01-20T10:00:00Z"
                    }
                ]
            }
        }
        mock_urlopen.return_value = self._mock_urlopen(payload)

        provider = BingSearchProvider(
            api_key="test-bing-key",
            validate_key=False
        )
        response = provider.search("test query", max_results=3)

        self.assertEqual(response.query, "test query")
        self.assertEqual(len(response.results), 1)

        result = response.results[0]
        self.assertEqual(result.title, "Example Bing Result")
        self.assertEqual(result.url, "https://example.com/bing-page")
        self.assertEqual(result.snippet, "This is an example snippet from Bing.")
        self.assertEqual(result.source, "bing")
        self.assertEqual(result.published_date, "2024-01-20T10:00:00Z")

    @patch("HDRP.tools.search.bing.request.urlopen")
    def test_bing_handles_empty_results(self, mock_urlopen):
        from HDRP.tools.search import BingSearchProvider
        
        payload = {}  # Bing returns no 'webPages' key when no results
        mock_urlopen.return_value = self._mock_urlopen(payload)

        provider = BingSearchProvider(
            api_key="test-bing-key",
            validate_key=False
        )
        response = provider.search("no results", max_results=5)

        self.assertEqual(response.total_found, 0)
        self.assertEqual(len(response.results), 0)

    @patch("HDRP.tools.search.bing.request.urlopen")
    def test_bing_tolerates_partial_items(self, mock_urlopen):
        from HDRP.tools.search import BingSearchProvider
        
        payload = {
            "webPages": {
                "value": [
                    {
                        # Name intentionally omitted
                        "url": "https://example.com/partial",
                        "snippet": "Partial snippet from Bing.",
                    }
                ]
            }
        }
        mock_urlopen.return_value = self._mock_urlopen(payload)

        provider = BingSearchProvider(
            api_key="test-bing-key",
            validate_key=False
        )
        response = provider.search("partial data", max_results=3)

        self.assertEqual(len(response.results), 1)
        result = response.results[0]
        self.assertEqual(result.title, "Untitled result")
        self.assertEqual(result.url, "https://example.com/partial")
        self.assertEqual(result.snippet, "Partial snippet from Bing.")

    @patch("HDRP.tools.search.bing.request.urlopen")
    def test_bing_http_error_raises_search_error(self, mock_urlopen):
        from HDRP.tools.search import BingSearchProvider
        from urllib import error as urlerror

        mock_urlopen.side_effect = urlerror.HTTPError(
            url="https://api.bing.microsoft.com/v7.0/search",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=None,
        )

        provider = BingSearchProvider(
            api_key="test-bing-key",
            validate_key=False
        )
        with self.assertRaises(SearchError):
            provider.search("trigger error")


if __name__ == '__main__':
    unittest.main()