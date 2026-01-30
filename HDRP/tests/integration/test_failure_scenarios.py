"""Failure scenario integration tests.

Tests pipeline behavior under various failure conditions:
- Service timeouts
- Critic rejecting all claims
- gRPC connection failures
- Partial service availability
- Search provider errors
"""

import os
import sys
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import subprocess

import pytest

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from HDRP.cli import run_query_programmatic
from HDRP.services.researcher.service import ResearcherService
from HDRP.services.critic.service import CriticService
from HDRP.tools.search.base import SearchError
from HDRP.services.shared.claims import AtomicClaim, CritiqueResult


class TestResearcherTimeouts:
    """Tests for researcher service timeout scenarios."""
    
    @pytest.mark.timeout(8)
    def test_researcher_timeout_graceful_degradation(
        self,
        ensure_search_provider_env,
        mock_artifacts_dir,
        mocker
    ):
        """Test that slow researcher operations are handled."""
        # Mock researcher to be slow but not timeout pytest
        def slow_research(*args, **kwargs):
            time.sleep(2)  # Slow but not timeout-inducing
            return []
        
        mocker.patch(
            'HDRP.services.researcher.service.ResearcherService.research',
            side_effect=slow_research
        )
        
        # Should complete but be slow
        result = run_query_programmatic(
            query="quantum computing",
            provider="simulated",
            verbose=False
        )
        
        # Should succeed with empty/minimal results
        assert result["success"] is True

    
    @pytest.mark.timeout(10)
    def test_researcher_timeout_returns_error(
        self,
        ensure_search_provider_env,
        mock_artifacts_dir,
        mocker
    ):
        """Test that researcher timeout returns a proper error response."""
        # Mock researcher to raise TimeoutError
        mocker.patch(
            'HDRP.services.researcher.service.ResearcherService.research',
            side_effect=TimeoutError("Search provider timeout")
        )
        
        result = run_query_programmatic(
            query="quantum computing",
            provider="simulated",
            verbose=False
        )
        
        # Should fail gracefully
        assert result["success"] is False
        assert "timeout" in result["error"].lower() or "failed" in result["error"].lower()
        assert result["report"] == ""


class TestCriticRejection:
    """Tests for critic rejecting all claims."""
    
    @pytest.mark.timeout(10)
    def test_critic_rejects_all_claims(
        self,
        ensure_search_provider_env,
        mock_artifacts_dir,
        mocker
    ):
        """Test pipeline when critic rejects all claims."""
        # Mock critic to reject everything
        def reject_all_claims(claims, task=None):
            return [
                CritiqueResult(
                    claim=claim,
                    is_valid=False,
                    reason="Test rejection: insufficient evidence",
                    confidence=0.0
                )
                for claim in claims
            ]
        
        mocker.patch(
            'HDRP.services.critic.service.CriticService.verify',
            side_effect=reject_all_claims
        )
        
        result = run_query_programmatic(
            query="quantum computing",
            provider="simulated",
            verbose=False
        )
        
        # Should succeed but have no verified claims
        assert result["success"] is True
        assert result["report"], "Should still generate a report"
        
        # Check metadata shows zero verified claims
        run_id = result["run_id"]
        import json
        metadata_path = mock_artifacts_dir / run_id / "metadata.json"
        with open(metadata_path) as f:
            metadata = json.load(f)
        
        assert metadata["statistics"]["verified_claims"] == 0, "Should have zero verified claims"
        assert metadata["statistics"]["rejected_claims"] > 0, "Should have rejected claims"


class TestGRPCConnectionFailures:
    """Tests for gRPC service connection failures."""
    
    @pytest.mark.timeout(15)
    def test_orchestrator_mode_services_not_started(
        self,
        ensure_search_provider_env,
        tmp_path
    ):
        """Test orchestrator mode when services are not available."""
        output_file = tmp_path / "report.md"
        
        # Try to run in orchestrator mode without starting services
        result = subprocess.run(
            [
                sys.executable, "-m", "HDRP.cli",
                "--query", "quantum computing",
                "--provider", "simulated",
                "--mode", "orchestrator",
                "--output", str(output_file)
            ],
            cwd=str(root_dir),
            capture_output=True,
            text=True,
            timeout=12  # Give more time for connection attempts to fail
        )
        
        # Should fail with connection error
        assert result.returncode != 0, "Should fail when services unavailable"
        # The error output should mention service/connection issues
        error_output = result.stderr + result.stdout
        assert any(
            keyword in error_output.lower() 
            for keyword in ["failed", "error", "connection", "service"]
        ), "Should report service/connection error"


