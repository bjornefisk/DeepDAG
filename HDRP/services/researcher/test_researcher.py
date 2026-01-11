import time
import unittest
from unittest.mock import Mock, MagicMock, patch

from HDRP.services.researcher.service import ResearcherService
from HDRP.tools.search.simulated import SimulatedSearchProvider
from HDRP.tools.search.base import SearchError
from HDRP.tools.search.schema import SearchResponse, SearchResult


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
            # print(f"Claim: {claim.statement}")

    def test_research_failure_logging(self):
        # Mock the search provider to raise an exception
        self.search_provider.search = Mock(side_effect=Exception("Simulated API Error"))
        
        # Ensure exception is re-raised
        with self.assertRaisesRegex(Exception, "Simulated API Error"):
            self.researcher.research("fail query")


class TestResearcherRetryLogic(unittest.TestCase):
    """Tests for retry logic with multiple failures."""

    def setUp(self):
        self.search_provider = Mock()
        self.researcher = ResearcherService(self.search_provider)

    def test_retries_on_search_error(self):
        """Verify retries on SearchError before raising."""
        # First two calls fail, third succeeds
        successful_response = SearchResponse(
            query="test",
            results=[SearchResult(
                title="Test",
                url="https://example.com",
                snippet="Test snippet with enough content to be extracted.",
                source="simulated"
            )],
            total_found=1,
            latency_ms=100,
        )
        self.search_provider.search = Mock(side_effect=[
            SearchError("First failure"),
            SearchError("Second failure"),
            successful_response,
        ])
        
        with patch.object(time, 'sleep'):  # Skip actual sleep
            claims = self.researcher.research("test query")
        
        # Should have retried and eventually succeeded
        self.assertEqual(self.search_provider.search.call_count, 3)

    def test_raises_after_max_retries(self):
        """Verify exception is raised after max retries exhausted."""
        self.search_provider.search = Mock(side_effect=SearchError("Persistent failure"))
        
        with patch.object(time, 'sleep'):  # Skip actual sleep
            with self.assertRaises(SearchError):
                self.researcher.research("fail query")
        
        # Should have tried 3 times (initial + 2 retries)
        self.assertEqual(self.search_provider.search.call_count, 3)

    def test_no_retry_on_non_search_error(self):
        """Verify non-SearchError exceptions are not retried."""
        self.search_provider.search = Mock(side_effect=ValueError("Not a search error"))
        
        with self.assertRaises(ValueError):
            self.researcher.research("fail query")
        
        # Should only try once (no retries for non-SearchError)
        self.assertEqual(self.search_provider.search.call_count, 1)

    def test_logs_retry_attempts(self):
        """Verify retry attempts are logged."""
        self.search_provider.search = Mock(side_effect=SearchError("Transient failure"))
        
        with patch.object(time, 'sleep'):
            with patch.object(self.researcher.logger, 'log') as mock_log:
                with self.assertRaises(SearchError):
                    self.researcher.research("test")
        
        # Should have logged retry events
        retry_calls = [c for c in mock_log.call_args_list if c[0][0] == "research_retry"]
        self.assertEqual(len(retry_calls), 2)


class TestResearcherEmptyResults(unittest.TestCase):
    """Tests for empty search results handling."""

    def setUp(self):
        self.search_provider = Mock()
        self.researcher = ResearcherService(self.search_provider)

    def test_returns_empty_list_on_no_results(self):
        """Verify empty list returned when search returns no results."""
        empty_response = SearchResponse(
            query="test",
            results=[],
            total_found=0,
            latency_ms=50,
        )
        self.search_provider.search = Mock(return_value=empty_response)
        
        claims = self.researcher.research("obscure query")
        
        self.assertEqual(claims, [])

    def test_logs_empty_results(self):
        """Verify empty results are logged."""
        empty_response = SearchResponse(
            query="test",
            results=[],
            total_found=0,
            latency_ms=50,
        )
        self.search_provider.search = Mock(return_value=empty_response)
        
        with patch.object(self.researcher.logger, 'log') as mock_log:
            self.researcher.research("obscure query")
        
        # Should have logged research_failed with EmptyResults type
        failed_calls = [c for c in mock_log.call_args_list if c[0][0] == "research_failed"]
        self.assertEqual(len(failed_calls), 1)
        self.assertEqual(failed_calls[0][0][1]["type"], "EmptyResults")


class TestResearcherSourceNodePropagation(unittest.TestCase):
    """Tests for source node ID propagation."""

    def setUp(self):
        self.search_provider = SimulatedSearchProvider()
        self.researcher = ResearcherService(self.search_provider)

    def test_source_node_id_propagated_to_claims(self):
        """Verify source_node_id is propagated to all claims."""
        claims = self.researcher.research("quantum computing", source_node_id="research_node_1")
        
        self.assertGreater(len(claims), 0)
        for claim in claims:
            self.assertEqual(claim.source_node_id, "research_node_1")

    def test_source_node_id_none_when_not_provided(self):
        """Verify source_node_id is None when not provided."""
        claims = self.researcher.research("quantum computing")
        
        self.assertGreater(len(claims), 0)
        for claim in claims:
            self.assertIsNone(claim.source_node_id)

    def test_source_rank_is_set(self):
        """Verify source_rank is set based on result position."""
        claims = self.researcher.research("quantum computing")
        
        self.assertGreater(len(claims), 0)
        # At least some claims should have source_rank set
        ranks = [c.source_rank for c in claims if c.source_rank is not None]
        self.assertGreater(len(ranks), 0)


class TestResearcherTraceability(unittest.TestCase):
    """Tests for claim traceability fields."""

    def setUp(self):
        self.search_provider = SimulatedSearchProvider()
        self.researcher = ResearcherService(self.search_provider)

    def test_claims_have_extracted_at_timestamp(self):
        """Verify claims have extraction timestamp."""
        claims = self.researcher.research("AI research")
        
        self.assertGreater(len(claims), 0)
        for claim in claims:
            self.assertIsNotNone(claim.extracted_at)
            self.assertTrue(claim.extracted_at.endswith("Z"))

    def test_claims_have_source_title(self):
        """Verify claims have source title when available."""
        claims = self.researcher.research("quantum computing")
        
        self.assertGreater(len(claims), 0)
        # At least some claims should have source_title
        titles = [c.source_title for c in claims if c.source_title]
        self.assertGreater(len(titles), 0)

    def test_claims_have_support_offset(self):
        """Verify claims have support_offset when found in text."""
        claims = self.researcher.research("AI research")
        
        # Claims where support_text == statement should have offset
        for claim in claims:
            if claim.support_text == claim.statement:
                # support_offset should be set (could be 0 or positive)
                self.assertIsNotNone(claim.support_offset)


if __name__ == "__main__":
    unittest.main()