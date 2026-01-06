import json
import unittest
from unittest.mock import MagicMock, patch

from HDRP.tools.search import (
    MultiSearchProvider,
    SearchResult,
    SearchError,
)


class TestMultiSearchProvider(unittest.TestCase):
    
    def test_multi_provider_combines_results(self):
        """Test that MultiSearchProvider combines results from multiple providers."""
        # Create mock providers
        provider1 = MagicMock()
        provider1.search.return_value = MagicMock(
            results=[
                SearchResult(
                    title="Result 1 from Provider 1",
                    url="https://example.com/1",
                    snippet="Snippet 1",
                    source="provider1"
                ),
                SearchResult(
                    title="Result 2 from Provider 1",
                    url="https://example.com/2",
                    snippet="Snippet 2",
                    source="provider1"
                ),
            ]
        )
        
        provider2 = MagicMock()
        provider2.search.return_value = MagicMock(
            results=[
                SearchResult(
                    title="Result 1 from Provider 2",
                    url="https://test.com/1",
                    snippet="Snippet 3",
                    source="provider2"
                ),
            ]
        )
        
        # Create multi-provider
        multi = MultiSearchProvider(providers=[provider1, provider2])
        response = multi.search("test query", max_results=10)
        
        # Should have results from both providers
        self.assertEqual(len(response.results), 3)
        self.assertEqual(response.total_found, 3)
        
    def test_multi_provider_deduplicates_urls(self):
        """Test that duplicate URLs are removed."""
        provider1 = MagicMock()
        provider1.search.return_value = MagicMock(
            results=[
                SearchResult(
                    title="Result 1",
                    url="https://example.com/same",
                    snippet="Snippet 1",
                    source="provider1"
                ),
            ]
        )
        
        provider2 = MagicMock()
        provider2.search.return_value = MagicMock(
            results=[
                SearchResult(
                    title="Result 2",
                    url="https://example.com/same",  # Duplicate URL
                    snippet="Snippet 2",
                    source="provider2"
                ),
            ]
        )
        
        multi = MultiSearchProvider(
            providers=[provider1, provider2],
            dedup_by_url=True
        )
        response = multi.search("test query", max_results=10)
        
        # Should only have 1 result (duplicate removed)
        self.assertEqual(len(response.results), 1)
        
    def test_multi_provider_enforces_domain_limit(self):
        """Test that domain limits are enforced."""
        provider = MagicMock()
        provider.search.return_value = MagicMock(
            results=[
                SearchResult(
                    title=f"Result {i}",
                    url=f"https://example.com/{i}",
                    snippet=f"Snippet {i}",
                    source="provider"
                )
                for i in range(5)  # 5 results from same domain
            ]
        )
        
        multi = MultiSearchProvider(
            providers=[provider],
            dedup_by_domain_limit=2  # Max 2 per domain
        )
        response = multi.search("test query", max_results=10)
        
        # Should only have 2 results (domain limit enforced)
        self.assertEqual(len(response.results), 2)
        
    def test_multi_provider_handles_provider_failure(self):
        """Test that MultiSearchProvider continues if one provider fails."""
        provider1 = MagicMock()
        provider1.search.side_effect = SearchError("Provider 1 failed")
        
        provider2 = MagicMock()
        provider2.search.return_value = MagicMock(
            results=[
                SearchResult(
                    title="Result from Provider 2",
                    url="https://test.com/1",
                    snippet="Snippet",
                    source="provider2"
                ),
            ]
        )
        
        multi = MultiSearchProvider(providers=[provider1, provider2])
        response = multi.search("test query", max_results=10)
        
        # Should still get results from provider2
        self.assertEqual(len(response.results), 1)
        
    def test_multi_provider_fails_if_all_providers_fail(self):
        """Test that MultiSearchProvider raises error if all providers fail."""
        provider1 = MagicMock()
        provider1.search.side_effect = SearchError("Provider 1 failed")
        
        provider2 = MagicMock()
        provider2.search.side_effect = SearchError("Provider 2 failed")
        
        multi = MultiSearchProvider(providers=[provider1, provider2])
        
        with self.assertRaises(SearchError) as context:
            multi.search("test query", max_results=10)
        
        self.assertIn("All providers failed", str(context.exception))
        
    def test_multi_provider_health_check(self):
        """Test that health check returns True if any provider is healthy."""
        provider1 = MagicMock()
        provider1.health_check.return_value = False
        
        provider2 = MagicMock()
        provider2.health_check.return_value = True
        
        multi = MultiSearchProvider(providers=[provider1, provider2])
        
        self.assertTrue(multi.health_check())


if __name__ == '__main__':
    unittest.main()
