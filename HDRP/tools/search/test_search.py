import json
import unittest
from unittest.mock import MagicMock, patch

from HDRP.tools.search import (
    SearchFactory,
    SearchResult,
    SearchError,
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


class TestSearchFactoryFromEnv(unittest.TestCase):
    """Tests for SearchFactory.from_env() with various env configurations."""

    def test_from_env_default_simulated(self):
        """Verify from_env() returns simulated when no env vars set."""
        with patch.dict('os.environ', {}, clear=True):
            provider = SearchFactory.from_env()
        
        # Should return simulated provider
        self.assertTrue(provider.health_check())

    def test_from_env_respects_provider_env_var(self):
        """Verify from_env() uses HDRP_SEARCH_PROVIDER."""
        with patch.dict('os.environ', {'HDRP_SEARCH_PROVIDER': 'simulated'}, clear=True):
            provider = SearchFactory.from_env()
        
        self.assertTrue(provider.health_check())

    @patch('HDRP.tools.search.factory.SearchFactory.get_provider')
    def test_from_env_google_with_env_vars(self, mock_get_provider):
        """Verify from_env() passes Google config from env vars."""
        mock_provider = MagicMock()
        mock_provider.health_check.return_value = True
        mock_get_provider.return_value = mock_provider
        
        env = {
            'HDRP_SEARCH_PROVIDER': 'google',
            'GOOGLE_API_KEY': 'test-key',
            'GOOGLE_CX': 'test-cx',
            'GOOGLE_TIMEOUT_SECONDS': '10.0',
            'GOOGLE_MAX_RESULTS': '5',
        }
        with patch.dict('os.environ', env, clear=True):
            provider = SearchFactory.from_env()
        
        # Should have called get_provider with google config
        mock_get_provider.assert_called_with(
            'google',
            api_key='test-key',
            cx='test-cx',
            timeout_seconds=10.0,
            default_max_results=5,
        )

    @patch('HDRP.tools.search.factory.SearchFactory.get_provider')
    def test_from_env_handles_invalid_timeout(self, mock_get_provider):
        """Verify from_env() handles invalid timeout gracefully."""
        mock_provider = MagicMock()
        mock_provider.health_check.return_value = True
        mock_get_provider.return_value = mock_provider
        
        env = {
            'HDRP_SEARCH_PROVIDER': 'google',
            'GOOGLE_API_KEY': 'test-key',
            'GOOGLE_CX': 'test-cx',
            'GOOGLE_TIMEOUT_SECONDS': 'not-a-number',
        }
        with patch.dict('os.environ', env, clear=True):
            provider = SearchFactory.from_env()
        
        # Should have used default timeout (8.0)
        call_kwargs = mock_get_provider.call_args[1]
        self.assertEqual(call_kwargs['timeout_seconds'], 8.0)

    @patch('HDRP.tools.search.factory.SearchFactory.get_provider')
    def test_from_env_handles_invalid_max_results(self, mock_get_provider):
        """Verify from_env() handles invalid max_results gracefully."""
        mock_provider = MagicMock()
        mock_provider.health_check.return_value = True
        mock_get_provider.return_value = mock_provider
        
        env = {
            'HDRP_SEARCH_PROVIDER': 'google',
            'GOOGLE_API_KEY': 'test-key',
            'GOOGLE_CX': 'test-cx',
            'GOOGLE_MAX_RESULTS': 'invalid',
        }
        with patch.dict('os.environ', env, clear=True):
            provider = SearchFactory.from_env()
        
        # Should have used None for default_max_results
        call_kwargs = mock_get_provider.call_args[1]
        self.assertIsNone(call_kwargs['default_max_results'])


class TestSearchFactoryFallback(unittest.TestCase):
    """Tests for fallback behavior when providers fail health checks."""

    def test_fallback_to_simulated_on_health_check_failure(self):
        """Verify fallback to simulated when Google health check fails."""
        with patch('HDRP.tools.search.factory.SearchFactory.get_provider') as mock_get:
            # First call (google) returns provider that fails health check
            mock_google = MagicMock()
            mock_google.health_check.return_value = False
            
            # Second call (simulated) returns working provider
            mock_simulated = MagicMock()
            mock_simulated.health_check.return_value = True
            
            mock_get.side_effect = [mock_google, mock_simulated]
            
            env = {
                'HDRP_SEARCH_PROVIDER': 'google',
                'GOOGLE_API_KEY': 'test-key',
                'GOOGLE_CX': 'test-cx',
            }
            with patch.dict('os.environ', env, clear=True):
                provider = SearchFactory.from_env(strict_mode=False)
            
            # Should have fallen back to simulated
            self.assertEqual(provider, mock_simulated)

    def test_strict_mode_raises_on_health_check_failure(self):
        """Verify strict mode raises instead of falling back."""
        with patch('HDRP.tools.search.factory.SearchFactory.get_provider') as mock_get:
            mock_google = MagicMock()
            mock_google.health_check.return_value = False
            mock_get.return_value = mock_google
            
            env = {
                'HDRP_SEARCH_PROVIDER': 'google',
                'GOOGLE_API_KEY': 'test-key',
                'GOOGLE_CX': 'test-cx',
            }
            with patch.dict('os.environ', env, clear=True):
                with self.assertRaises(SearchError):
                    SearchFactory.from_env(strict_mode=True)

    def test_fallback_on_search_error_during_init(self):
        """Verify fallback when SearchError raised during initialization."""
        with patch('HDRP.tools.search.factory.SearchFactory.get_provider') as mock_get:
            # First call raises SearchError
            mock_simulated = MagicMock()
            mock_simulated.health_check.return_value = True
            
            mock_get.side_effect = [SearchError("Init failed"), mock_simulated]
            
            env = {
                'HDRP_SEARCH_PROVIDER': 'google',
                'GOOGLE_API_KEY': 'test-key',
                'GOOGLE_CX': 'test-cx',
            }
            with patch.dict('os.environ', env, clear=True):
                provider = SearchFactory.from_env(strict_mode=False)
            
            # Should have fallen back to simulated
            self.assertEqual(provider, mock_simulated)

    def test_strict_mode_raises_on_search_error(self):
        """Verify strict mode raises SearchError on init failure."""
        with patch('HDRP.tools.search.factory.SearchFactory.get_provider') as mock_get:
            mock_get.side_effect = SearchError("Init failed")
            
            env = {
                'HDRP_SEARCH_PROVIDER': 'google',
                'GOOGLE_API_KEY': 'test-key',
                'GOOGLE_CX': 'test-cx',
            }
            with patch.dict('os.environ', env, clear=True):
                with self.assertRaises(SearchError):
                    SearchFactory.from_env(strict_mode=True)

    def test_fallback_on_unexpected_exception(self):
        """Verify fallback on unexpected exceptions."""
        with patch('HDRP.tools.search.factory.SearchFactory.get_provider') as mock_get:
            # First call raises unexpected exception
            mock_simulated = MagicMock()
            mock_simulated.health_check.return_value = True
            
            mock_get.side_effect = [RuntimeError("Unexpected"), mock_simulated]
            
            env = {
                'HDRP_SEARCH_PROVIDER': 'google',
                'GOOGLE_API_KEY': 'test-key',
                'GOOGLE_CX': 'test-cx',
            }
            with patch.dict('os.environ', env, clear=True):
                provider = SearchFactory.from_env(strict_mode=False)
            
            # Should have fallen back to simulated
            self.assertEqual(provider, mock_simulated)

    def test_default_provider_arg(self):
        """Verify default_provider argument is used when env var not set."""
        # Clear env vars
        with patch.dict('os.environ', {}, clear=True):
            provider = SearchFactory.from_env(default_provider='simulated')
        
        self.assertTrue(provider.health_check())


class TestSearchProviderHealthCheck(unittest.TestCase):
    """Tests for provider health check behavior."""

    def test_simulated_always_healthy(self):
        """Verify simulated provider always returns healthy."""
        provider = SearchFactory.get_provider("simulated")
        self.assertTrue(provider.health_check())

    @patch("HDRP.tools.search.google.request.urlopen")
    def test_google_health_check_success(self, mock_urlopen):
        """Verify Google health check succeeds with valid response."""
        from HDRP.tools.search import GoogleSearchProvider
        
        # Mock a successful but empty search response
        mock_resp = MagicMock()
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.getcode.return_value = 200
        mock_resp.read.return_value = json.dumps({"items": []}).encode("utf-8")
        mock_urlopen.return_value = mock_resp
        
        provider = GoogleSearchProvider(
            api_key="test-key",
            cx="test-cx",
            validate_key=False,
        )
        
        # Should be able to make a search (health check)
        response = provider.search("test")
        self.assertEqual(len(response.results), 0)

    @patch("HDRP.tools.search.google.request.urlopen")
    def test_google_health_check_failure_on_error(self, mock_urlopen):
        """Verify Google search fails on HTTP error."""
        from HDRP.tools.search import GoogleSearchProvider
        from urllib import error as urlerror
        
        mock_urlopen.side_effect = urlerror.HTTPError(
            url="https://googleapis.com",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=None,
        )
        
        provider = GoogleSearchProvider(
            api_key="invalid-key",
            cx="test-cx",
            validate_key=False,
        )
        
        with self.assertRaises(SearchError):
            provider.search("test")


if __name__ == '__main__':
    unittest.main()