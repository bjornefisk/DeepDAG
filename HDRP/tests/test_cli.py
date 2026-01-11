"""
Unit tests for HDRP CLI module.

Tests _build_search_provider, _run_pipeline, and run_query_programmatic functions.
"""

import os
import unittest
from unittest.mock import MagicMock, patch, Mock

from HDRP.cli import (
    _build_search_provider,
    _run_pipeline,
    run_query_programmatic,
)
from HDRP.tools.search.base import SearchError
from HDRP.tools.search.api_key_validator import APIKeyError


class TestBuildSearchProvider(unittest.TestCase):
    """Tests for _build_search_provider function."""

    @patch('HDRP.cli.SearchFactory')
    def test_empty_provider_uses_from_env(self, mock_factory):
        """Verify empty provider string delegates to from_env()."""
        mock_factory.from_env.return_value = MagicMock()
        
        result = _build_search_provider("", None)
        
        mock_factory.from_env.assert_called_once()

    @patch('HDRP.cli.SearchFactory')
    def test_none_provider_uses_from_env(self, mock_factory):
        """Verify None provider delegates to from_env()."""
        mock_factory.from_env.return_value = MagicMock()
        
        result = _build_search_provider(None, None)
        
        mock_factory.from_env.assert_called_once()

    @patch('HDRP.cli.SearchFactory')
    def test_whitespace_provider_uses_from_env(self, mock_factory):
        """Verify whitespace-only provider delegates to from_env()."""
        mock_factory.from_env.return_value = MagicMock()
        
        result = _build_search_provider("   ", None)
        
        mock_factory.from_env.assert_called_once()

    @patch('HDRP.cli.SearchFactory')
    def test_google_provider_with_explicit_key(self, mock_factory):
        """Verify Google provider uses explicit API key."""
        mock_factory.get_provider.return_value = MagicMock()
        
        result = _build_search_provider("google", "my-api-key")
        
        mock_factory.get_provider.assert_called_once_with("google", api_key="my-api-key")

    @patch.dict(os.environ, {"GOOGLE_API_KEY": "env-api-key"})
    @patch('HDRP.cli.SearchFactory')
    def test_google_provider_uses_env_key_when_none_provided(self, mock_factory):
        """Verify Google provider falls back to env key."""
        mock_factory.get_provider.return_value = MagicMock()
        
        result = _build_search_provider("google", None)
        
        mock_factory.get_provider.assert_called_once_with("google", api_key="env-api-key")

    @patch('HDRP.cli.SearchFactory')
    def test_simulated_provider_ignores_key(self, mock_factory):
        """Verify simulated provider ignores API key."""
        mock_factory.get_provider.return_value = MagicMock()
        
        result = _build_search_provider("simulated", "some-key")
        
        mock_factory.get_provider.assert_called_once_with("simulated")

    def test_unknown_provider_raises_system_exit(self):
        """Verify unknown provider raises SystemExit."""
        with self.assertRaises(SystemExit) as ctx:
            _build_search_provider("unknown_provider", None)
        
        self.assertIn("Unknown provider", str(ctx.exception))

    @patch('HDRP.cli.SearchFactory')
    def test_provider_is_case_insensitive(self, mock_factory):
        """Verify provider name is case insensitive."""
        mock_factory.get_provider.return_value = MagicMock()
        
        _build_search_provider("GOOGLE", "key")
        mock_factory.get_provider.assert_called_with("google", api_key="key")
        
        mock_factory.reset_mock()
        _build_search_provider("Simulated", None)
        mock_factory.get_provider.assert_called_with("simulated")


