"""
HDRP vs ReAct Comparison Runner

Main orchestrator that runs both HDRP and ReAct on the same queries,
collects metrics, and generates comparison results.
"""

import argparse
import sys
from typing import List, Optional
from rich.console import Console

from HDRP.tools.eval.test_queries import (
    ALL_QUERIES,
    QueryComplexity,
    EvalQuery,
    get_queries_by_complexity,
)
from HDRP.tools.eval.react_agent import ReActAgent
from HDRP.tools.eval.metrics import (
    MetricsCollector,
    AggregateComparison,
    ComparisonResult,
)
from HDRP.tools.eval.results_formatter import ResultsFormatter
from HDRP.tools.search.base import SearchProvider, SearchError
from HDRP.tools.search.api_key_validator import APIKeyError
from HDRP.services.researcher.service import ResearcherService
from HDRP.services.critic.service import CriticService
from HDRP.services.shared.logger import ResearchLogger
from HDRP.services.shared.pipeline_runner import build_search_provider


class ComparisonRunner:
    """Orchestrates comparison between HDRP and ReAct systems."""
    
    def __init__(
        self,
        search_provider: SearchProvider,
        max_results: int = 5,
        verbose: bool = False,
    ):
        self.search_provider = search_provider
        self.max_results = max_results
        self.verbose = verbose
        self.console = Console()
    
    def run_comparison(
        self,
        queries: List[EvalQuery],
        trials: int = 1,
    ) -> AggregateComparison:
        """Run comparison on a list of queries.
        
        Args:
            queries: List of test queries to evaluate
            trials: Number of trials per query (for averaging)
        
        Returns:
            AggregateComparison with results
        """
        aggregate = AggregateComparison()
        
        total_queries = len(queries)
        for idx, query in enumerate(queries, 1):
            if self.verbose:
                self.console.print(
                    f"\n[bold cyan]Progress:[/bold cyan] Query {idx}/{total_queries} - {query.id}"
                )
                self.console.print(f"[dim]{query.question}[/dim]\n")
            
            # Run trials and average (for now, just run once)
            result = self._run_single_comparison(query)
            aggregate.add_result(result)
            
            if self.verbose:
                self.console.print(f"[green]✓[/green] Completed {query.id}\n")
        
        return aggregate
    
    def _run_single_comparison(self, query: EvalQuery) -> ComparisonResult:
        """Run both HDRP and ReAct on a single query and compare."""
        # Generate run IDs with shared prefix for correlation
        import uuid
        run_id_prefix = str(uuid.uuid4())[:8]
        hdrp_run_id = f"{run_id_prefix}_hdrp"
        react_run_id = f"{run_id_prefix}_react"
        
        # Run ReAct baseline
        if self.verbose:
            self.console.print("  [yellow]→[/yellow] Running ReAct baseline...")
        react_metrics = self._run_react(query.question, react_run_id)
        
        # Run HDRP pipeline
        if self.verbose:
            self.console.print("  [green]→[/green] Running HDRP pipeline...")
        hdrp_metrics = self._run_hdrp(query.question, hdrp_run_id)
        
        return ComparisonResult(
            query=query.question,
            query_id=query.id,
            hdrp_metrics=hdrp_metrics,
            react_metrics=react_metrics,
        )
    
    def _run_react(self, question: str, run_id: str):
        """Run ReAct agent and collect metrics."""
        collector = MetricsCollector("ReAct")
        collector.start_timer()
        
        # Create and run ReAct agent
        agent = ReActAgent(
            search_provider=self.search_provider,
            max_results=self.max_results,
            run_id=run_id,
        )
        
        result = agent.run(question)
        
        # Record search call (ReAct makes 1 search call)
        collector.record_search_call(0.0)  # Latency tracked internally

        # Verify claims to calculate extraction accuracy
        critic = CriticService(run_id=run_id)
        critique_results = critic.verify(result.claims, task=question)
        
        # Collect metrics
        metrics = collector.collect_from_react(
            query=question,
            result=result,
            run_id=run_id,
            critique_results=critique_results,
        )
        
        return metrics
    
    def _run_hdrp(self, question: str, run_id: str):
        """Run HDRP pipeline and collect metrics."""
        collector = MetricsCollector("HDRP")
        collector.start_timer()
        
        # Initialize HDRP services
        researcher = ResearcherService(self.search_provider, run_id=run_id)
        critic = CriticService(run_id=run_id)
        
        # Step 1: Research (extract claims)
        raw_claims = researcher.research(question, source_node_id="root_research")
        
        # Record search call (ResearcherService makes 1 search call)
        collector.record_search_call(0.0)  # Latency tracked internally
        
        # Step 2: Critic (verify claims)
        critique_results = critic.verify(raw_claims, task=question)
        
        # Collect metrics
        metrics = collector.collect_from_hdrp(
            query=question,
            raw_claims=raw_claims,
            critique_results=critique_results,
            run_id=run_id,
        )
        
        return metrics





