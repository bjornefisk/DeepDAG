"""
Unit tests for HDRP metrics module.

Tests PerformanceMetrics, QualityMetrics, TrajectoryMetrics, HallucinationMetrics,
SystemMetrics, MetricsCollector, ComparisonResult, and AggregateComparison.
"""

import time
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from HDRP.tools.eval.metrics import (
    PerformanceMetrics,
    QualityMetrics,
    TrajectoryMetrics,
    HallucinationMetrics,
    SystemMetrics,
    MetricsCollector,
    ComparisonResult,
    AggregateComparison,
)
from HDRP.services.shared.claims import AtomicClaim, CritiqueResult
from HDRP.tools.eval.react_agent import ReActRunResult, ReActStep


class TestPerformanceMetrics(unittest.TestCase):
    """Tests for PerformanceMetrics dataclass."""

    def test_default_values(self):
        """Verify default values are set correctly."""
        metrics = PerformanceMetrics()
        self.assertEqual(metrics.total_execution_time_ms, 0.0)
        self.assertEqual(metrics.search_api_latency_ms, 0.0)
        self.assertEqual(metrics.search_calls_count, 0)

    def test_to_dict_returns_dict(self):
        """Verify to_dict returns a dictionary."""
        metrics = PerformanceMetrics(
            total_execution_time_ms=1234.5678,
            search_api_latency_ms=567.8901,
            search_calls_count=5,
        )
        result = metrics.to_dict()
        
        self.assertIsInstance(result, dict)
        self.assertEqual(result["total_execution_time_ms"], 1234.57)  # Rounded
        self.assertEqual(result["search_api_latency_ms"], 567.89)
        self.assertEqual(result["search_calls_count"], 5)

    def test_to_dict_rounds_values(self):
        """Verify to_dict rounds float values to 2 decimal places."""
        metrics = PerformanceMetrics(
            total_execution_time_ms=100.999999,
            search_api_latency_ms=50.111111,
        )
        result = metrics.to_dict()
        
        self.assertEqual(result["total_execution_time_ms"], 101.0)
        self.assertEqual(result["search_api_latency_ms"], 50.11)


class TestQualityMetrics(unittest.TestCase):
    """Tests for QualityMetrics dataclass."""

    def test_default_values(self):
        """Verify default values are set correctly."""
        metrics = QualityMetrics()
        self.assertEqual(metrics.total_claims_extracted, 0)
        self.assertEqual(metrics.raw_claims_extracted, 0)
        self.assertEqual(metrics.verified_claims_count, 0)
        self.assertEqual(metrics.completeness, 0.0)
        self.assertEqual(metrics.precision, 0.0)
        self.assertEqual(metrics.entailment_score, 0.0)

    def test_to_dict_returns_all_fields(self):
        """Verify to_dict returns all fields."""
        metrics = QualityMetrics(
            total_claims_extracted=10,
            raw_claims_extracted=10,
            verified_claims_count=8,
            completeness=0.8,
            precision=0.85,
            entailment_score=0.75,
            avg_entailment_verified=0.78,
            claims_per_source=2.5,
            unique_source_urls=4,
            entailment_check=0.6,
        )
        result = metrics.to_dict()
        
        self.assertEqual(result["total_claims_extracted"], 10)
        self.assertEqual(result["verified_claims_count"], 8)
        self.assertEqual(result["precision"], 0.85)
        self.assertEqual(result["unique_source_urls"], 4)

    def test_to_dict_rounds_floats(self):
        """Verify to_dict rounds float values appropriately."""
        metrics = QualityMetrics(
            completeness=0.12345,
            precision=0.98765,
            entailment_score=0.54321,
        )
        result = metrics.to_dict()
        
        self.assertEqual(result["completeness"], 0.123)
        self.assertEqual(result["precision"], 0.988)
        self.assertEqual(result["entailment_score"], 0.543)