class TestRunPipeline(unittest.TestCase):
    """Tests for _run_pipeline function."""

    @patch('HDRP.cli._build_search_provider')
    @patch('HDRP.cli.ResearchLogger')
    @patch('HDRP.cli.ResearcherService')
    @patch('HDRP.cli.CriticService')
    @patch('HDRP.cli.SynthesizerService')
    @patch('HDRP.cli.console')
    def test_returns_zero_on_success(
        self, mock_console, mock_synth, mock_critic, mock_researcher, mock_logger, mock_build_provider
    ):
        """Verify returns 0 on successful execution."""
        # Setup mocks
        mock_build_provider.return_value = MagicMock()
        mock_logger_instance = MagicMock()
        mock_logger_instance.run_id = "test-run-id"
        mock_logger.return_value = mock_logger_instance
        
        mock_researcher_instance = MagicMock()
        mock_researcher_instance.research.return_value = [MagicMock()]
        mock_researcher.return_value = mock_researcher_instance
        
        mock_critic_instance = MagicMock()
        mock_critic_instance.verify.return_value = [MagicMock(is_valid=True)]
        mock_critic.return_value = mock_critic_instance
        
        mock_synth_instance = MagicMock()
        mock_synth_instance.synthesize.return_value = "Test report"
        mock_synth.return_value = mock_synth_instance
        
        result = _run_pipeline(
            query="test query",
            provider="simulated",
            api_key=None,
            output_path=None,
            verbose=False,
        )
        
        self.assertEqual(result, 0)

    @patch('HDRP.cli._build_search_provider')
    @patch('HDRP.cli.ResearchLogger')
    @patch('HDRP.cli.console')
    def test_returns_one_on_search_error(self, mock_console, mock_logger, mock_build_provider):
        """Verify returns 1 on SearchError."""
        mock_build_provider.side_effect = SearchError("API error")
        mock_logger_instance = MagicMock()
        mock_logger_instance.run_id = "test-run-id"
        mock_logger.return_value = mock_logger_instance
        
        result = _run_pipeline(
            query="test query",
            provider="google",
            api_key=None,
            output_path=None,
            verbose=False,
        )
        
        self.assertEqual(result, 1)

    @patch('HDRP.cli._build_search_provider')
    @patch('HDRP.cli.ResearchLogger')
    @patch('HDRP.cli.console')
    def test_returns_one_on_api_key_error(self, mock_console, mock_logger, mock_build_provider):
        """Verify returns 1 on APIKeyError."""
        mock_build_provider.side_effect = APIKeyError("Missing API key")
        mock_logger_instance = MagicMock()
        mock_logger_instance.run_id = "test-run-id"
        mock_logger.return_value = mock_logger_instance
        
        result = _run_pipeline(
            query="test query",
            provider="google",
            api_key=None,
            output_path=None,
            verbose=False,
        )
        
        self.assertEqual(result, 1)

    @patch('HDRP.cli._build_search_provider')
    @patch('HDRP.cli.ResearchLogger')
    @patch('HDRP.cli.ResearcherService')
    @patch('HDRP.cli.console')
    def test_returns_zero_on_no_claims(
        self, mock_console, mock_researcher, mock_logger, mock_build_provider
    ):
        """Verify returns 0 when no claims found (graceful handling)."""
        mock_build_provider.return_value = MagicMock()
        mock_logger_instance = MagicMock()
        mock_logger_instance.run_id = "test-run-id"
        mock_logger.return_value = mock_logger_instance
        
        mock_researcher_instance = MagicMock()
        mock_researcher_instance.research.return_value = []  # No claims
        mock_researcher.return_value = mock_researcher_instance
        
        result = _run_pipeline(
            query="test query",
            provider="simulated",
            api_key=None,
            output_path=None,
            verbose=False,
        )
        
        self.assertEqual(result, 0)

    @patch('HDRP.cli._build_search_provider')
    @patch('HDRP.cli.ResearchLogger')
    @patch('HDRP.cli.ResearcherService')
    @patch('HDRP.cli.console')
    def test_returns_one_on_research_exception(
        self, mock_console, mock_researcher, mock_logger, mock_build_provider
    ):
        """Verify returns 1 when research throws exception."""
        mock_build_provider.return_value = MagicMock()
        mock_logger_instance = MagicMock()
        mock_logger_instance.run_id = "test-run-id"
        mock_logger.return_value = mock_logger_instance
        
        mock_researcher_instance = MagicMock()
        mock_researcher_instance.research.side_effect = Exception("Research failed")
        mock_researcher.return_value = mock_researcher_instance
        
        result = _run_pipeline(
            query="test query",
            provider="simulated",
            api_key=None,
            output_path=None,
            verbose=False,
        )
        
        self.assertEqual(result, 1)


