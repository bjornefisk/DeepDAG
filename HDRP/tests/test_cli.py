"""
Unit tests for HDRP CLI module.

Tests _build_search_provider, execute_pipeline, and run_query_programmatic functions.
"""

import os
import unittest
from unittest.mock import MagicMock, patch, Mock

from HDRP.cli import (
    execute_pipeline,
    run_query_programmatic,
)
from HDRP.services.shared.pipeline_runner import build_search_provider
from HDRP.tools.search.base import SearchError
from HDRP.tools.search.api_key_validator import APIKeyError


class TestBuildSearchProvider(unittest.TestCase):
    """Tests for _build_search_provider function."""

    @patch('HDRP.services.shared.pipeline_runner.SearchFactory')
    def test_empty_provider_uses_from_env(self, mock_factory):
        """Verify empty provider string delegates to from_env()."""
        mock_factory.from_env.return_value = MagicMock()
        
        result = build_search_provider("", None)
        
        mock_factory.from_env.assert_called_once()

    @patch('HDRP.services.shared.pipeline_runner.SearchFactory')
    def test_none_provider_uses_from_env(self, mock_factory):
        """Verify None provider delegates to from_env()."""
        mock_factory.from_env.return_value = MagicMock()
        
        result = build_search_provider(None, None)
        
        mock_factory.from_env.assert_called_once()

    @patch('HDRP.services.shared.pipeline_runner.SearchFactory')
    def test_whitespace_provider_uses_from_env(self, mock_factory):
        """Verify whitespace-only provider delegates to from_env()."""
        mock_factory.from_env.return_value = MagicMock()
        
        result = build_search_provider("   ", None)
        
        mock_factory.from_env.assert_called_once()

    @patch('HDRP.services.shared.pipeline_runner.SearchFactory')
    def test_google_provider_with_explicit_key(self, mock_factory):
        """Verify Google provider uses explicit API key."""
        mock_factory.get_provider.return_value = MagicMock()
        
        result = build_search_provider("google", "my-api-key")
        
        mock_factory.get_provider.assert_called_once_with("google", api_key="my-api-key")

    @patch.dict(os.environ, {"GOOGLE_API_KEY": "env-api-key"})
    @patch('HDRP.services.shared.pipeline_runner.SearchFactory')
    @patch('HDRP.services.shared.settings.get_settings')
    def test_google_provider_uses_env_key_when_none_provided(self, mock_get_settings, mock_factory):
        """Verify Google provider uses key from settings when none provided."""
        mock_factory.get_provider.return_value = MagicMock()
        
        # Mock settings to return the key
        mock_settings = MagicMock()
        mock_settings.search.google.api_key.get_secret_value.return_value = "env-api-key"
        mock_get_settings.return_value = mock_settings
        
        result = build_search_provider("google", None)
        
        mock_factory.get_provider.assert_called_once_with("google", api_key="env-api-key")

    @patch('HDRP.services.shared.pipeline_runner.SearchFactory')
    def test_simulated_provider_ignores_key(self, mock_factory):
        """Verify simulated provider ignores API key."""
        mock_factory.get_provider.return_value = MagicMock()
        
        result = build_search_provider("simulated", "some-key")
        
        mock_factory.get_provider.assert_called_once_with("simulated")

    def test_unknown_provider_raises_system_exit(self):
        """Verify unknown provider raises SystemExit."""
        with self.assertRaises(SystemExit) as ctx:
            build_search_provider("unknown_provider", None)
        
        self.assertIn("Unknown provider", str(ctx.exception))

    @patch('HDRP.services.shared.pipeline_runner.SearchFactory')
    def test_provider_is_case_insensitive(self, mock_factory):
        """Verify provider name is case insensitive."""
        mock_factory.get_provider.return_value = MagicMock()
        
        build_search_provider("GOOGLE", "key")
        mock_factory.get_provider.assert_called_with("google", api_key="key")
        
        mock_factory.reset_mock()
        build_search_provider("Simulated", None)
        mock_factory.get_provider.assert_called_with("simulated")