class TestTrajectoryMetrics(unittest.TestCase):
    """Tests for TrajectoryMetrics dataclass."""

    def test_default_values(self):
        """Verify default values are set correctly."""
        metrics = TrajectoryMetrics()
        self.assertEqual(metrics.relevant_claims_ratio, 0.0)
        self.assertEqual(metrics.search_efficiency, 0.0)

    def test_to_dict_returns_dict(self):
        """Verify to_dict returns a dictionary."""
        metrics = TrajectoryMetrics(
            relevant_claims_ratio=0.75,
            search_efficiency=1.5,
        )
        result = metrics.to_dict()
        
        self.assertIsInstance(result, dict)
        self.assertEqual(result["relevant_claims_ratio"], 0.75)
        self.assertEqual(result["search_efficiency"], 1.5)


class TestHallucinationMetrics(unittest.TestCase):
    """Tests for HallucinationMetrics dataclass."""

    def test_default_values(self):
        """Verify default values are set correctly."""
        metrics = HallucinationMetrics()
        self.assertEqual(metrics.claims_without_source, 0)
        self.assertEqual(metrics.claims_with_missing_urls, 0)
        self.assertEqual(metrics.hallucination_risk_score, 0.0)

    def test_to_dict_returns_dict(self):
        """Verify to_dict returns a dictionary."""
        metrics = HallucinationMetrics(
            claims_without_source=2,
            claims_with_missing_urls=1,
            hallucination_risk_score=0.3,
        )
        result = metrics.to_dict()
        
        self.assertEqual(result["claims_without_source"], 2)
        self.assertEqual(result["claims_with_missing_urls"], 1)
        self.assertEqual(result["hallucination_risk_score"], 0.3)


class TestSystemMetrics(unittest.TestCase):
    """Tests for SystemMetrics dataclass."""

    def test_required_fields(self):
        """Verify required fields must be provided."""
        metrics = SystemMetrics(
            system_name="test_system",
            query="test query",
            run_id="run-123",
        )
        self.assertEqual(metrics.system_name, "test_system")
        self.assertEqual(metrics.query, "test query")
        self.assertEqual(metrics.run_id, "run-123")

    def test_timestamp_auto_generated(self):
        """Verify timestamp is auto-generated."""
        metrics = SystemMetrics(
            system_name="test",
            query="query",
            run_id="run-1",
        )
        self.assertIsNotNone(metrics.timestamp)
        self.assertTrue(metrics.timestamp.endswith("Z"))

    def test_nested_metrics_default_factory(self):
        """Verify nested metrics are initialized by default."""
        metrics = SystemMetrics(
            system_name="test",
            query="query",
            run_id="run-1",
        )
        self.assertIsInstance(metrics.performance, PerformanceMetrics)
        self.assertIsInstance(metrics.quality, QualityMetrics)
        self.assertIsInstance(metrics.trajectory, TrajectoryMetrics)
        self.assertIsInstance(metrics.hallucination, HallucinationMetrics)

    def test_to_dict_includes_all_sections(self):
        """Verify to_dict includes all sections."""
        metrics = SystemMetrics(
            system_name="test",
            query="query",
            run_id="run-1",
        )
        result = metrics.to_dict()
        
        self.assertIn("system_name", result)
        self.assertIn("query", result)
        self.assertIn("run_id", result)
        self.assertIn("timestamp", result)
        self.assertIn("performance", result)
        self.assertIn("quality", result)
        self.assertIn("trajectory", result)
        self.assertIn("hallucination", result)


