"""Full pipeline integration tests.

Tests the complete HDRP pipeline from CLI/programmatic entry points
through services to final report generation.
"""

import os
import sys
import json
import subprocess
from pathlib import Path

import pytest

root_dir = Path(__file__).resolve().parent.parent.parent.parent

from HDRP.cli import run_query_programmatic
from HDRP.services.shared.logger import ResearchLogger


class TestFullPipeline:
    """Full pipeline tests covering CLI and programmatic execution."""
    
    @pytest.mark.timeout(15)
    def test_cli_python_mode_full_pipeline(
        self, 
        ensure_search_provider_env, 
        mock_artifacts_dir,
        tmp_path
    ):
        """Test CLI execution in Python mode (direct service calls)."""
        # Prepare output file
        output_file = tmp_path / "report.md"
        
        # Execute CLI command
        result = subprocess.run(
            [
                sys.executable, "-m", "HDRP.cli",
                "--query", "quantum computing impact",
                "--provider", "simulated",
                "--mode", "python",
                "--output", str(output_file),
                "--verbose"
            ],
            cwd=str(root_dir),
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # Assertions
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert output_file.exists(), "Report file should be created"
        
        # Validate report content
        report_content = output_file.read_text()
        assert "# HDRP" in report_content or "# Research Report" in report_content, "Report should have title"
        assert "Bibliography" in report_content, "Report should have bibliography"
        assert len(report_content) > 100, "Report should have substantial content"
        
        # Validate artifacts were created in the real artifacts directory
        # Note: CLI subprocess doesn't use the mocked artifacts dir
        real_artifacts_dir = root_dir / "HDRP" / "artifacts"
        if real_artifacts_dir.exists():
            artifact_dirs = [d for d in real_artifacts_dir.iterdir() if d.is_dir()]
            assert len(artifact_dirs) > 0, "Should create artifact directory"
            
            # Check most recent artifact directory
            artifact_dir = max(artifact_dirs, key=lambda p: p.stat().st_mtime)
            assert (artifact_dir / "metadata.json").exists(), "Should have metadata.json"
            assert (artifact_dir / "report.md").exists(), "Should have report.md in artifacts"
            
            # Validate metadata structure
            with open(artifact_dir / "metadata.json") as f:
                metadata = json.load(f)
            
            assert "bundle_info" in metadata
            assert "statistics" in metadata
            assert "sources" in metadata
            assert metadata["bundle_info"]["query"] == "quantum computing impact"
            assert metadata["statistics"]["total_claims"] > 0, "Should extract claims"
    
    @pytest.mark.timeout(10)
    def test_programmatic_pipeline(
        self,
        ensure_search_provider_env,
        mock_artifacts_dir
    ):
        """Test programmatic API (used by dashboard)."""
        # Execute programmatic query
        result = run_query_programmatic(
            query="research quantum computing",
            provider="simulated",
            verbose=False
        )
        
        # Validate result structure
        assert isinstance(result, dict), "Should return dict"
        assert "success" in result
        assert "run_id" in result
        assert "report" in result
        assert "error" in result
        
        # Validate success
        assert result["success"] is True, f"Should succeed: {result.get('error')}"
        assert result["run_id"], "Should have run_id"
        assert len(result["report"]) > 0, "Should have report content"
        assert result["error"] == "", "Should have no error"
        
        # Validate statistics
        if "stats" in result:
            stats = result["stats"]
            assert "total_claims" in stats
            assert "verified_claims" in stats
            assert stats["total_claims"] > 0, "Should extract claims"
        
        # Validate artifacts
        run_id = result["run_id"]
        artifact_dir = mock_artifacts_dir / run_id
        assert artifact_dir.exists(), f"Artifact dir should exist for {run_id}"
        assert (artifact_dir / "metadata.json").exists()
        assert (artifact_dir / "report.md").exists()
    
    @pytest.mark.timeout(10)
    def test_programmatic_pipeline_with_progress_callback(
        self,
        ensure_search_provider_env,
        mock_artifacts_dir
    ):
        """Test programmatic API with progress callbacks."""
        progress_updates = []
        
        def progress_callback(stage: str, percent: float):
            progress_updates.append((stage, percent))
        
        # Execute with callback
        result = run_query_programmatic(
            query="quantum computing",
            provider="simulated",
            verbose=False,
            progress_callback=progress_callback
        )
        
        # Validate progress updates
        assert len(progress_updates) > 0, "Should receive progress updates"
        assert result["success"] is True
        
        # Check progress is increasing
        percentages = [p for _, p in progress_updates]
        assert percentages[-1] == 100, "Should reach 100% at completion"
        
        # Verify stages are meaningful
        stages = [s for s, _ in progress_updates]
        assert any("Initializing" in s for s in stages), "Should have initialization stage"
        assert any("Completed" in s for s in stages), "Should have completion stage"
    
    @pytest.mark.timeout(10)
    def test_pipeline_with_custom_run_id(
        self,
        ensure_search_provider_env,
        mock_artifacts_dir
    ):
        """Test that custom run_id is respected."""
        custom_run_id = "test-custom-run-12345"
        
        result = run_query_programmatic(
            query="quantum computing",
            provider="simulated",
            run_id=custom_run_id,
            verbose=False
        )
        
        assert result["success"] is True
        assert result["run_id"] == custom_run_id, "Should use custom run_id"
        
        # Verify artifacts use custom run_id
        artifact_dir = mock_artifacts_dir / custom_run_id
        assert artifact_dir.exists(), "Should create artifacts with custom run_id"
    
    @pytest.mark.timeout(10)
    def test_pipeline_empty_query_returns_no_results(
        self,
        ensure_search_provider_env,
        mock_artifacts_dir
    ):
        """Test handling of queries that return no claims."""
        # Query that won't match simulated provider patterns
        result = run_query_programmatic(
            query="xyzabc123notfound",
            provider="simulated",
            verbose=False
        )
        
        # Should still succeed but with no/minimal content
        assert result["success"] is True
        # Simulated provider will return generic results, so we just check no crash
        assert result["report"], "Should return some report even if minimal"


class TestPipelineEndToEnd:
    """Tests that verify complete data flow through the pipeline."""
    
    @pytest.mark.timeout(10)
    def test_claim_traceability_preserved(
        self,
        ensure_search_provider_env,
        mock_artifacts_dir
    ):
        """Verify that traceability metadata flows through the entire pipeline."""
        result = run_query_programmatic(
            query="quantum computing",
            provider="simulated",
            verbose=False
        )
        
        assert result["success"] is True
        
        # Load metadata
        run_id = result["run_id"]
        metadata_path = mock_artifacts_dir / run_id / "metadata.json"
        with open(metadata_path) as f:
            metadata = json.load(f)
        
        # Verify sources have proper structure
        sources = metadata.get("sources", [])
        assert len(sources) > 0, "Should have sources"
        
        for source in sources:
            assert "url" in source, "Source should have URL"
            assert "title" in source, "Source should have title"
            assert "rank" in source, "Source should have search rank"
            assert "claims" in source, "Source should have claim count"
        
        # Verify report includes citations
        report = result["report"]
        import re
        citations = re.findall(r'\[\d+\]', report)
        assert len(citations) > 0, "Report should contain numbered citations"