class TestRunPipeline(unittest.TestCase):
    """Tests for execute_pipeline function."""

    @patch('HDRP.cli.build_search_provider')
    @patch('HDRP.cli.PipelineRunner')
    @patch('HDRP.cli.console')
    def test_returns_zero_on_success(
        self, mock_console, mock_runner_class, mock_build_provider
    ):
        """Verify returns 0 on successful execution."""
        # Setup mocks
        mock_build_provider.return_value = MagicMock()
        
        mock_runner = MagicMock()
        mock_runner.execute.return_value = {
            "success": True,
            "run_id": "test-run-id",
            "report": "Test report",
            "error": "",
        }
        mock_runner_class.return_value = mock_runner
        
        result = execute_pipeline(
            query="test query",
            provider="simulated",
            api_key=None,
            output_path=None,
            verbose=False,
        )
        
        self.assertEqual(result, 0)

    @patch('HDRP.cli.build_search_provider')
    @patch('HDRP.cli.console')
    def test_returns_one_on_search_error(self, mock_console, mock_build_provider):
        """Verify returns 1 on SearchError."""
        mock_build_provider.side_effect = SearchError("API error")
        
        result = execute_pipeline(
            query="test query",
            provider="google",
            api_key=None,
            output_path=None,
            verbose=False,
        )
        
        self.assertEqual(result, 1)

    @patch('HDRP.cli.build_search_provider')
    @patch('HDRP.cli.console')
    def test_returns_one_on_api_key_error(self, mock_console, mock_build_provider):
        """Verify returns 1 on APIKeyError."""
        mock_build_provider.side_effect = APIKeyError("Missing API key")
        
        result = execute_pipeline(
            query="test query",
            provider="google",
            api_key=None,
            output_path=None,
            verbose=False,
        )
        
        self.assertEqual(result, 1)

    @patch('HDRP.cli.build_search_provider')
    @patch('HDRP.cli.PipelineRunner')
    @patch('HDRP.cli.console')
    def test_returns_zero_on_no_claims(
        self, mock_console, mock_runner_class, mock_build_provider
    ):
        """Verify returns 0 when no claims found (graceful handling)."""
        mock_build_provider.return_value = MagicMock()
        
        mock_runner = MagicMock()
        mock_runner.execute.return_value = {
            "success": True,
            "run_id": "test-run-id",
            "report": "No information found for this query.",
            "error": "",
        }
        mock_runner_class.return_value = mock_runner
        
        result = execute_pipeline(
            query="test query",
            provider="simulated",
            api_key=None,
            output_path=None,
            verbose=False,
        )
        
        self.assertEqual(result, 0)

    @patch('HDRP.cli.build_search_provider')
    @patch('HDRP.cli.PipelineRunner')
    @patch('HDRP.cli.console')
    def test_returns_one_on_research_exception(
        self, mock_console, mock_runner_class, mock_build_provider
    ):
        """Verify returns 1 when research throws exception."""
        mock_build_provider.return_value = MagicMock()
        
        mock_runner = MagicMock()
        mock_runner.execute.return_value = {
            "success": False,
            "run_id": "test-run-id",
            "report": "",
            "error": "Research failed: Research failed",
        }
        mock_runner_class.return_value = mock_runner
        
        result = execute_pipeline(
            query="test query",
            provider="simulated",
            api_key=None,
            output_path=None,
            verbose=False,
        )
        
        self.assertEqual(result, 1)