class TestMetricsCollector(unittest.TestCase):
    """Tests for MetricsCollector class."""

    def setUp(self):
        self.collector = MetricsCollector("test_system")
        self.timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _create_claim(self, source_url="https://example.com"):
        return AtomicClaim(
            statement="Test claim",
            support_text="Test claim",
            source_url=source_url,
            confidence=0.8,
            extracted_at=self.timestamp,
        )

    def _create_critique_result(self, claim, is_valid=True, entailment_score=0.8):
        return CritiqueResult(
            claim=claim,
            is_valid=is_valid,
            reason="Test reason",
            entailment_score=entailment_score,
        )

    def test_init_sets_system_name(self):
        """Verify system name is set on init."""
        collector = MetricsCollector("my_system")
        self.assertEqual(collector.system_name, "my_system")

    def test_init_resets_state(self):
        """Verify state is reset on init."""
        collector = MetricsCollector("test")
        self.assertIsNone(collector.start_time)
        self.assertEqual(collector.search_latencies, [])
        self.assertEqual(collector.search_call_count, 0)

    def test_start_timer_sets_time(self):
        """Verify start_timer sets start_time."""
        self.assertIsNone(self.collector.start_time)
        self.collector.start_timer()
        self.assertIsNotNone(self.collector.start_time)
        self.assertIsInstance(self.collector.start_time, float)

    def test_record_search_call_increments_count(self):
        """Verify record_search_call increments count."""
        self.assertEqual(self.collector.search_call_count, 0)
        
        self.collector.record_search_call(100.0)
        self.assertEqual(self.collector.search_call_count, 1)
        
        self.collector.record_search_call(200.0)
        self.assertEqual(self.collector.search_call_count, 2)

    def test_record_search_call_tracks_latencies(self):
        """Verify record_search_call tracks latencies."""
        self.collector.record_search_call(100.5)
        self.collector.record_search_call(200.3)
        
        self.assertEqual(self.collector.search_latencies, [100.5, 200.3])

    def test_count_unique_sources(self):
        """Verify _count_unique_sources counts correctly."""
        claims = [
            self._create_claim(source_url="https://source1.com"),
            self._create_claim(source_url="https://source2.com"),
            self._create_claim(source_url="https://source1.com"),  # Duplicate
            self._create_claim(source_url=None),  # No URL
        ]
        count = self.collector._count_unique_sources(claims)
        self.assertEqual(count, 2)

    def test_count_unique_sources_empty_list(self):
        """Verify _count_unique_sources handles empty list."""
        count = self.collector._count_unique_sources([])
        self.assertEqual(count, 0)

    def test_compute_hallucination_metrics_no_issues(self):
        """Verify _compute_hallucination_metrics with valid claims."""
        claims = [
            self._create_claim(source_url="https://valid.com/1"),
            self._create_claim(source_url="https://valid.com/2"),
        ]
        metrics = self.collector._compute_hallucination_metrics(claims)
        
        self.assertEqual(metrics.claims_without_source, 0)
        self.assertEqual(metrics.claims_with_missing_urls, 0)
        self.assertEqual(metrics.hallucination_risk_score, 0.0)

    def test_compute_hallucination_metrics_missing_urls(self):
        """Verify _compute_hallucination_metrics with missing URLs."""
        claims = [
            self._create_claim(source_url=None),
            self._create_claim(source_url="https://valid.com"),
        ]
        metrics = self.collector._compute_hallucination_metrics(claims)
        
        self.assertEqual(metrics.claims_without_source, 1)
        self.assertEqual(metrics.hallucination_risk_score, 0.5)  # 1/2

    def test_compute_hallucination_metrics_invalid_urls(self):
        """Verify _compute_hallucination_metrics with invalid URLs."""
        claims = [
            self._create_claim(source_url="not-a-url"),  # Doesn't start with http
            self._create_claim(source_url="https://valid.com"),
        ]
        metrics = self.collector._compute_hallucination_metrics(claims)
        
        self.assertEqual(metrics.claims_with_missing_urls, 1)

    def test_compute_hallucination_metrics_empty_claims(self):
        """Verify _compute_hallucination_metrics with empty list."""
        metrics = self.collector._compute_hallucination_metrics([])
        self.assertEqual(metrics.hallucination_risk_score, 0.0)


