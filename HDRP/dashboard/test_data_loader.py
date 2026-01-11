"""
Unit tests for HDRP dashboard data_loader module.

Tests list_available_runs, load_run, _parse_claim, get_run_summary_stats,
get_demo_data, get_latest_events, and get_run_progress functions.
"""

import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from HDRP.dashboard.data_loader import (
    LOGS_DIR,
    ClaimData,
    RunData,
    list_available_runs,
    load_run,
    _parse_claim,
    get_run_summary_stats,
    get_demo_data,
    get_latest_events,
    get_run_progress,
)


class TestClaimData(unittest.TestCase):
    """Tests for ClaimData dataclass."""

    def test_default_values(self):
        """Verify default values are set correctly."""
        claim = ClaimData(claim_id="c1", statement="Test claim")
        
        self.assertEqual(claim.claim_id, "c1")
        self.assertEqual(claim.statement, "Test claim")
        self.assertIsNone(claim.source_url)
        self.assertIsNone(claim.source_title)
        self.assertEqual(claim.confidence, 0.0)
        self.assertIsNone(claim.is_verified)
        self.assertIsNone(claim.verification_reason)
        self.assertEqual(claim.entailment_score, 0.0)
        self.assertIsNone(claim.extracted_at)
        self.assertIsNone(claim.source_node_id)

    def test_all_fields(self):
        """Verify all fields can be set."""
        claim = ClaimData(
            claim_id="c2",
            statement="Full claim",
            source_url="https://example.com",
            source_title="Example Title",
            confidence=0.9,
            is_verified=True,
            verification_reason="Verified",
            entailment_score=0.85,
            extracted_at="2024-01-15T10:00:00Z",
            source_node_id="node1",
        )
        
        self.assertEqual(claim.source_url, "https://example.com")
        self.assertEqual(claim.source_title, "Example Title")
        self.assertEqual(claim.confidence, 0.9)
        self.assertTrue(claim.is_verified)


class TestRunData(unittest.TestCase):
    """Tests for RunData dataclass."""

    def test_default_values(self):
        """Verify default values are set correctly."""
        run = RunData(run_id="run-1")
        
        self.assertEqual(run.run_id, "run-1")
        self.assertEqual(run.query, "")
        self.assertEqual(run.timestamp, "")
        self.assertEqual(run.status, "unknown")
        self.assertEqual(run.claims, [])
        self.assertEqual(run.events, [])
        self.assertEqual(run.metrics, {})
        self.assertIsNone(run.dag_data)
        self.assertEqual(run.total_claims, 0)
        self.assertEqual(run.verified_claims, 0)
        self.assertEqual(run.rejected_claims, 0)
        self.assertEqual(run.unique_sources, 0)
        self.assertEqual(run.execution_time_ms, 0.0)


class TestParseClaim(unittest.TestCase):
    """Tests for _parse_claim function."""

    def test_parses_complete_claim_data(self):
        """Verify complete claim data is parsed correctly."""
        data = {
            "claim_id": "c1",
            "statement": "Test statement",
            "source_url": "https://example.com",
            "source_title": "Example",
            "confidence": 0.85,
            "extracted_at": "2024-01-15T10:00:00Z",
            "source_node_id": "node1",
        }
        
        claim = _parse_claim(data)
        
        self.assertEqual(claim.claim_id, "c1")
        self.assertEqual(claim.statement, "Test statement")
        self.assertEqual(claim.source_url, "https://example.com")
        self.assertEqual(claim.source_title, "Example")
        self.assertEqual(claim.confidence, 0.85)
        self.assertEqual(claim.extracted_at, "2024-01-15T10:00:00Z")
        self.assertEqual(claim.source_node_id, "node1")

    def test_parses_with_alternative_keys(self):
        """Verify alternative keys are handled (id, claim)."""
        data = {
            "id": "c2",
            "claim": "Alternative claim text",
        }
        
        claim = _parse_claim(data)
        
        self.assertEqual(claim.claim_id, "c2")
        self.assertEqual(claim.statement, "Alternative claim text")

    def test_handles_missing_fields(self):
        """Verify missing fields use defaults."""
        data = {"claim_id": "c3"}
        
        claim = _parse_claim(data)
        
        self.assertEqual(claim.claim_id, "c3")
        self.assertEqual(claim.statement, "")
        self.assertEqual(claim.source_url, "")
        self.assertEqual(claim.confidence, 0.0)

    def test_handles_empty_dict(self):
        """Verify empty dict is handled."""
        claim = _parse_claim({})
        
        self.assertEqual(claim.claim_id, "")
        self.assertEqual(claim.statement, "")


