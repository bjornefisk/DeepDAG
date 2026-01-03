"""
Metrics Collection System for HDRP vs ReAct Comparison

This module provides comprehensive metric tracking for evaluating and comparing
research agent performance across multiple dimensions.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime

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
    """Quality and accuracy metrics."""
    
    total_claims_extracted: int = 0
    verified_claims_count: int = 0
    claims_per_source: float = 0.0
    unique_source_urls: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "total_claims_extracted": self.total_claims_extracted,
            "verified_claims_count": self.verified_claims_count,
            "claims_per_source": round(self.claims_per_source, 2),
            "unique_source_urls": self.unique_source_urls,
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
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
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
    ) -> SystemMetrics:
        """Collect metrics from a ReAct agent run."""
        execution_time_ms = (time.time() - self.start_time) * 1000 if self.start_time else 0.0
        
        # Extract claims and analyze
        claims = result.claims
        unique_sources = self._count_unique_sources(claims)
        
        # Performance metrics
        performance = PerformanceMetrics(
            total_execution_time_ms=execution_time_ms,
            search_api_latency_ms=sum(self.search_latencies),
            search_calls_count=self.search_call_count,
        )
        
        # Quality metrics
        quality = QualityMetrics(
            total_claims_extracted=len(claims),
            verified_claims_count=len(claims),  # ReAct has no separate verification
            claims_per_source=len(claims) / unique_sources if unique_sources > 0 else 0.0,
            unique_source_urls=unique_sources,
        )
        
        # Trajectory metrics
        trajectory = TrajectoryMetrics(
            relevant_claims_ratio=1.0,  # ReAct assumes all claims are relevant
            search_efficiency=len(claims) / self.search_call_count if self.search_call_count > 0 else 0.0,
        )
        
        # Hallucination metrics
        hallucination = self._compute_hallucination_metrics(claims)
        
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
        """Collect metrics from an HDRP pipeline run."""
        execution_time_ms = (time.time() - self.start_time) * 1000 if self.start_time else 0.0
        
        # Separate verified and rejected claims
        verified_claims = [cr.claim for cr in critique_results if cr.is_valid]
        
        # Count unique sources
        unique_sources_raw = self._count_unique_sources(raw_claims)
        unique_sources_verified = self._count_unique_sources(verified_claims)
        
        # Performance metrics
        performance = PerformanceMetrics(
            total_execution_time_ms=execution_time_ms,
            search_api_latency_ms=sum(self.search_latencies),
            search_calls_count=self.search_call_count,
        )
        
        # Quality metrics
        quality = QualityMetrics(
            total_claims_extracted=len(raw_claims),
            verified_claims_count=len(verified_claims),
            claims_per_source=len(verified_claims) / unique_sources_verified if unique_sources_verified > 0 else 0.0,
            unique_source_urls=unique_sources_verified,
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
    """Results from comparing HDRP and ReAct on a single query."""
    
    query: str
    query_id: str
    hdrp_metrics: SystemMetrics
    react_metrics: SystemMetrics
    
    def to_dict(self) -> Dict:
        return {
            "query": self.query,
            "query_id": self.query_id,
            "hdrp": self.hdrp_metrics.to_dict(),
            "react": self.react_metrics.to_dict(),
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
        """Compute win rates across all queries for key metrics."""
        win_counter = {"hdrp": 0, "react": 0, "tie": 0}
        
        # Define key metrics to evaluate
        key_metrics = [
            ("quality", "verified_claims_count"),
            ("quality", "unique_source_urls"),
            ("trajectory", "relevant_claims_ratio"),
            ("trajectory", "search_efficiency"),
            ("hallucination", "hallucination_risk_score"),
        ]
        
        for result in self.comparison_results:
            query_wins = {"hdrp": 0, "react": 0}
            for category, metric in key_metrics:
                winner = result.get_winner(category, metric)
                if winner in query_wins:
                    query_wins[winner] += 1
            
            # Determine overall query winner
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
        
        for result in self.comparison_results:
            self._add_to_totals(hdrp_totals, result.hdrp_metrics)
            self._add_to_totals(react_totals, result.react_metrics)
        
        n = len(self.comparison_results)
        return {
            "hdrp": self._compute_averages(hdrp_totals, n),
            "react": self._compute_averages(react_totals, n),
        }
    
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
        }