class TestMetricsCollectorHDRP(unittest.TestCase):
    """Tests for MetricsCollector.collect_from_hdrp method."""

    def setUp(self):
        self.collector = MetricsCollector("hdrp")
        self.timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _create_claim(self, source_url="https://example.com"):
        return AtomicClaim(
            statement="Test claim",
            support_text="Test claim",
            source_url=source_url,
            confidence=0.8,
            extracted_at=self.timestamp,
        )

    def _create_critique_result(self, claim, is_valid=True, entailment_score=0.8):
        return CritiqueResult(
            claim=claim,
            is_valid=is_valid,
            reason="Test reason",
            entailment_score=entailment_score,
        )

    def test_collect_from_hdrp_returns_system_metrics(self):
        """Verify collect_from_hdrp returns SystemMetrics."""
        self.collector.start_timer()
        claims = [self._create_claim()]
        critique_results = [self._create_critique_result(claims[0], is_valid=True)]
        
        result = self.collector.collect_from_hdrp(
            query="test query",
            raw_claims=claims,
            critique_results=critique_results,
            run_id="run-123",
        )
        
        self.assertIsInstance(result, SystemMetrics)
        self.assertEqual(result.system_name, "hdrp")
        self.assertEqual(result.query, "test query")
        self.assertEqual(result.run_id, "run-123")

    def test_collect_from_hdrp_tracks_execution_time(self):
        """Verify execution time is tracked."""
        self.collector.start_timer()
        time.sleep(0.01)  # Brief delay
        
        claims = [self._create_claim()]
        critique_results = [self._create_critique_result(claims[0])]
        
        result = self.collector.collect_from_hdrp(
            query="test",
            raw_claims=claims,
            critique_results=critique_results,
            run_id="run-1",
        )
        
        self.assertGreater(result.performance.total_execution_time_ms, 0)

    def test_collect_from_hdrp_counts_verified_claims(self):
        """Verify verified claims are counted correctly."""
        self.collector.start_timer()
        claims = [self._create_claim() for _ in range(5)]
        critique_results = [
            self._create_critique_result(claims[0], is_valid=True),
            self._create_critique_result(claims[1], is_valid=True),
            self._create_critique_result(claims[2], is_valid=False),
            self._create_critique_result(claims[3], is_valid=True),
            self._create_critique_result(claims[4], is_valid=False),
        ]
        
        result = self.collector.collect_from_hdrp(
            query="test",
            raw_claims=claims,
            critique_results=critique_results,
            run_id="run-1",
        )
        
        self.assertEqual(result.quality.raw_claims_extracted, 5)
        self.assertEqual(result.quality.verified_claims_count, 3)

    def test_collect_from_hdrp_calculates_precision(self):
        """Verify precision is calculated correctly."""
        self.collector.start_timer()
        claims = [self._create_claim() for _ in range(4)]
        critique_results = [
            self._create_critique_result(claims[0], is_valid=True),
            self._create_critique_result(claims[1], is_valid=True),
            self._create_critique_result(claims[2], is_valid=False),
            self._create_critique_result(claims[3], is_valid=False),
        ]
        
        result = self.collector.collect_from_hdrp(
            query="test",
            raw_claims=claims,
            critique_results=critique_results,
            run_id="run-1",
        )
        
        # Precision = verified / raw = 2/4 = 0.5
        self.assertEqual(result.quality.precision, 0.5)

    def test_collect_from_hdrp_calculates_entailment(self):
        """Verify entailment score is calculated correctly."""
        self.collector.start_timer()
        claims = [self._create_claim() for _ in range(2)]
        critique_results = [
            self._create_critique_result(claims[0], is_valid=True, entailment_score=0.8),
            self._create_critique_result(claims[1], is_valid=True, entailment_score=0.6),
        ]
        
        result = self.collector.collect_from_hdrp(
            query="test",
            raw_claims=claims,
            critique_results=critique_results,
            run_id="run-1",
        )
        
        # Average entailment = (0.8 + 0.6) / 2 = 0.7
        self.assertEqual(result.quality.avg_entailment_verified, 0.7)


