"""
Metrics Collection System for HDRP vs ReAct Comparison

This module provides comprehensive metric tracking for evaluating and comparing
research agent performance across multiple dimensions.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, timezone

from HDRP.services.shared.claims import AtomicClaim, CritiqueResult
from HDRP.tools.eval.react_agent import ReActRunResult


@dataclass
class PerformanceMetrics:
    """Performance and efficiency metrics."""
    
    total_execution_time_ms: float = 0.0
    search_api_latency_ms: float = 0.0
    search_calls_count: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "total_execution_time_ms": round(self.total_execution_time_ms, 2),
            "search_api_latency_ms": round(self.search_api_latency_ms, 2),
            "search_calls_count": self.search_calls_count,
        }


@dataclass
class QualityMetrics:
    """Quality and accuracy metrics.
    
    Tracks both raw extraction and verified claims separately to prevent
    conflating quantity with quality.
    """
    
    total_claims_extracted: int = 0
    raw_claims_extracted: int = 0
    verified_claims_count: int = 0
    completeness: float = 0.0  # verified / raw (recall: coverage of raw claims)
    precision: float = 0.0     # verified / total_possible (system accuracy)
    entailment_score: float = 0.0  # avg entailment of verified claims
    avg_entailment_verified: float = 0.0  # explicit avg entailment metric
    claims_per_source: float = 0.0
    unique_source_urls: int = 0
    entailment_check: float = 0.0  # % verified claims that answer original query
    
    def to_dict(self) -> Dict:
        return {
            "total_claims_extracted": self.total_claims_extracted,
            "raw_claims_extracted": self.raw_claims_extracted,
            "verified_claims_count": self.verified_claims_count,
            "completeness": round(self.completeness, 3),
            "precision": round(self.precision, 3),
            "entailment_score": round(self.entailment_score, 3),
            "avg_entailment_verified": round(self.avg_entailment_verified, 3),
            "claims_per_source": round(self.claims_per_source, 2),
            "unique_source_urls": self.unique_source_urls,
            "entailment_check": round(self.entailment_check, 3),
        }


@dataclass
class TrajectoryMetrics:
    """Trajectory efficiency and reasoning path metrics."""
    
    relevant_claims_ratio: float = 0.0  # verified / total
    search_efficiency: float = 0.0  # verified / search_calls
    
    def to_dict(self) -> Dict:
        return {
            "relevant_claims_ratio": round(self.relevant_claims_ratio, 3),
            "search_efficiency": round(self.search_efficiency, 3),
        }


@dataclass
class HallucinationMetrics:
    """Hallucination detection metrics (heuristic-based)."""
    
    claims_without_source: int = 0
    claims_with_missing_urls: int = 0
    hallucination_risk_score: float = 0.0  # 0-1 scale
    
    def to_dict(self) -> Dict:
        return {
            "claims_without_source": self.claims_without_source,
            "claims_with_missing_urls": self.claims_with_missing_urls,
            "hallucination_risk_score": round(self.hallucination_risk_score, 3),
        }


@dataclass
class SystemMetrics:
    """Complete metrics for a single system run."""
    
    system_name: str
    query: str
    run_id: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    
    performance: PerformanceMetrics = field(default_factory=PerformanceMetrics)
    quality: QualityMetrics = field(default_factory=QualityMetrics)
    trajectory: TrajectoryMetrics = field(default_factory=TrajectoryMetrics)
    hallucination: HallucinationMetrics = field(default_factory=HallucinationMetrics)
    
    def to_dict(self) -> Dict:
        return {
            "system_name": self.system_name,
            "query": self.query,
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "performance": self.performance.to_dict(),
            "quality": self.quality.to_dict(),
            "trajectory": self.trajectory.to_dict(),
            "hallucination": self.hallucination.to_dict(),
        }


class MetricsCollector:
    """Collects and computes comprehensive metrics from system runs."""
    
    def __init__(self, system_name: str):
        self.system_name = system_name
        self.start_time: Optional[float] = None
        self.search_latencies: List[float] = []
        self.search_call_count: int = 0
    
    def start_timer(self) -> None:
        """Start the execution timer."""
        self.start_time = time.time()
    
    def record_search_call(self, latency_ms: float) -> None:
        """Record a search API call with its latency."""
        self.search_call_count += 1
        self.search_latencies.append(latency_ms)
    
    def collect_from_react(
        self,
        query: str,
        result: ReActRunResult,
        run_id: str,
        critique_results: Optional[List[CritiqueResult]] = None,
    ) -> SystemMetrics:
        """Collect metrics from a ReAct agent run.
        
        IMPORTANT: ReAct claims are tracked separately from verified claims.
        Only counts verified_count if critique_results are passed AND verified.
        This prevents inflating metrics by counting unverified ReAct claims as verified.
        """
        execution_time_ms = (time.time() - self.start_time) * 1000 if self.start_time else 0.0
        
        # Extract claims and analyze
        claims = result.claims
        unique_sources = self._count_unique_sources(claims)
        
        # Calculate verification metrics ONLY if critique_results provided
        verified_count = 0
        verified_claims = []
        entailment_sum = 0.0
        high_entailment_count = 0
        
        if critique_results:
            # Only count claims that passed verification
            verified_results = [c for c in critique_results if c.is_valid]
            verified_claims = [c.claim for c in verified_results]
            verified_count = len(verified_claims)
            
            if verified_count > 0:
                entailment_sum = sum(c.entailment_score for c in verified_results)
                # Count claims with meaningful entailment (>0.4)
                high_entailment_count = sum(1 for c in verified_results if c.entailment_score >= 0.4)
        # else: no critique_results means verified_count stays 0 (don't assume all are verified)
        
        raw_count = len(claims)
        
        # PRECISION: % of ReAct claims that pass verification
        precision = verified_count / raw_count if raw_count > 0 else 0.0
        
        # RECALL: All ReAct claims are "recalled" - it's a raw measure
        # For ReAct, recall is just the raw count normalized
        recall = raw_count / raw_count if raw_count > 0 else 0.0
        
        avg_entailment = entailment_sum / verified_count if verified_count > 0 else 0.0
        entailment_check = high_entailment_count / verified_count if verified_count > 0 else 0.0
        
        # Performance metrics
        performance = PerformanceMetrics(
            total_execution_time_ms=execution_time_ms,
            search_api_latency_ms=sum(self.search_latencies),
            search_calls_count=self.search_call_count,
        )
        
        # Quality metrics - separated for ReAct
        quality = QualityMetrics(
            total_claims_extracted=raw_count,
            raw_claims_extracted=raw_count,
            verified_claims_count=verified_count,  # Only if verified via critique
            completeness=precision,  # For ReAct: % verified of total extracted
            precision=precision,  # ReAct precision: verified / raw
            entailment_score=avg_entailment,
            avg_entailment_verified=avg_entailment,
            claims_per_source=raw_count / unique_sources if unique_sources > 0 else 0.0,
            unique_source_urls=unique_sources,
            entailment_check=entailment_check,  # % verified claims answering query
        )
        
        # Trajectory metrics - use verified claims for efficiency metrics
        relevant_ratio = precision  # Use precision for consistency
        efficiency = verified_count / self.search_call_count if self.search_call_count > 0 else 0.0
        trajectory = TrajectoryMetrics(
            relevant_claims_ratio=relevant_ratio,
            search_efficiency=efficiency,
        )
        
        # Hallucination metrics - compute on verified claims if available
        hallucination_claims = verified_claims if verified_claims else claims
        hallucination = self._compute_hallucination_metrics(hallucination_claims)
        
        return SystemMetrics(
            system_name=self.system_name,
            query=query,
            run_id=run_id,
            performance=performance,
            quality=quality,
            trajectory=trajectory,
            hallucination=hallucination,
        )
    
    def collect_from_hdrp(
        self,
        query: str,
        raw_claims: List[AtomicClaim],
        critique_results: List[CritiqueResult],
        run_id: str,
    ) -> SystemMetrics:
        """Collect metrics from an HDRP pipeline run.
        
        Metrics are tracked separately:
        - raw_claims_extracted: Total claims extracted by HDRP
        - verified_claims_count: Claims that pass critic verification
        - Precision: verified_claims / raw_claims (quality of extraction)
        - Recall: verified_claims / total_possible (coverage)
        - Entailment: avg score of verified claims (relevance to query)
        """
        execution_time_ms = (time.time() - self.start_time) * 1000 if self.start_time else 0.0
        
        # Separate verified and rejected claims
        verified_results = [cr for cr in critique_results if cr.is_valid]
        verified_claims = [cr.claim for cr in verified_results]
        
        # Calculate entailment metrics
        entailment_sum = sum(cr.entailment_score for cr in verified_results)
        verified_count = len(verified_claims)
        raw_count = len(raw_claims)
        
        avg_entailment = entailment_sum / verified_count if verified_count > 0 else 0.0
        
        # PRECISION: What % of extracted claims are verified (quality metric)
        precision = verified_count / raw_count if raw_count > 0 else 0.0
        
        # RECALL: What % of raw claims are verified (coverage metric)
        # Note: Assumes all raw_claims should ideally be verified
        recall = verified_count / raw_count if raw_count > 0 else 0.0
        
        # ENTAILMENT CHECK: How many verified claims have high entailment (>0.4)?
        # This indicates they actually answer the query
        high_entailment_count = sum(1 for cr in verified_results if cr.entailment_score >= 0.4)
        entailment_check = high_entailment_count / verified_count if verified_count > 0 else 0.0
        
        # Count unique sources
        unique_sources_raw = self._count_unique_sources(raw_claims)
        unique_sources_verified = self._count_unique_sources(verified_claims)
        
        # Performance metrics
        performance = PerformanceMetrics(
            total_execution_time_ms=execution_time_ms,
            search_api_latency_ms=sum(self.search_latencies),
            search_calls_count=self.search_call_count,
        )
        
        # Quality metrics - now with separated tracking
        quality = QualityMetrics(
            total_claims_extracted=raw_count,
            raw_claims_extracted=raw_count,
            verified_claims_count=verified_count,
            completeness=recall,  # Keep for backward compatibility
            precision=precision,  # New: system's claim extraction quality
            entailment_score=avg_entailment,  # Keep for backward compatibility
            avg_entailment_verified=avg_entailment,  # Explicit metric
            claims_per_source=verified_count / unique_sources_verified if unique_sources_verified > 0 else 0.0,
            unique_source_urls=unique_sources_verified,
            entailment_check=entailment_check,  # % of verified claims answering query
        )
        
        # Trajectory metrics
        relevant_ratio = len(verified_claims) / len(raw_claims) if len(raw_claims) > 0 else 0.0
        trajectory = TrajectoryMetrics(
            relevant_claims_ratio=relevant_ratio,
            search_efficiency=len(verified_claims) / self.search_call_count if self.search_call_count > 0 else 0.0,
        )
        
        # Hallucination metrics (on verified claims)
        hallucination = self._compute_hallucination_metrics(verified_claims)
        
        return SystemMetrics(
            system_name=self.system_name,
            query=query,
            run_id=run_id,
            performance=performance,
            quality=quality,
            trajectory=trajectory,
            hallucination=hallucination,
        )
    
    def _count_unique_sources(self, claims: List[AtomicClaim]) -> int:
        """Count unique source URLs in claims."""
        urls = set()
        for claim in claims:
            if claim.source_url:
                urls.add(claim.source_url)
        return len(urls)
    
    def _compute_hallucination_metrics(self, claims: List[AtomicClaim]) -> HallucinationMetrics:
        """Compute heuristic hallucination indicators."""
        claims_without_source = 0
        claims_with_missing_urls = 0
        
        for claim in claims:
            if not claim.source_url:
                claims_without_source += 1
            elif not claim.source_url.startswith("http"):
                claims_with_missing_urls += 1
        
        # Compute risk score: percentage of claims with source issues
        total_claims = len(claims)
        if total_claims == 0:
            risk_score = 0.0
        else:
            risk_score = (claims_without_source + claims_with_missing_urls) / total_claims
        
        return HallucinationMetrics(
            claims_without_source=claims_without_source,
            claims_with_missing_urls=claims_with_missing_urls,
            hallucination_risk_score=risk_score,
        )


@dataclass
class ComparisonResult:
    """Results from comparing HDRP and ReAct on a single query.
    
    Now provides comprehensive precision, recall, and entailment metrics
    to properly assess quality vs quantity.
    """
    
    query: str
    query_id: str
    hdrp_metrics: SystemMetrics
    react_metrics: SystemMetrics
    
    @property
    def precision_hdrp_vs_react(self) -> float:
        """HDRP Precision: verified_hdrp / total_react.
        
        Measures: Of all ReAct's extracted claims, how many would HDRP 
        have verified? Shows HDRP's quality advantage.
        """
        react_raw = self.react_metrics.quality.raw_claims_extracted
        if react_raw == 0:
            return 0.0
        return self.hdrp_metrics.quality.verified_claims_count / react_raw
    
    @property
    def recall_hdrp(self) -> float:
        """HDRP Recall: verified_hdrp / raw_hdrp.
        
        Measures: Of HDRP's own extracted claims, what % are verified?
        Shows HDRP's extraction accuracy.
        """
        hdrp_raw = self.hdrp_metrics.quality.raw_claims_extracted
        if hdrp_raw == 0:
            return 0.0
        return self.hdrp_metrics.quality.verified_claims_count / hdrp_raw
    
    @property
    def recall_react(self) -> float:
        """ReAct Recall: verified_react / raw_react.
        
        Measures: Of ReAct's extracted claims, what % are verified?
        Shows ReAct's extraction accuracy.
        """
        react_raw = self.react_metrics.quality.raw_claims_extracted
        if react_raw == 0:
            return 0.0
        return self.react_metrics.quality.verified_claims_count / react_raw
    
    @property
    def entailment_advantage_hdrp(self) -> float:
        """Entailment Advantage: % HDRP verified claims vs ReAct verified.
        
        Measures: What % of HDRP's verified claims have strong entailment
        (answer the query) vs ReAct's?
        """
        hdrp_entailment = self.hdrp_metrics.quality.entailment_check
        react_entailment = self.react_metrics.quality.entailment_check
        return hdrp_entailment - react_entailment

    def to_dict(self) -> Dict:
        return {
            "query": self.query,
            "query_id": self.query_id,
            "hdrp": self.hdrp_metrics.to_dict(),
            "react": self.react_metrics.to_dict(),
            # Comparative metrics
            "precision_hdrp_vs_react": round(self.precision_hdrp_vs_react, 3),
            "recall_hdrp": round(self.recall_hdrp, 3),
            "recall_react": round(self.recall_react, 3),
            "entailment_advantage_hdrp": round(self.entailment_advantage_hdrp, 3),
        }
    
    def get_winner(self, metric_category: str, metric_name: str) -> str:
        """Determine which system performs better for a specific metric.
        
        Returns: "hdrp", "react", or "tie"
        """
        # Navigate nested metrics structure
        hdrp_val = self._get_metric_value(self.hdrp_metrics, metric_category, metric_name)
        react_val = self._get_metric_value(self.react_metrics, metric_category, metric_name)
        
        if hdrp_val is None or react_val is None:
            return "tie"
        
        # Lower is better for these metrics
        lower_is_better = [
            "total_execution_time_ms",
            "hallucination_risk_score",
            "claims_without_source",
            "claims_with_missing_urls",
        ]
        
        if metric_name in lower_is_better:
            if hdrp_val < react_val:
                return "hdrp"
            elif react_val < hdrp_val:
                return "react"
        else:
            # Higher is better
            if hdrp_val > react_val:
                return "hdrp"
            elif react_val > hdrp_val:
                return "react"
        
        return "tie"
    
    def _get_metric_value(self, metrics: SystemMetrics, category: str, name: str):
        """Extract a specific metric value from SystemMetrics."""
        category_obj = getattr(metrics, category, None)
        if category_obj is None:
            return None
        return getattr(category_obj, name, None)


@dataclass
class AggregateComparison:
    """Aggregate comparison results across multiple queries."""
    
    total_queries: int = 0
    hdrp_wins: int = 0
    react_wins: int = 0
    ties: int = 0
    
    comparison_results: List[ComparisonResult] = field(default_factory=list)
    
    def add_result(self, result: ComparisonResult) -> None:
        """Add a comparison result to the aggregate."""
        self.comparison_results.append(result)
        self.total_queries += 1
    
    def compute_win_rates(self) -> Dict[str, int]:
        """Compute win rates across all queries for quality metrics.
        
        Uses precision, recall, and entailment to avoid conflating
        quantity with quality.
        """
        win_counter = {"hdrp": 0, "react": 0, "tie": 0}
        
        # Define quality-focused metrics (exclude raw extraction counts)
        key_metrics = [
            ("quality", "verified_claims_count"),
            ("quality", "precision"),
            ("quality", "avg_entailment_verified"),
            ("quality", "entailment_check"),
            ("trajectory", "search_efficiency"),
            ("hallucination", "hallucination_risk_score"),
        ]
        
        for result in self.comparison_results:
            query_wins = {"hdrp": 0, "react": 0}
            for category, metric in key_metrics:
                winner = result.get_winner(category, metric)
                if winner in query_wins:
                    query_wins[winner] += 1
            
            # Determine overall query winner (best quality, not quantity)
            if query_wins["hdrp"] > query_wins["react"]:
                win_counter["hdrp"] += 1
            elif query_wins["react"] > query_wins["hdrp"]:
                win_counter["react"] += 1
            else:
                win_counter["tie"] += 1
        
        return win_counter
    
    def get_average_metrics(self) -> Dict[str, Dict]:
        """Compute average metrics for both systems."""
        if not self.comparison_results:
            return {"hdrp": {}, "react": {}}
        
        hdrp_totals = self._initialize_totals()
        react_totals = self._initialize_totals()
        total_precision = 0.0
        
        for result in self.comparison_results:
            self._add_to_totals(hdrp_totals, result.hdrp_metrics)
            self._add_to_totals(react_totals, result.react_metrics)
            total_precision += result.precision_hdrp_vs_react
        
        n = len(self.comparison_results)
        avgs = {
            "hdrp": self._compute_averages(hdrp_totals, n),
            "react": self._compute_averages(react_totals, n),
        }
        # Inject comparative average precision into HDRP stats (or separate)
        avgs["hdrp"]["avg_comparative_precision"] = round(total_precision / n, 3)
        return avgs
    
    def _initialize_totals(self) -> Dict:
        """Initialize totals dictionary for averaging."""
        return {
            "execution_time": 0.0,
            "search_calls": 0,
            "total_claims": 0,
            "verified_claims": 0,
            "unique_sources": 0,
            "relevant_ratio": 0.0,
            "search_efficiency": 0.0,
            "hallucination_risk": 0.0,
            "completeness": 0.0,
            "entailment_score": 0.0,
        }
    
    def _add_to_totals(self, totals: Dict, metrics: SystemMetrics) -> None:
        """Add metrics to running totals."""
        totals["execution_time"] += metrics.performance.total_execution_time_ms
        totals["search_calls"] += metrics.performance.search_calls_count
        totals["total_claims"] += metrics.quality.total_claims_extracted
        totals["verified_claims"] += metrics.quality.verified_claims_count
        totals["unique_sources"] += metrics.quality.unique_source_urls
        totals["relevant_ratio"] += metrics.trajectory.relevant_claims_ratio
        totals["search_efficiency"] += metrics.trajectory.search_efficiency
        totals["hallucination_risk"] += metrics.hallucination.hallucination_risk_score
        totals["completeness"] += metrics.quality.completeness
        totals["entailment_score"] += metrics.quality.entailment_score
    
    def _compute_averages(self, totals: Dict, n: int) -> Dict:
        """Compute averages from totals."""
        return {
            "avg_execution_time_ms": round(totals["execution_time"] / n, 2),
            "avg_search_calls": round(totals["search_calls"] / n, 1),
            "avg_total_claims": round(totals["total_claims"] / n, 1),
            "avg_verified_claims": round(totals["verified_claims"] / n, 1),
            "avg_unique_sources": round(totals["unique_sources"] / n, 1),
            "avg_relevant_ratio": round(totals["relevant_ratio"] / n, 3),
            "avg_search_efficiency": round(totals["search_efficiency"] / n, 3),
            "avg_hallucination_risk": round(totals["hallucination_risk"] / n, 3),
            "avg_completeness": round(totals["completeness"] / n, 3),
            "avg_entailment_score": round(totals["entailment_score"] / n, 3),
        }