class TestPartialServiceAvailability:
    """Tests for scenarios with partial service availability."""
    
    @pytest.mark.timeout(10)
    def test_search_provider_initialization_failure(
        self,
        mock_artifacts_dir,
        mocker
    ):
        """Test when search provider fails to initialize."""
        # Mock SearchFactory to raise error
        mocker.patch(
            'HDRP.cli.SearchFactory.from_env',
            side_effect=SearchError("Failed to initialize search provider")
        )
        
        result = run_query_programmatic(
            query="quantum computing",
            provider="",  # Use from_env which we mocked
            verbose=False
        )
        
        assert result["success"] is False
        assert "search provider" in result["error"].lower() or "configuration" in result["error"].lower()


class TestSearchProviderErrors:
    """Tests for search provider error scenarios."""
    
    @pytest.mark.timeout(10)
    def test_search_provider_raises_error(
        self,
        ensure_search_provider_env,
        mock_artifacts_dir,
        mocker
    ):
        """Test when search provider raises an error during search."""
        # Create a mock search provider that raises error
        mock_provider = Mock()
        mock_provider.search.side_effect = SearchError("API rate limit exceeded")
        mock_provider.health_check.return_value = True
        
        mocker.patch(
            'HDRP.tools.search.factory.SearchFactory.from_env',
            return_value=mock_provider
        )
        
        result = run_query_programmatic(
            query="quantum computing",
            provider="",  # Use from_env
            verbose=False
        )
        
        # Should fail gracefully
        assert result["success"] is False, "Should report failure"
        assert result["error"], "Should have error message"
    
    @pytest.mark.timeout(10)
    def test_search_provider_returns_empty_results(
        self,
        ensure_search_provider_env,
        mock_artifacts_dir,
        mocker
    ):
        """Test when search provider returns no results."""
        from HDRP.tools.search.schema import SearchResponse
        
        # Create mock that returns empty results
        mock_provider = Mock()
        mock_provider.search.return_value = SearchResponse(
            query="test",
            results=[],
            total_found=0,
            latency_ms=10.0
        )
        mock_provider.health_check.return_value = True
        
        mocker.patch(
            'HDRP.tools.search.factory.SearchFactory.from_env',
            return_value=mock_provider
        )
        
        result = run_query_programmatic(
            query="quantum computing",
            provider="",
            verbose=False
        )
        
        # Should succeed but indicate no information found
        assert result["success"] is True
        assert "no information" in result["report"].lower() or len(result["report"]) < 100


class TestServiceExceptions:
    """Tests for various service-level exceptions."""
    
    @pytest.mark.timeout(10)
    def test_synthesizer_failure(
        self,
        ensure_search_provider_env,
        mock_artifacts_dir,
        mocker
    ):
        """Test when synthesizer service fails."""
        mocker.patch(
            'HDRP.services.synthesizer.service.SynthesizerService.synthesize',
            side_effect=Exception("Synthesizer internal error")
        )
        
        result = run_query_programmatic(
            query="quantum computing",
            provider="simulated",
            verbose=False
        )
        
        # Should report failure
        assert result["success"] is False
        assert result["error"], "Should have error message"
    
    @pytest.mark.timeout(10)
    def test_researcher_returns_malformed_claims(
        self,
        ensure_search_provider_env,
        mock_artifacts_dir,
        mocker
    ):
        """Test when researcher returns malformed claim objects."""
        # Mock to return non-AtomicClaim objects
        mocker.patch(
            'HDRP.services.researcher.service.ResearcherService.research',
            return_value=[{"invalid": "claim"}]  # Not an AtomicClaim
        )
        
        result = run_query_programmatic(
            query="quantum computing",
            provider="simulated",
            verbose=False
        )
        
        # Should either fail or handle gracefully
        # The exact behavior depends on implementation, but shouldn't crash
        assert isinstance(result, dict)
        assert "success" in result


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    @pytest.mark.timeout(20)
    def test_very_long_query(
        self,
        ensure_search_provider_env,
        mock_artifacts_dir
    ):
        """Test with extremely long query."""
        long_query = "quantum computing " * 20  # Very long query (reduced from 100 for reasonable test time)
        
        result = run_query_programmatic(
            query=long_query,
            provider="simulated",
            verbose=False
        )
        
        # Should either succeed or fail gracefully (no crash)
        assert isinstance(result, dict)
        assert "success" in result
    
    @pytest.mark.timeout(10)
    def test_special_characters_in_query(
        self,
        ensure_search_provider_env,
        mock_artifacts_dir
    ):
        """Test with special characters in query."""
        special_query = "quantum <script>alert('xss')</script> computing & \"quotes\""
        
        result = run_query_programmatic(
            query=special_query,
            provider="simulated",
            verbose=False
        )
        
        # Should handle special characters without crashing
        assert isinstance(result, dict)
        assert "success" in result