class TestMetricsCollectorReAct(unittest.TestCase):
    """Tests for MetricsCollector.collect_from_react method."""

    def setUp(self):
        self.collector = MetricsCollector("react")
        self.timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _create_claim(self, source_url="https://example.com"):
        return AtomicClaim(
            statement="Test claim",
            support_text="Test claim",
            source_url=source_url,
            confidence=0.8,
            extracted_at=self.timestamp,
        )

    def _create_react_result(self, claims):
        return ReActRunResult(
            question="test question",
            final_answer="test answer",
            claims=claims,
            steps=[ReActStep(thought="test thought")],
        )

    def _create_critique_result(self, claim, is_valid=True, entailment_score=0.8):
        return CritiqueResult(
            claim=claim,
            is_valid=is_valid,
            reason="Test reason",
            entailment_score=entailment_score,
        )

    def test_collect_from_react_returns_system_metrics(self):
        """Verify collect_from_react returns SystemMetrics."""
        self.collector.start_timer()
        claims = [self._create_claim()]
        result = ReActRunResult(
            question="test",
            final_answer="answer",
            claims=claims,
            steps=[],
        )
        
        metrics = self.collector.collect_from_react(
            query="test query",
            result=result,
            run_id="run-123",
        )
        
        self.assertIsInstance(metrics, SystemMetrics)
        self.assertEqual(metrics.system_name, "react")

    def test_collect_from_react_without_critique_results(self):
        """Verify behavior without critique results."""
        self.collector.start_timer()
        claims = [self._create_claim() for _ in range(5)]
        react_result = self._create_react_result(claims)
        
        metrics = self.collector.collect_from_react(
            query="test",
            result=react_result,
            run_id="run-1",
            critique_results=None,
        )
        
        # Without critique, verified_claims_count should be 0
        self.assertEqual(metrics.quality.raw_claims_extracted, 5)
        self.assertEqual(metrics.quality.verified_claims_count, 0)

    def test_collect_from_react_with_critique_results(self):
        """Verify behavior with critique results."""
        self.collector.start_timer()
        claims = [self._create_claim() for _ in range(3)]
        react_result = self._create_react_result(claims)
        critique_results = [
            self._create_critique_result(claims[0], is_valid=True),
            self._create_critique_result(claims[1], is_valid=False),
            self._create_critique_result(claims[2], is_valid=True),
        ]
        
        metrics = self.collector.collect_from_react(
            query="test",
            result=react_result,
            run_id="run-1",
            critique_results=critique_results,
        )
        
        self.assertEqual(metrics.quality.raw_claims_extracted, 3)
        self.assertEqual(metrics.quality.verified_claims_count, 2)