class TestRunQueryProgrammatic(unittest.TestCase):
    """Tests for run_query_programmatic function."""

    @patch('HDRP.cli.build_search_provider')
    @patch('HDRP.cli.PipelineRunner')
    def test_returns_success_dict(
        self, mock_runner_class, mock_build_provider
    ):
        """Verify returns success dictionary on successful execution."""
        # Setup mocks
        mock_build_provider.return_value = MagicMock()
        
        mock_runner = MagicMock()
        mock_runner.execute.return_value = {
            "success": True,
            "run_id": "programmatic-run-id",
            "report": "Generated report",
            "error": "",
            "stats": {
                "total_claims": 1,
                "verified_claims": 1,
                "rejected_claims": 0,
            }
        }
        mock_runner_class.return_value = mock_runner
        
        result = run_query_programmatic(
            query="test query",
            provider="simulated",
        )
        
        self.assertIsInstance(result, dict)
        self.assertTrue(result["success"])
        self.assertEqual(result["run_id"], "programmatic-run-id")
        self.assertEqual(result["report"], "Generated report")
        self.assertEqual(result["error"], "")

    @patch('HDRP.cli.build_search_provider')
    def test_returns_error_on_provider_failure(self, mock_build_provider):
        """Verify returns error dict on provider failure."""
        mock_build_provider.side_effect = SearchError("Provider failed")
        
        result = run_query_programmatic(
            query="test query",
            provider="google",
        )
        
        self.assertFalse(result["success"])
        self.assertIn("Configuration Error", result["error"])
        self.assertEqual(result["report"], "")

    @patch('HDRP.cli.build_search_provider')
    @patch('HDRP.cli.PipelineRunner')
    def test_returns_stats_on_success(
        self, mock_runner_class, mock_build_provider
    ):
        """Verify returns stats in success response."""
        mock_build_provider.return_value = MagicMock()
        
        mock_runner = MagicMock()
        mock_runner.execute.return_value = {
            "success": True,
            "run_id": "stats-run-id",
            "report": "Report",
            "error": "",
            "stats": {
                "total_claims": 5,
                "verified_claims": 3,
                "rejected_claims": 2,
            }
        }
        mock_runner_class.return_value = mock_runner
        
        result = run_query_programmatic(query="test")
        
        self.assertIn("stats", result)
        self.assertEqual(result["stats"]["total_claims"], 5)
        self.assertEqual(result["stats"]["verified_claims"], 3)
        self.assertEqual(result["stats"]["rejected_claims"], 2)

    @patch('HDRP.cli.build_search_provider')
    @patch('HDRP.cli.PipelineRunner')
    def test_handles_no_claims_gracefully(
        self, mock_runner_class, mock_build_provider
    ):
        """Verify handles no claims found gracefully."""
        mock_build_provider.return_value = MagicMock()
        
        mock_runner = MagicMock()
        mock_runner.execute.return_value = {
            "success": True,
            "run_id": "no-claims-run",
            "report": "No information found for this query.",
            "error": "",
        }
        mock_runner_class.return_value = mock_runner
        
        result = run_query_programmatic(query="obscure query")
        
        self.assertTrue(result["success"])
        self.assertIn("No information found", result["report"])

    @patch('HDRP.cli.build_search_provider')
    @patch('HDRP.cli.PipelineRunner')
    def test_returns_error_on_research_failure(
        self, mock_runner_class, mock_build_provider
    ):
        """Verify returns error on research failure."""
        mock_build_provider.return_value = MagicMock()
        
        mock_runner = MagicMock()
        mock_runner.execute.return_value = {
            "success": False,
            "run_id": "research-fail-run",
            "report": "",
            "error": "Research failed: Research error",
        }
        mock_runner_class.return_value = mock_runner
        
        result = run_query_programmatic(query="test")
        
        self.assertFalse(result["success"])
        self.assertIn("Research failed", result["error"])

    @patch('HDRP.cli.build_search_provider')
    @patch('HDRP.cli.PipelineRunner')
    def test_uses_provided_run_id(
        self, mock_runner_class, mock_build_provider
    ):
        """Verify uses provided run_id."""
        mock_build_provider.return_value = MagicMock()
        
        mock_runner = MagicMock()
        mock_runner.execute.return_value = {
            "success": True,
            "run_id": "custom-run-id",
            "report": "Report",
            "error": "",
        }
        mock_runner_class.return_value = mock_runner
        
        result = run_query_programmatic(
            query="test",
            run_id="custom-run-id",
        )
        
        mock_runner_class.assert_called_with(
            search_provider=mock_build_provider.return_value,
            run_id="custom-run-id",
            verbose=False,
            progress_callback=None,
        )

    @patch('HDRP.cli.build_search_provider')
    @patch('HDRP.cli.PipelineRunner')
    def test_calls_progress_callback(
        self, mock_runner_class, mock_build_provider
    ):
        """Verify progress_callback is called."""
        mock_build_provider.return_value = MagicMock()
        
        # Track if progress callback was passed
        captured_callback = None
        def capture_runner(*args, **kwargs):
            nonlocal captured_callback
            captured_callback = kwargs.get('progress_callback')
            mock_runner = MagicMock()
            mock_runner.execute.return_value = {
                "success": True,
                "run_id": "callback-run",
                "report": "Report",
                "error": "",
            }
            return mock_runner
        
        mock_runner_class.side_effect = capture_runner
        
        # Call run_query_programmatic with a callback
        callback = MagicMock()
        result = run_query_programmatic(query="test", progress_callback=callback)
        
        # Verify callback was passed to runner
        self.assertIsNotNone(captured_callback)

    @patch('HDRP.cli.build_search_provider')
    def test_handles_unexpected_exception(self, mock_build_provider):
        """Verify handles unexpected exceptions."""
        mock_build_provider.side_effect = RuntimeError("Unexpected error")
        
        result = run_query_programmatic(query="test")
        
        self.assertFalse(result["success"])
        self.assertIn("Unexpected error", result["error"])


if __name__ == "__main__":
    unittest.main()