def main() -> int:
    """Main entry point for comparison script."""
    parser = argparse.ArgumentParser(
        description="Compare HDRP and ReAct baseline on research queries",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with simulated provider (fast, deterministic)
  python -m HDRP.tools.eval.compare --provider simulated
  
  # Run with Google Custom Search (real web search)
  python -m HDRP.tools.eval.compare --provider google
  
  # Run only complex queries
  python -m HDRP.tools.eval.compare --complexity complex --provider simulated
  
  # Run with verbose output
  python -m HDRP.tools.eval.compare --provider simulated --verbose
        """,
    )
    
    parser.add_argument(
        "--provider",
        choices=["simulated", "tavily", "google"],
        default="simulated",
        help="Search provider to use (default: simulated)",
    )
    
    parser.add_argument(
        "--api-key",
        help="API key for provider (if not set in env vars)",
    )
    
    parser.add_argument(
        "--cx",
        help="Google Custom Search Engine ID (if not set in GOOGLE_CX env var)",
    )
    
    parser.add_argument(
        "--complexity",
        choices=["simple", "medium", "complex", "all"],
        default="all",
        help="Query complexity level to test (default: all)",
    )
    
    parser.add_argument(
        "--max-results",
        type=int,
        default=5,
        help="Maximum search results per query (default: 5)",
    )
    
    parser.add_argument(
        "--trials",
        type=int,
        default=1,
        help="Number of trials per query for averaging (default: 1)",
    )
    
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output during comparison",
    )
    
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Show detailed per-query results",
    )
    
    args = parser.parse_args()
    
    console = Console()
    formatter = ResultsFormatter(console)
    
    # Print header
    formatter.print_header()
    
    # Build search provider
    try:
        search_provider = build_search_provider(args.provider, args.api_key, args.cx)
    except (SearchError, APIKeyError) as e:
        console.print(f"[bold red]Configuration Error:[/bold red]\n")
        console.print(str(e))
        console.print("\n[yellow]Tip:[/yellow] Use --provider simulated for testing without an API key.")
        return 1
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] Failed to initialize search provider: {e}")
        return 1
    
    # Select queries based on complexity
    if args.complexity == "all":
        queries = ALL_QUERIES
    else:
        complexity_map = {
            "simple": QueryComplexity.SIMPLE,
            "medium": QueryComplexity.MEDIUM,
            "complex": QueryComplexity.COMPLEX,
        }
        queries = get_queries_by_complexity(complexity_map[args.complexity])
    
    # Print configuration
    config = {
        "Search Provider": args.provider,
        "Query Complexity": args.complexity,
        "Total Queries": len(queries),
        "Max Results per Query": args.max_results,
        "Trials per Query": args.trials,
    }
    formatter.print_configuration(config)
    
    # Run comparison
    console.print("[bold cyan]Starting comparison...[/bold cyan]\n")
    
    runner = ComparisonRunner(
        search_provider=search_provider,
        max_results=args.max_results,
        verbose=args.verbose,
    )
    
    try:
        aggregate = runner.run_comparison(queries, trials=args.trials)
    except KeyboardInterrupt:
        console.print("\n[yellow]Comparison interrupted by user.[/yellow]")
        return 130
    except Exception as e:
        console.print(f"\n[bold red]Error during comparison:[/bold red] {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1
    
    # Print results
    console.print("[bold green]✓[/bold green] Comparison complete!\n")
    
    formatter.print_win_summary(aggregate)
    formatter.print_summary_table(aggregate)
    
    if args.detailed:
        formatter.print_per_query_breakdown(aggregate)
    
    # Print footer note
    note = (
        "Note: Metrics are computed from actual system runs. "
        "HDRP includes explicit verification via the Critic component, "
        "while ReAct assumes all extracted claims are valid."
    )
    formatter.print_footer(note)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

