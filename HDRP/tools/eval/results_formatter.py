"""
Results Formatter for HDRP vs ReAct Comparison

Provides Rich-formatted console output with tables, winner indicators,
and visual comparison of metrics.
"""

from typing import Dict, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from HDRP.tools.eval.metrics import AggregateComparison, ComparisonResult, SystemMetrics


class ResultsFormatter:
    """Formats comparison results for console output using Rich."""
    
    def __init__(self, console: Console = None):
        self.console = console or Console()
    
    def print_header(self, title: str = "HDRP vs ReAct Baseline Comparison") -> None:
        """Print a formatted header."""
        self.console.print()
        self.console.print(Panel.fit(
            f"[bold cyan]{title}[/bold cyan]",
            border_style="cyan",
        ))
        self.console.print()
    
    def print_summary_table(self, aggregate: AggregateComparison) -> None:
        """Print aggregate summary comparison table."""
        averages = aggregate.get_average_metrics()
        hdrp_avg = averages["hdrp"]
        react_avg = averages["react"]
        
        table = Table(title="📊 Aggregate Metrics Summary", show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="cyan", no_wrap=True)
        table.add_column("HDRP", justify="right", style="green")
        table.add_column("ReAct", justify="right", style="yellow")
        table.add_column("Winner", justify="center")
        
        # Performance metrics
        table.add_row(
            "Avg Execution Time (ms)",
            f"{hdrp_avg['avg_execution_time_ms']:.2f}",
            f"{react_avg['avg_execution_time_ms']:.2f}",
            self._get_winner_icon(
                hdrp_avg['avg_execution_time_ms'],
                react_avg['avg_execution_time_ms'],
                lower_is_better=True
            ),
        )
        
        table.add_row(
            "Avg Search Calls",
            f"{hdrp_avg['avg_search_calls']:.1f}",
            f"{react_avg['avg_search_calls']:.1f}",
            self._get_winner_icon(
                hdrp_avg['avg_search_calls'],
                react_avg['avg_search_calls'],
                lower_is_better=True
            ),
        )
        
        table.add_section()
        
        # Quality metrics
        table.add_row(
            "Avg Raw Claims",
            f"{hdrp_avg['avg_total_claims']:.1f}",
            f"{react_avg['avg_total_claims']:.1f}",
            self._get_winner_icon(
                hdrp_avg['avg_total_claims'],
                react_avg['avg_total_claims'],
                lower_is_better=False
            ),
        )
        
        table.add_row(
            "Avg Verified Claims",
            f"{hdrp_avg['avg_verified_claims']:.1f}",
            f"{react_avg['avg_verified_claims']:.1f}",
            self._get_winner_icon(
                hdrp_avg['avg_verified_claims'],
                react_avg['avg_verified_claims'],
                lower_is_better=False
            ),
        )
        
        table.add_row(
            "Avg Completeness/Accuracy",
            f"{hdrp_avg['avg_completeness']:.3f}",
            f"{react_avg['avg_completeness']:.3f}",
            self._get_winner_icon(
                hdrp_avg['avg_completeness'],
                react_avg['avg_completeness'],
                lower_is_better=False
            ),
        )

        table.add_row(
            "Avg Entailment Score",
            f"{hdrp_avg['avg_entailment_score']:.3f}",
            f"{react_avg['avg_entailment_score']:.3f}",
            self._get_winner_icon(
                hdrp_avg['avg_entailment_score'],
                react_avg['avg_entailment_score'],
                lower_is_better=False
            ),
        )

        # Comparative Precision (HDRP only)
        # Check if the key exists (it should based on my previous edit)
        comp_precision = hdrp_avg.get('avg_comparative_precision', 0.0)
        table.add_row(
            "Avg Comparative Precision",
            f"{comp_precision:.3f}",
            "N/A",
            "HDRP" # By definition specific to HDRP
        )
        
        table.add_row(
            "Avg Unique Sources",
            f"{hdrp_avg['avg_unique_sources']:.1f}",
            f"{react_avg['avg_unique_sources']:.1f}",
            self._get_winner_icon(
                hdrp_avg['avg_unique_sources'],
                react_avg['avg_unique_sources'],
                lower_is_better=False
            ),
        )
        
        table.add_section()
        
        # Trajectory metrics
        table.add_row(
            "Avg Relevant Claims Ratio",
            f"{hdrp_avg['avg_relevant_ratio']:.3f}",
            f"{react_avg['avg_relevant_ratio']:.3f}",
            self._get_winner_icon(
                hdrp_avg['avg_relevant_ratio'],
                react_avg['avg_relevant_ratio'],
                lower_is_better=False
            ),
        )
        
        table.add_row(
            "Avg Search Efficiency",
            f"{hdrp_avg['avg_search_efficiency']:.3f}",
            f"{react_avg['avg_search_efficiency']:.3f}",
            self._get_winner_icon(
                hdrp_avg['avg_search_efficiency'],
                react_avg['avg_search_efficiency'],
                lower_is_better=False
            ),
        )
        
        table.add_section()
        
        # Hallucination metrics
        table.add_row(
            "Avg Hallucination Risk",
            f"{hdrp_avg['avg_hallucination_risk']:.3f}",
            f"{react_avg['avg_hallucination_risk']:.3f}",
            self._get_winner_icon(
                hdrp_avg['avg_hallucination_risk'],
                react_avg['avg_hallucination_risk'],
                lower_is_better=True
            ),
        )
        
        self.console.print(table)
        self.console.print()
    
    def print_win_summary(self, aggregate: AggregateComparison) -> None:
        """Print overall win/loss summary."""
        win_rates = aggregate.compute_win_rates()
        total = aggregate.total_queries
        
        # Create win rate panel
        win_text = Text()
        win_text.append("Overall Query Winners:\n\n", style="bold")
        win_text.append(f"  HDRP:  {win_rates['hdrp']}/{total} queries ", style="green bold")
        win_text.append(f"({win_rates['hdrp']/total*100:.1f}%)\n", style="green")
        win_text.append(f"  ReAct: {win_rates['react']}/{total} queries ", style="yellow bold")
        win_text.append(f"({win_rates['react']/total*100:.1f}%)\n", style="yellow")
        win_text.append(f"  Ties:  {win_rates['tie']}/{total} queries ", style="dim")
        win_text.append(f"({win_rates['tie']/total*100:.1f}%)", style="dim")
        
        self.console.print(Panel(win_text, border_style="magenta", title="🏆 Win Summary"))
        self.console.print()
    
    def print_per_query_breakdown(self, aggregate: AggregateComparison) -> None:
        """Print detailed per-query comparison table."""
        table = Table(
            title="📋 Per-Query Breakdown",
            show_header=True,
            header_style="bold magenta"
        )
        table.add_column("Query ID", style="cyan", no_wrap=True)
        table.add_column("Complexity", style="dim")
        table.add_column("HDRP Claims", justify="right", style="green")
        table.add_column("ReAct Claims", justify="right", style="yellow")
        table.add_column("HDRP Sources", justify="right", style="green")
        table.add_column("ReAct Sources", justify="right", style="yellow")
        table.add_column("HDRP Time", justify="right", style="green")
        table.add_column("ReAct Time", justify="right", style="yellow")
        
        for result in aggregate.comparison_results:
            # Extract query complexity from query_id
            complexity = "?"
            if result.query_id.startswith("simple"):
                complexity = "S"
            elif result.query_id.startswith("medium"):
                complexity = "M"
            elif result.query_id.startswith("complex"):
                complexity = "C"
            
            table.add_row(
                result.query_id,
                complexity,
                str(result.hdrp_metrics.quality.verified_claims_count),
                str(result.react_metrics.quality.total_claims_extracted),
                str(result.hdrp_metrics.quality.unique_source_urls),
                str(result.react_metrics.quality.unique_source_urls),
                f"{result.hdrp_metrics.performance.total_execution_time_ms:.0f}ms",
                f"{result.react_metrics.performance.total_execution_time_ms:.0f}ms",
            )
        
        self.console.print(table)
        self.console.print()
    
    def print_detailed_query_result(self, result: ComparisonResult) -> None:
        """Print detailed metrics for a single query comparison."""
        self.console.print(f"\n[bold cyan]Query:[/bold cyan] {result.query}")
        self.console.print(f"[dim]ID: {result.query_id}[/dim]\n")
        
        # Create side-by-side comparison table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="cyan")
        table.add_column("HDRP", justify="right", style="green")
        table.add_column("ReAct", justify="right", style="yellow")
        table.add_column("Winner", justify="center")
        
        # Add metrics rows
        self._add_metric_row(
            table, "Execution Time (ms)",
            result.hdrp_metrics.performance.total_execution_time_ms,
            result.react_metrics.performance.total_execution_time_ms,
            lower_is_better=True
        )
        
        self._add_metric_row(
            table, "Search Calls",
            result.hdrp_metrics.performance.search_calls_count,
            result.react_metrics.performance.search_calls_count,
            lower_is_better=True
        )
        
        self._add_metric_row(
            table, "Total Claims",
            result.hdrp_metrics.quality.total_claims_extracted,
            result.react_metrics.quality.total_claims_extracted,
            lower_is_better=False
        )
        
        self._add_metric_row(
            table, "Verified Claims",
            result.hdrp_metrics.quality.verified_claims_count,
            result.react_metrics.quality.verified_claims_count,
            lower_is_better=False
        )
        
        self._add_metric_row(
            table, "Unique Sources",
            result.hdrp_metrics.quality.unique_source_urls,
            result.react_metrics.quality.unique_source_urls,
            lower_is_better=False
        )
        
        self._add_metric_row(
            table, "Relevant Claims Ratio",
            result.hdrp_metrics.trajectory.relevant_claims_ratio,
            result.react_metrics.trajectory.relevant_claims_ratio,
            lower_is_better=False,
            format_str="{:.3f}"
        )
        
        self._add_metric_row(
            table, "Hallucination Risk",
            result.hdrp_metrics.hallucination.hallucination_risk_score,
            result.react_metrics.hallucination.hallucination_risk_score,
            lower_is_better=True,
            format_str="{:.3f}"
        )
        
        self.console.print(table)
        self.console.print()
    
    def print_footer(self, note: str = None) -> None:
        """Print footer with optional note."""
        if note:
            self.console.print(Panel(note, border_style="dim", title="ℹ️  Note"))
        self.console.print()
    
    def _get_winner_icon(self, hdrp_val: float, react_val: float, lower_is_better: bool = False) -> str:
        """Get winner icon based on metric comparison."""
        if abs(hdrp_val - react_val) < 0.001:  # Essentially tied
            return "━"
        
        if lower_is_better:
            if hdrp_val < react_val:
                return "✓ HDRP"
            else:
                return "✓ ReAct"
        else:
            if hdrp_val > react_val:
                return "✓ HDRP"
            else:
                return "✓ ReAct"
    
    def _add_metric_row(
        self,
        table: Table,
        metric_name: str,
        hdrp_val: float,
        react_val: float,
        lower_is_better: bool = False,
        format_str: str = "{:.2f}"
    ) -> None:
        """Add a metric comparison row to a table."""
        table.add_row(
            metric_name,
            format_str.format(hdrp_val),
            format_str.format(react_val),
            self._get_winner_icon(hdrp_val, react_val, lower_is_better)
        )
    
    def print_configuration(self, config: Dict) -> None:
        """Print the comparison configuration."""
        config_text = Text()
        config_text.append("Configuration:\n", style="bold")
        for key, value in config.items():
            config_text.append(f"  {key}: ", style="dim")
            config_text.append(f"{value}\n", style="white")
        
        self.console.print(Panel(config_text, border_style="blue", title="⚙️  Settings"))
        self.console.print()