class TestRunQueryProgrammatic(unittest.TestCase):
    """Tests for run_query_programmatic function."""

    @patch('HDRP.cli._build_search_provider')
    @patch('HDRP.cli.ResearchLogger')
    @patch('HDRP.cli.ResearcherService')
    @patch('HDRP.cli.CriticService')
    @patch('HDRP.cli.SynthesizerService')
    def test_returns_success_dict(
        self, mock_synth, mock_critic, mock_researcher, mock_logger, mock_build_provider
    ):
        """Verify returns success dictionary on successful execution."""
        # Setup mocks
        mock_build_provider.return_value = MagicMock()
        mock_logger_instance = MagicMock()
        mock_logger_instance.run_id = "programmatic-run-id"
        mock_logger_instance.log = MagicMock()
        mock_logger.return_value = mock_logger_instance
        
        mock_researcher_instance = MagicMock()
        mock_researcher_instance.research.return_value = [MagicMock()]
        mock_researcher.return_value = mock_researcher_instance
        
        mock_critic_instance = MagicMock()
        mock_critic_instance.verify.return_value = [MagicMock(is_valid=True)]
        mock_critic.return_value = mock_critic_instance
        
        mock_synth_instance = MagicMock()
        mock_synth_instance.synthesize.return_value = "Generated report"
        mock_synth.return_value = mock_synth_instance
        
        result = run_query_programmatic(
            query="test query",
            provider="simulated",
        )
        
        self.assertIsInstance(result, dict)
        self.assertTrue(result["success"])
        self.assertEqual(result["run_id"], "programmatic-run-id")
        self.assertEqual(result["report"], "Generated report")
        self.assertEqual(result["error"], "")

    @patch('HDRP.cli._build_search_provider')
    @patch('HDRP.cli.ResearchLogger')
    def test_returns_error_on_provider_failure(self, mock_logger, mock_build_provider):
        """Verify returns error dict on provider failure."""
        mock_build_provider.side_effect = SearchError("Provider failed")
        mock_logger_instance = MagicMock()
        mock_logger_instance.run_id = "error-run-id"
        mock_logger_instance.log = MagicMock()
        mock_logger.return_value = mock_logger_instance
        
        result = run_query_programmatic(
            query="test query",
            provider="google",
        )
        
        self.assertFalse(result["success"])
        self.assertIn("Configuration Error", result["error"])
        self.assertEqual(result["report"], "")

    @patch('HDRP.cli._build_search_provider')
    @patch('HDRP.cli.ResearchLogger')
    @patch('HDRP.cli.ResearcherService')
    @patch('HDRP.cli.CriticService')
    @patch('HDRP.cli.SynthesizerService')
    def test_returns_stats_on_success(
        self, mock_synth, mock_critic, mock_researcher, mock_logger, mock_build_provider
    ):
        """Verify returns stats in success response."""
        mock_build_provider.return_value = MagicMock()
        mock_logger_instance = MagicMock()
        mock_logger_instance.run_id = "stats-run-id"
        mock_logger_instance.log = MagicMock()
        mock_logger.return_value = mock_logger_instance
        
        # Create mock claims
        mock_claims = [MagicMock() for _ in range(5)]
        mock_researcher_instance = MagicMock()
        mock_researcher_instance.research.return_value = mock_claims
        mock_researcher.return_value = mock_researcher_instance
        
        # 3 verified, 2 rejected
        mock_critique_results = [
            MagicMock(is_valid=True),
            MagicMock(is_valid=True),
            MagicMock(is_valid=True),
            MagicMock(is_valid=False),
            MagicMock(is_valid=False),
        ]
        mock_critic_instance = MagicMock()
        mock_critic_instance.verify.return_value = mock_critique_results
        mock_critic.return_value = mock_critic_instance
        
        mock_synth_instance = MagicMock()
        mock_synth_instance.synthesize.return_value = "Report"
        mock_synth.return_value = mock_synth_instance
        
        result = run_query_programmatic(query="test")
        
        self.assertIn("stats", result)
        self.assertEqual(result["stats"]["total_claims"], 5)
        self.assertEqual(result["stats"]["verified_claims"], 3)
        self.assertEqual(result["stats"]["rejected_claims"], 2)

    @patch('HDRP.cli._build_search_provider')
    @patch('HDRP.cli.ResearchLogger')
    @patch('HDRP.cli.ResearcherService')
    def test_handles_no_claims_gracefully(
        self, mock_researcher, mock_logger, mock_build_provider
    ):
        """Verify handles no claims found gracefully."""
        mock_build_provider.return_value = MagicMock()
        mock_logger_instance = MagicMock()
        mock_logger_instance.run_id = "no-claims-run"
        mock_logger_instance.log = MagicMock()
        mock_logger.return_value = mock_logger_instance
        
        mock_researcher_instance = MagicMock()
        mock_researcher_instance.research.return_value = []
        mock_researcher.return_value = mock_researcher_instance
        
        result = run_query_programmatic(query="obscure query")
        
        self.assertTrue(result["success"])
        self.assertIn("No information found", result["report"])

    @patch('HDRP.cli._build_search_provider')
    @patch('HDRP.cli.ResearchLogger')
    @patch('HDRP.cli.ResearcherService')
    def test_returns_error_on_research_failure(
        self, mock_researcher, mock_logger, mock_build_provider
    ):
        """Verify returns error on research failure."""
        mock_build_provider.return_value = MagicMock()
        mock_logger_instance = MagicMock()
        mock_logger_instance.run_id = "research-fail-run"
        mock_logger_instance.log = MagicMock()
        mock_logger.return_value = mock_logger_instance
        
        mock_researcher_instance = MagicMock()
        mock_researcher_instance.research.side_effect = Exception("Research error")
        mock_researcher.return_value = mock_researcher_instance
        
        result = run_query_programmatic(query="test")
        
        self.assertFalse(result["success"])
        self.assertIn("Research failed", result["error"])

    @patch('HDRP.cli._build_search_provider')
    @patch('HDRP.cli.ResearchLogger')
    @patch('HDRP.cli.ResearcherService')
    @patch('HDRP.cli.CriticService')
    @patch('HDRP.cli.SynthesizerService')
    def test_uses_provided_run_id(
        self, mock_synth, mock_critic, mock_researcher, mock_logger, mock_build_provider
    ):
        """Verify uses provided run_id."""
        mock_build_provider.return_value = MagicMock()
        mock_logger_instance = MagicMock()
        mock_logger_instance.run_id = "custom-run-id"
        mock_logger_instance.log = MagicMock()
        mock_logger.return_value = mock_logger_instance
        
        mock_researcher_instance = MagicMock()
        mock_researcher_instance.research.return_value = [MagicMock()]
        mock_researcher.return_value = mock_researcher_instance
        
        mock_critic_instance = MagicMock()
        mock_critic_instance.verify.return_value = [MagicMock(is_valid=True)]
        mock_critic.return_value = mock_critic_instance
        
        mock_synth_instance = MagicMock()
        mock_synth_instance.synthesize.return_value = "Report"
        mock_synth.return_value = mock_synth_instance
        
        result = run_query_programmatic(
            query="test",
            run_id="custom-run-id",
        )
        
        mock_logger.assert_called_with("cli", run_id="custom-run-id")

    @patch('HDRP.cli._build_search_provider')
    @patch('HDRP.cli.ResearchLogger')
    @patch('HDRP.cli.ResearcherService')
    @patch('HDRP.cli.CriticService')
    @patch('HDRP.cli.SynthesizerService')
    def test_calls_progress_callback(
        self, mock_synth, mock_critic, mock_researcher, mock_logger, mock_build_provider
    ):
        """Verify progress_callback is called."""
        mock_build_provider.return_value = MagicMock()
        mock_logger_instance = MagicMock()
        mock_logger_instance.run_id = "callback-run"
        mock_logger_instance.log = MagicMock()
        mock_logger.return_value = mock_logger_instance
        
        mock_researcher_instance = MagicMock()
        mock_researcher_instance.research.return_value = [MagicMock()]
        mock_researcher.return_value = mock_researcher_instance
        
        mock_critic_instance = MagicMock()
        mock_critic_instance.verify.return_value = [MagicMock(is_valid=True)]
        mock_critic.return_value = mock_critic_instance
        
        mock_synth_instance = MagicMock()
        mock_synth_instance.synthesize.return_value = "Report"
        mock_synth.return_value = mock_synth_instance
        
        progress_calls = []
        def progress_callback(stage, percent):
            progress_calls.append((stage, percent))
        
        result = run_query_programmatic(
            query="test",
            progress_callback=progress_callback,
        )
        
        # Should have multiple progress updates
        self.assertGreater(len(progress_calls), 0)
        # Should include 100% at the end
        self.assertEqual(progress_calls[-1][1], 100)

    @patch('HDRP.cli._build_search_provider')
    @patch('HDRP.cli.ResearchLogger')
    def test_handles_unexpected_exception(self, mock_logger, mock_build_provider):
        """Verify handles unexpected exceptions."""
        mock_build_provider.side_effect = RuntimeError("Unexpected error")
        mock_logger_instance = MagicMock()
        mock_logger_instance.run_id = "unexpected-run"
        mock_logger_instance.log = MagicMock()
        mock_logger.return_value = mock_logger_instance
        
        result = run_query_programmatic(query="test")
        
        self.assertFalse(result["success"])
        self.assertIn("Unexpected error", result["error"])


if __name__ == "__main__":
    unittest.main()