class TestListAvailableRuns(unittest.TestCase):
    """Tests for list_available_runs function."""

    def test_returns_empty_when_no_logs_dir(self):
        """Verify empty list when logs dir doesn't exist."""
        with patch.object(Path, 'exists', return_value=False):
            with patch('HDRP.dashboard.data_loader.LOGS_DIR', Path("/nonexistent")):
                runs = list_available_runs()
        
        self.assertEqual(runs, [])

    def test_returns_list_of_dicts(self):
        """Verify returns list of dictionaries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)
            
            # Create a test log file
            log_file = logs_dir / "test-run.jsonl"
            event = {"timestamp": "2024-01-15T10:00:00Z", "event": "test", "payload": {"query": "test query"}}
            log_file.write_text(json.dumps(event) + "\n")
            
            with patch('HDRP.dashboard.data_loader.LOGS_DIR', logs_dir):
                runs = list_available_runs()
            
            self.assertIsInstance(runs, list)
            self.assertEqual(len(runs), 1)
            self.assertIn("run_id", runs[0])
            self.assertIn("filename", runs[0])
            self.assertIn("timestamp", runs[0])

    def test_extracts_query_from_first_event(self):
        """Verify query is extracted from first event."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)
            
            log_file = logs_dir / "query-run.jsonl"
            event = {"timestamp": "2024-01-15T10:00:00Z", "payload": {"query": "my research query"}}
            log_file.write_text(json.dumps(event) + "\n")
            
            with patch('HDRP.dashboard.data_loader.LOGS_DIR', logs_dir):
                runs = list_available_runs()
            
            self.assertEqual(runs[0]["query"], "my research query")

    def test_truncates_long_queries(self):
        """Verify long queries are truncated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)
            
            long_query = "x" * 150
            log_file = logs_dir / "long-query.jsonl"
            event = {"timestamp": "2024-01-15T10:00:00Z", "payload": {"query": long_query}}
            log_file.write_text(json.dumps(event) + "\n")
            
            with patch('HDRP.dashboard.data_loader.LOGS_DIR', logs_dir):
                runs = list_available_runs()
            
            self.assertLessEqual(len(runs[0]["query"]), 103)  # 100 + "..."
            self.assertTrue(runs[0]["query"].endswith("..."))

    def test_sorts_by_timestamp_descending(self):
        """Verify runs are sorted by timestamp (newest first)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)
            
            # Create files with different timestamps
            for i, ts in enumerate(["2024-01-10T10:00:00Z", "2024-01-15T10:00:00Z", "2024-01-12T10:00:00Z"]):
                log_file = logs_dir / f"run-{i}.jsonl"
                event = {"timestamp": ts, "payload": {}}
                log_file.write_text(json.dumps(event) + "\n")
            
            with patch('HDRP.dashboard.data_loader.LOGS_DIR', logs_dir):
                runs = list_available_runs()
            
            # Should be sorted by timestamp descending
            timestamps = [r["timestamp"] for r in runs]
            self.assertEqual(timestamps, sorted(timestamps, reverse=True))

    def test_skips_readme(self):
        """Verify README.md is skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)
            
            (logs_dir / "README.md").write_text("# Logs")
            log_file = logs_dir / "real-run.jsonl"
            log_file.write_text(json.dumps({"timestamp": "2024-01-15T10:00:00Z"}) + "\n")
            
            with patch('HDRP.dashboard.data_loader.LOGS_DIR', logs_dir):
                runs = list_available_runs()
            
            self.assertEqual(len(runs), 1)
            self.assertEqual(runs[0]["run_id"], "real-run")


class TestLoadRun(unittest.TestCase):
    """Tests for load_run function."""

    def test_returns_none_for_nonexistent_run(self):
        """Verify None returned for nonexistent run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('HDRP.dashboard.data_loader.LOGS_DIR', Path(tmpdir)):
                result = load_run("nonexistent-run")
        
        self.assertIsNone(result)

    def test_returns_run_data(self):
        """Verify RunData is returned for valid run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)
            
            log_file = logs_dir / "test-run.jsonl"
            events = [
                {"timestamp": "2024-01-15T10:00:00Z", "component": "researcher", "event": "research_start", "payload": {"query": "test"}},
            ]
            log_file.write_text("\n".join(json.dumps(e) for e in events) + "\n")
            
            with patch('HDRP.dashboard.data_loader.LOGS_DIR', logs_dir):
                result = load_run("test-run")
            
            self.assertIsInstance(result, RunData)
            self.assertEqual(result.run_id, "test-run")

    def test_extracts_query(self):
        """Verify query is extracted from events."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)
            
            log_file = logs_dir / "query-run.jsonl"
            events = [
                {"timestamp": "2024-01-15T10:00:00Z", "event": "research_start", "payload": {"query": "my query"}},
            ]
            log_file.write_text("\n".join(json.dumps(e) for e in events) + "\n")
            
            with patch('HDRP.dashboard.data_loader.LOGS_DIR', logs_dir):
                result = load_run("query-run")
            
            self.assertEqual(result.query, "my query")

    def test_parses_claims_extracted_event(self):
        """Verify claims_extracted events are parsed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)
            
            log_file = logs_dir / "claims-run.jsonl"
            events = [
                {
                    "timestamp": "2024-01-15T10:00:00Z",
                    "event": "claims_extracted",
                    "payload": {
                        "claims": [
                            {"claim_id": "c1", "statement": "Claim 1", "source_url": "https://ex.com/1"},
                            {"claim_id": "c2", "statement": "Claim 2", "source_url": "https://ex.com/2"},
                        ]
                    }
                },
            ]
            log_file.write_text("\n".join(json.dumps(e) for e in events) + "\n")
            
            with patch('HDRP.dashboard.data_loader.LOGS_DIR', logs_dir):
                result = load_run("claims-run")
            
            self.assertEqual(result.total_claims, 2)
            self.assertEqual(len(result.claims), 2)

    def test_parses_verification_events(self):
        """Verify verification events update claims."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)
            
            log_file = logs_dir / "verify-run.jsonl"
            events = [
                {
                    "timestamp": "2024-01-15T10:00:00Z",
                    "event": "claims_extracted",
                    "payload": {"claims": [{"claim_id": "c1", "statement": "Test"}]}
                },
                {
                    "timestamp": "2024-01-15T10:00:01Z",
                    "event": "claim_verified",
                    "payload": {"claim_id": "c1", "is_valid": True, "reason": "OK", "entailment_score": 0.9}
                },
            ]
            log_file.write_text("\n".join(json.dumps(e) for e in events) + "\n")
            
            with patch('HDRP.dashboard.data_loader.LOGS_DIR', logs_dir):
                result = load_run("verify-run")
            
            self.assertEqual(result.verified_claims, 1)
            self.assertTrue(result.claims[0].is_verified)
            self.assertEqual(result.claims[0].entailment_score, 0.9)

    def test_parses_dag_update_event(self):
        """Verify dag_update event is captured."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)
            
            dag_data = {"nodes": [{"id": "n1"}], "edges": []}
            log_file = logs_dir / "dag-run.jsonl"
            events = [
                {"timestamp": "2024-01-15T10:00:00Z", "event": "dag_update", "payload": dag_data},
            ]
            log_file.write_text("\n".join(json.dumps(e) for e in events) + "\n")
            
            with patch('HDRP.dashboard.data_loader.LOGS_DIR', logs_dir):
                result = load_run("dag-run")
            
            self.assertEqual(result.dag_data, dag_data)

    def test_parses_run_complete_event(self):
        """Verify run_complete event sets status and metrics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)
            
            log_file = logs_dir / "complete-run.jsonl"
            events = [
                {
                    "timestamp": "2024-01-15T10:00:00Z",
                    "event": "run_complete",
                    "payload": {"execution_time_ms": 1234.5}
                },
            ]
            log_file.write_text("\n".join(json.dumps(e) for e in events) + "\n")
            
            with patch('HDRP.dashboard.data_loader.LOGS_DIR', logs_dir):
                result = load_run("complete-run")
            
            self.assertEqual(result.status, "completed")
            self.assertEqual(result.execution_time_ms, 1234.5)

    def test_counts_unique_sources(self):
        """Verify unique sources are counted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)
            
            log_file = logs_dir / "sources-run.jsonl"
            events = [
                {
                    "timestamp": "2024-01-15T10:00:00Z",
                    "event": "claims_extracted",
                    "payload": {
                        "claims": [
                            {"claim_id": "c1", "statement": "C1", "source_url": "https://a.com"},
                            {"claim_id": "c2", "statement": "C2", "source_url": "https://b.com"},
                            {"claim_id": "c3", "statement": "C3", "source_url": "https://a.com"},  # Dup
                        ]
                    }
                },
            ]
            log_file.write_text("\n".join(json.dumps(e) for e in events) + "\n")
            
            with patch('HDRP.dashboard.data_loader.LOGS_DIR', logs_dir):
                result = load_run("sources-run")
            
            self.assertEqual(result.unique_sources, 2)

    def test_handles_malformed_json(self):
        """Verify malformed JSON lines are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)
            
            log_file = logs_dir / "malformed-run.jsonl"
            log_file.write_text('{"valid": "event"}\nnot valid json\n{"another": "event"}\n')
            
            with patch('HDRP.dashboard.data_loader.LOGS_DIR', logs_dir):
                result = load_run("malformed-run")
            
            # Should have 2 events (skipping malformed line)
            self.assertEqual(len(result.events), 2)