class TestComparisonResult(unittest.TestCase):
    """Tests for ComparisonResult dataclass."""

    def _create_system_metrics(self, system_name, raw_claims=10, verified_claims=8, entailment=0.7):
        metrics = SystemMetrics(
            system_name=system_name,
            query="test query",
            run_id="run-1",
        )
        metrics.quality.raw_claims_extracted = raw_claims
        metrics.quality.verified_claims_count = verified_claims
        metrics.quality.entailment_check = entailment
        return metrics

    def test_precision_hdrp_vs_react(self):
        """Verify precision_hdrp_vs_react calculation."""
        hdrp_metrics = self._create_system_metrics("hdrp", raw_claims=10, verified_claims=8)
        react_metrics = self._create_system_metrics("react", raw_claims=20, verified_claims=5)
        
        result = ComparisonResult(
            query="test",
            query_id="q1",
            hdrp_metrics=hdrp_metrics,
            react_metrics=react_metrics,
        )
        
        # precision_hdrp_vs_react = hdrp_verified / react_raw = 8/20 = 0.4
        self.assertEqual(result.precision_hdrp_vs_react, 0.4)

    def test_recall_hdrp(self):
        """Verify recall_hdrp calculation."""
        hdrp_metrics = self._create_system_metrics("hdrp", raw_claims=10, verified_claims=7)
        react_metrics = self._create_system_metrics("react", raw_claims=10, verified_claims=5)
        
        result = ComparisonResult(
            query="test",
            query_id="q1",
            hdrp_metrics=hdrp_metrics,
            react_metrics=react_metrics,
        )
        
        # recall_hdrp = hdrp_verified / hdrp_raw = 7/10 = 0.7
        self.assertEqual(result.recall_hdrp, 0.7)

    def test_recall_react(self):
        """Verify recall_react calculation."""
        hdrp_metrics = self._create_system_metrics("hdrp", raw_claims=10, verified_claims=8)
        react_metrics = self._create_system_metrics("react", raw_claims=20, verified_claims=10)
        
        result = ComparisonResult(
            query="test",
            query_id="q1",
            hdrp_metrics=hdrp_metrics,
            react_metrics=react_metrics,
        )
        
        # recall_react = react_verified / react_raw = 10/20 = 0.5
        self.assertEqual(result.recall_react, 0.5)

    def test_entailment_advantage_hdrp(self):
        """Verify entailment_advantage_hdrp calculation."""
        hdrp_metrics = self._create_system_metrics("hdrp", entailment=0.8)
        react_metrics = self._create_system_metrics("react", entailment=0.5)
        
        result = ComparisonResult(
            query="test",
            query_id="q1",
            hdrp_metrics=hdrp_metrics,
            react_metrics=react_metrics,
        )
        
        # advantage = hdrp_entailment - react_entailment = 0.8 - 0.5 = 0.3
        self.assertAlmostEqual(result.entailment_advantage_hdrp, 0.3, places=5)

    def test_to_dict_includes_comparative_metrics(self):
        """Verify to_dict includes comparative metrics."""
        hdrp_metrics = self._create_system_metrics("hdrp")
        react_metrics = self._create_system_metrics("react")
        
        result = ComparisonResult(
            query="test",
            query_id="q1",
            hdrp_metrics=hdrp_metrics,
            react_metrics=react_metrics,
        )
        d = result.to_dict()
        
        self.assertIn("precision_hdrp_vs_react", d)
        self.assertIn("recall_hdrp", d)
        self.assertIn("recall_react", d)
        self.assertIn("entailment_advantage_hdrp", d)

    def test_get_winner_higher_is_better(self):
        """Verify get_winner for metrics where higher is better."""
        hdrp_metrics = self._create_system_metrics("hdrp")
        hdrp_metrics.quality.precision = 0.9
        
        react_metrics = self._create_system_metrics("react")
        react_metrics.quality.precision = 0.7
        
        result = ComparisonResult(
            query="test",
            query_id="q1",
            hdrp_metrics=hdrp_metrics,
            react_metrics=react_metrics,
        )
        
        winner = result.get_winner("quality", "precision")
        self.assertEqual(winner, "hdrp")

    def test_get_winner_lower_is_better(self):
        """Verify get_winner for metrics where lower is better."""
        hdrp_metrics = self._create_system_metrics("hdrp")
        hdrp_metrics.performance.total_execution_time_ms = 1000
        
        react_metrics = self._create_system_metrics("react")
        react_metrics.performance.total_execution_time_ms = 2000
        
        result = ComparisonResult(
            query="test",
            query_id="q1",
            hdrp_metrics=hdrp_metrics,
            react_metrics=react_metrics,
        )
        
        winner = result.get_winner("performance", "total_execution_time_ms")
        self.assertEqual(winner, "hdrp")

    def test_get_winner_tie(self):
        """Verify get_winner returns tie when equal."""
        hdrp_metrics = self._create_system_metrics("hdrp")
        hdrp_metrics.quality.precision = 0.8
        
        react_metrics = self._create_system_metrics("react")
        react_metrics.quality.precision = 0.8
        
        result = ComparisonResult(
            query="test",
            query_id="q1",
            hdrp_metrics=hdrp_metrics,
            react_metrics=react_metrics,
        )
        
        winner = result.get_winner("quality", "precision")
        self.assertEqual(winner, "tie")

    def test_get_winner_invalid_metric(self):
        """Verify get_winner handles invalid metric."""
        hdrp_metrics = self._create_system_metrics("hdrp")
        react_metrics = self._create_system_metrics("react")
        
        result = ComparisonResult(
            query="test",
            query_id="q1",
            hdrp_metrics=hdrp_metrics,
            react_metrics=react_metrics,
        )
        
        winner = result.get_winner("invalid", "metric")
        self.assertEqual(winner, "tie")