class TestGetRunSummaryStats(unittest.TestCase):
    """Tests for get_run_summary_stats function."""

    def test_returns_stats_dict(self):
        """Verify returns dictionary with expected keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('HDRP.dashboard.data_loader.LOGS_DIR', Path(tmpdir)):
                stats = get_run_summary_stats()
            
            self.assertIsInstance(stats, dict)
            self.assertIn("total_runs", stats)
            self.assertIn("recent_runs", stats)
            self.assertIn("total_claims", stats)
            self.assertIn("total_verified", stats)
            self.assertIn("verification_rate", stats)

    def test_counts_runs(self):
        """Verify runs are counted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)
            
            # Create test log files
            for i in range(3):
                log_file = logs_dir / f"run-{i}.jsonl"
                log_file.write_text(json.dumps({"timestamp": f"2024-01-{10+i}T10:00:00Z"}) + "\n")
            
            with patch('HDRP.dashboard.data_loader.LOGS_DIR', logs_dir):
                stats = get_run_summary_stats()
            
            self.assertEqual(stats["total_runs"], 3)

    def test_calculates_verification_rate(self):
        """Verify verification rate is calculated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)
            
            log_file = logs_dir / "test-run.jsonl"
            events = [
                {
                    "timestamp": "2024-01-15T10:00:00Z",
                    "event": "claims_extracted",
                    "payload": {"claims": [
                        {"claim_id": "c1", "statement": "C1"},
                        {"claim_id": "c2", "statement": "C2"},
                    ]}
                },
                {"timestamp": "2024-01-15T10:00:01Z", "event": "claim_verified", "payload": {"claim_id": "c1", "is_valid": True}},
                {"timestamp": "2024-01-15T10:00:02Z", "event": "claim_verified", "payload": {"claim_id": "c2", "is_valid": False}},
            ]
            log_file.write_text("\n".join(json.dumps(e) for e in events) + "\n")
            
            with patch('HDRP.dashboard.data_loader.LOGS_DIR', logs_dir):
                stats = get_run_summary_stats()
            
            self.assertEqual(stats["total_claims"], 2)
            self.assertEqual(stats["total_verified"], 1)
            self.assertEqual(stats["verification_rate"], 0.5)


class TestGetDemoData(unittest.TestCase):
    """Tests for get_demo_data function."""

    def test_returns_run_data(self):
        """Verify returns RunData object."""
        result = get_demo_data()
        self.assertIsInstance(result, RunData)

    def test_demo_has_claims(self):
        """Verify demo data has claims."""
        result = get_demo_data()
        self.assertGreater(len(result.claims), 0)

    def test_demo_has_query(self):
        """Verify demo data has query."""
        result = get_demo_data()
        self.assertNotEqual(result.query, "")

    def test_demo_has_verified_and_rejected(self):
        """Verify demo data has both verified and rejected claims."""
        result = get_demo_data()
        self.assertGreater(result.verified_claims, 0)
        self.assertGreater(result.rejected_claims, 0)

    def test_demo_has_metrics(self):
        """Verify demo data has metrics."""
        result = get_demo_data()
        self.assertNotEqual(result.metrics, {})


class TestGetLatestEvents(unittest.TestCase):
    """Tests for get_latest_events function."""

    def test_returns_empty_for_nonexistent_run(self):
        """Verify empty list for nonexistent run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('HDRP.dashboard.data_loader.LOGS_DIR', Path(tmpdir)):
                events = get_latest_events("nonexistent")
        
        self.assertEqual(events, [])

    def test_returns_all_events_from_start(self):
        """Verify all events returned when since_line=0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)
            
            log_file = logs_dir / "test-run.jsonl"
            events_data = [
                {"event": "e1", "timestamp": "2024-01-15T10:00:00Z"},
                {"event": "e2", "timestamp": "2024-01-15T10:00:01Z"},
                {"event": "e3", "timestamp": "2024-01-15T10:00:02Z"},
            ]
            log_file.write_text("\n".join(json.dumps(e) for e in events_data) + "\n")
            
            with patch('HDRP.dashboard.data_loader.LOGS_DIR', logs_dir):
                events = get_latest_events("test-run", since_line=0)
            
            self.assertEqual(len(events), 3)

    def test_returns_events_since_line(self):
        """Verify only events since specified line are returned."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)
            
            log_file = logs_dir / "test-run.jsonl"
            events_data = [
                {"event": "e1"},
                {"event": "e2"},
                {"event": "e3"},
                {"event": "e4"},
            ]
            log_file.write_text("\n".join(json.dumps(e) for e in events_data) + "\n")
            
            with patch('HDRP.dashboard.data_loader.LOGS_DIR', logs_dir):
                events = get_latest_events("test-run", since_line=2)
            
            self.assertEqual(len(events), 2)
            self.assertEqual(events[0]["event"], "e3")
            self.assertEqual(events[1]["event"], "e4")

    def test_skips_empty_lines(self):
        """Verify empty lines are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)
            
            log_file = logs_dir / "test-run.jsonl"
            log_file.write_text('{"event": "e1"}\n\n{"event": "e2"}\n')
            
            with patch('HDRP.dashboard.data_loader.LOGS_DIR', logs_dir):
                events = get_latest_events("test-run")
            
            self.assertEqual(len(events), 2)


class TestGetRunProgress(unittest.TestCase):
    """Tests for get_run_progress function."""

    def test_returns_none_for_nonexistent_run(self):
        """Verify None returned for nonexistent run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('HDRP.dashboard.data_loader.LOGS_DIR', Path(tmpdir)):
                progress = get_run_progress("nonexistent")
        
        self.assertIsNone(progress)

    def test_returns_progress_dict(self):
        """Verify returns dictionary with expected keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)
            
            log_file = logs_dir / "test-run.jsonl"
            log_file.write_text(json.dumps({"event": "test"}) + "\n")
            
            with patch('HDRP.dashboard.data_loader.LOGS_DIR', logs_dir):
                progress = get_run_progress("test-run")
            
            self.assertIn("status", progress)
            self.assertIn("current_stage", progress)
            self.assertIn("progress_percent", progress)
            self.assertIn("claims_extracted", progress)
            self.assertIn("claims_verified", progress)
            self.assertIn("claims_rejected", progress)
            self.assertIn("total_events", progress)

    def test_tracks_research_start(self):
        """Verify research_start event is tracked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)
            
            log_file = logs_dir / "test-run.jsonl"
            events = [{"event": "research_start", "payload": {"query": "test"}}]
            log_file.write_text("\n".join(json.dumps(e) for e in events) + "\n")
            
            with patch('HDRP.dashboard.data_loader.LOGS_DIR', logs_dir):
                progress = get_run_progress("test-run")
            
            self.assertEqual(progress["progress_percent"], 10.0)
            self.assertIn("Starting", progress["current_stage"])

    def test_tracks_claims_extracted(self):
        """Verify claims_extracted event is tracked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)
            
            log_file = logs_dir / "test-run.jsonl"
            events = [
                {"event": "claims_extracted", "payload": {"claims": [{"id": "c1"}, {"id": "c2"}]}}
            ]
            log_file.write_text("\n".join(json.dumps(e) for e in events) + "\n")
            
            with patch('HDRP.dashboard.data_loader.LOGS_DIR', logs_dir):
                progress = get_run_progress("test-run")
            
            self.assertEqual(progress["claims_extracted"], 2)
            self.assertEqual(progress["progress_percent"], 40.0)

    def test_tracks_verification(self):
        """Verify verification events are tracked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)
            
            log_file = logs_dir / "test-run.jsonl"
            events = [
                {"event": "claims_extracted", "payload": {"claims": [{"id": "c1"}, {"id": "c2"}]}},
                {"event": "claim_verified", "payload": {"claim_id": "c1", "is_valid": True}},
                {"event": "claim_verified", "payload": {"claim_id": "c2", "is_valid": False}},
            ]
            log_file.write_text("\n".join(json.dumps(e) for e in events) + "\n")
            
            with patch('HDRP.dashboard.data_loader.LOGS_DIR', logs_dir):
                progress = get_run_progress("test-run")
            
            self.assertEqual(progress["claims_verified"], 1)
            self.assertEqual(progress["claims_rejected"], 1)

    def test_tracks_run_complete(self):
        """Verify run_complete event sets status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)
            
            log_file = logs_dir / "test-run.jsonl"
            events = [{"event": "run_complete", "payload": {}}]
            log_file.write_text("\n".join(json.dumps(e) for e in events) + "\n")
            
            with patch('HDRP.dashboard.data_loader.LOGS_DIR', logs_dir):
                progress = get_run_progress("test-run")
            
            self.assertEqual(progress["status"], "completed")
            self.assertEqual(progress["progress_percent"], 100.0)

    def test_tracks_error(self):
        """Verify error event sets failed status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)
            
            log_file = logs_dir / "test-run.jsonl"
            events = [{"event": "error", "payload": {"error": "Something went wrong"}}]
            log_file.write_text("\n".join(json.dumps(e) for e in events) + "\n")
            
            with patch('HDRP.dashboard.data_loader.LOGS_DIR', logs_dir):
                progress = get_run_progress("test-run")
            
            self.assertEqual(progress["status"], "failed")
            self.assertIn("error_message", progress)


if __name__ == "__main__":
    unittest.main()