class TestAggregateComparison(unittest.TestCase):
    """Tests for AggregateComparison dataclass."""

    def _create_system_metrics(self, system_name):
        metrics = SystemMetrics(
            system_name=system_name,
            query="test query",
            run_id="run-1",
        )
        metrics.performance.total_execution_time_ms = 1000.0
        metrics.performance.search_calls_count = 5
        metrics.quality.total_claims_extracted = 10
        metrics.quality.verified_claims_count = 8
        metrics.quality.precision = 0.8
        metrics.quality.entailment_score = 0.75
        metrics.quality.avg_entailment_verified = 0.75
        metrics.quality.entailment_check = 0.6
        metrics.quality.unique_source_urls = 4
        metrics.trajectory.relevant_claims_ratio = 0.8
        metrics.trajectory.search_efficiency = 1.6
        metrics.hallucination.hallucination_risk_score = 0.1
        return metrics

    def _create_comparison_result(self, hdrp_verified=8, react_verified=5):
        hdrp = self._create_system_metrics("hdrp")
        hdrp.quality.verified_claims_count = hdrp_verified
        hdrp.quality.precision = 0.9
        
        react = self._create_system_metrics("react")
        react.quality.verified_claims_count = react_verified
        react.quality.precision = 0.5
        
        return ComparisonResult(
            query="test",
            query_id="q1",
            hdrp_metrics=hdrp,
            react_metrics=react,
        )

    def test_default_values(self):
        """Verify default values."""
        agg = AggregateComparison()
        self.assertEqual(agg.total_queries, 0)
        self.assertEqual(agg.hdrp_wins, 0)
        self.assertEqual(agg.react_wins, 0)
        self.assertEqual(agg.ties, 0)
        self.assertEqual(agg.comparison_results, [])

    def test_add_result_increments_count(self):
        """Verify add_result increments total_queries."""
        agg = AggregateComparison()
        result = self._create_comparison_result()
        
        agg.add_result(result)
        
        self.assertEqual(agg.total_queries, 1)
        self.assertEqual(len(agg.comparison_results), 1)

    def test_add_result_multiple(self):
        """Verify add_result works with multiple results."""
        agg = AggregateComparison()
        
        for i in range(5):
            result = self._create_comparison_result()
            agg.add_result(result)
        
        self.assertEqual(agg.total_queries, 5)
        self.assertEqual(len(agg.comparison_results), 5)

    def test_compute_win_rates_empty(self):
        """Verify compute_win_rates with no results."""
        agg = AggregateComparison()
        win_rates = agg.compute_win_rates()
        
        self.assertEqual(win_rates["hdrp"], 0)
        self.assertEqual(win_rates["react"], 0)
        self.assertEqual(win_rates["tie"], 0)

    def test_compute_win_rates_counts_correctly(self):
        """Verify compute_win_rates counts wins correctly."""
        agg = AggregateComparison()
        
        # Add results where HDRP should win (higher precision, entailment)
        for _ in range(3):
            result = self._create_comparison_result(hdrp_verified=10, react_verified=3)
            agg.add_result(result)
        
        win_rates = agg.compute_win_rates()
        
        # HDRP should win based on quality metrics
        self.assertGreater(win_rates["hdrp"] + win_rates["tie"], 0)

    def test_get_average_metrics_empty(self):
        """Verify get_average_metrics with no results."""
        agg = AggregateComparison()
        avgs = agg.get_average_metrics()
        
        self.assertEqual(avgs, {"hdrp": {}, "react": {}})

    def test_get_average_metrics_calculates_correctly(self):
        """Verify get_average_metrics calculates averages."""
        agg = AggregateComparison()
        
        for _ in range(2):
            result = self._create_comparison_result()
            agg.add_result(result)
        
        avgs = agg.get_average_metrics()
        
        self.assertIn("hdrp", avgs)
        self.assertIn("react", avgs)
        self.assertIn("avg_execution_time_ms", avgs["hdrp"])
        self.assertIn("avg_verified_claims", avgs["hdrp"])

    def test_get_average_metrics_includes_comparative_precision(self):
        """Verify get_average_metrics includes comparative precision."""
        agg = AggregateComparison()
        result = self._create_comparison_result()
        agg.add_result(result)
        
        avgs = agg.get_average_metrics()
        
        self.assertIn("avg_comparative_precision", avgs["hdrp"])


if __name__ == "__main__":
    unittest.main()

