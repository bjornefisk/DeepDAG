#!/usr/bin/env python3
"""
HDRP CLI

Typer/Rich-powered command-line interface for running the HDRP research
pipeline end-to-end using the Python services and pluggable search
providers (Google or simulated).
"""


import sys
from pathlib import Path

# Add project root to sys.path to support HDRP.* imports
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import os
import json
from datetime import datetime, timezone
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from HDRP.tools.search.factory import SearchFactory
from HDRP.tools.search.base import SearchError
from HDRP.tools.search.api_key_validator import APIKeyError
from HDRP.services.researcher.service import ResearcherService
from HDRP.services.critic.service import CriticService
from HDRP.services.synthesizer.service import SynthesizerService
from HDRP.services.shared.logger import ResearchLogger


console = Console()

# Path to artifacts directory
ARTIFACTS_DIR = Path(__file__).parent / "artifacts"

# Create app with run as the default callback
app = typer.Typer(help="HDRP research CLI")


def _save_report_artifacts(run_id: str, query: str, report: str, claims: list, critique_results: list):
    """
    Save report and metadata to the artifacts directory for dashboard access.
    
    Args:
        run_id: The run ID
        query: The original query
        report: The generated markdown report
        claims: List of all extracted claims
        critique_results: List of critique results
    """
    # Create run-specific directory
    run_dir = ARTIFACTS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    
    # Save report.md
    report_path = run_dir / "report.md"
    report_path.write_text(report, encoding='utf-8')
    
    # Build metadata
    verified_count = sum(1 for r in critique_results if r.is_valid)
    
    # Collect unique sources
    sources_dict = {}
    for claim in claims:
        url = getattr(claim, 'source_url', None)
        if url and url not in sources_dict:
            sources_dict[url] = {
                "url": url,
                "title": getattr(claim, 'source_title', 'Unknown'),
                "rank": len(sources_dict) + 1,
                "claims": 1
            }
        elif url:
            sources_dict[url]["claims"] += 1
    
    metadata = {
        "bundle_info": {
            "run_id": run_id,
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "query": query,
            "report_title": f"HDRP Research Report: {query}"
        },
        "statistics": {
            "total_claims": len(claims),
            "verified_claims": verified_count,
            "rejected_claims": len(critique_results) - verified_count,
            "unique_sources": len(sources_dict)
        },
        "sources": list(sources_dict.values()),
        "provenance": {
            "system": "HDRP",
            "version": "1.0.0",
            "pipeline": ["Researcher", "Critic", "Synthesizer"],
            "verification_enabled": True
        }
    }
    
    # Save metadata.json
    metadata_path = run_dir / "metadata.json"
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)


def _build_search_provider(
    provider: str,
    api_key: Optional[str],
) -> object:
    """
    Construct a search provider using the existing SearchFactory.

    - When provider == "google", prefer explicit api_key if given,
      otherwise fall back to GOOGLE_API_KEY env var.
    - When provider == "simulated", ignore api_key.
    - When provider is omitted, delegate to SearchFactory.from_env().
    """
    provider = (provider or "").strip().lower()

    if not provider:
        # Let factory decide based on HDRP_SEARCH_PROVIDER and friends.
        return SearchFactory.from_env()

    if provider == "google":
        # Explicit key wins; otherwise rely on settings
        effective_key = api_key
        if not effective_key:
            from HDRP.services.shared.settings import get_settings
            settings = get_settings()
            if settings.search.google.api_key:
                effective_key = settings.search.google.api_key.get_secret_value()
        return SearchFactory.get_provider("google", api_key=effective_key)

    if provider == "simulated":
        return SearchFactory.get_provider("simulated")

    raise SystemExit(f"Unknown provider '{provider}'. Use 'google' or 'simulated'.")



def _run_pipeline(
    query: str,
    provider: str,
    api_key: Optional[str],
    output_path: Optional[str],
    verbose: bool,
) -> int:
    """Execute the core HDRP research → critic → synthesize pipeline."""
    # Single run_id shared across components for joined logging.
    run_logger = ResearchLogger("cli")
    run_id = run_logger.run_id

    if verbose:
        console.print(f"[bold cyan][hdrp][/bold cyan] run_id={run_id}")
        console.print(f"[bold cyan][hdrp][/bold cyan] provider={provider or 'auto'}")

    # 1. Build search provider (Tavily or simulated).
    try:
        search_provider = _build_search_provider(provider, api_key)
    except SystemExit:
        # Re-raise to allow clean exit with message
        raise
    except (SearchError, APIKeyError) as exc:
        # API key validation errors get special formatting
        console.print(Panel.fit(
            f"[bold red]Configuration Error[/bold red]\n\n{exc}",
            border_style="red",
            title="[bold]HDRP Setup Required[/bold]",
        ))
        return 1
    except Exception as exc:
        console.print(
            f"[bold red][hdrp][/bold red] Failed to initialize search provider: {exc}"
        )
        return 1

    # 2. Initialize services.
    researcher = ResearcherService(search_provider, run_id=run_id)
    critic = CriticService(run_id=run_id)
    synthesizer = SynthesizerService()

    if verbose:
        console.print(f"[bold cyan][hdrp][/bold cyan] Researching: [italic]{query}[/italic]")

    # 3. Research.
    try:
        claims = researcher.research(query, source_node_id="root_research")
    except Exception as exc:
        console.print(f"[bold red][hdrp][/bold red] Research failed: {exc}")
        return 1

    if verbose:
        console.print(f"[bold cyan][hdrp][/bold cyan] Retrieved {len(claims)} raw claims")

    if not claims:
        console.print("[yellow]No information found for this query.[/yellow]")
        return 0

    # 4. Critic: verify claims.
    critique_results = critic.verify(claims, task=query)
    verified_count = sum(1 for r in critique_results if r.is_valid)

    if verbose:
        rejected_count = len(critique_results) - verified_count
        console.print(
            f"[bold cyan][hdrp][/bold cyan] Verified={verified_count}, "
            f"Rejected={rejected_count}"
        )

    # 5. Synthesize human-readable report.
    context = {
        "report_title": f"HDRP Research Report: {query}",
        "introduction": (
            "This report was generated by the Hierarchical Deep Research Planner (HDRP) "
            "pipeline using structured claims with explicit source traceability."
        ),
    }
    report = synthesizer.synthesize(critique_results, context=context)
    
    # 6. Save report artifacts to artifacts directory
    try:
        _save_report_artifacts(run_id, query, report, claims, critique_results)
        if verbose:
            console.print(f"[bold cyan][hdrp][/bold cyan] Artifacts saved to artifacts/{run_id}/")
    except Exception as e:
        if verbose:
            console.print(f"[yellow][hdrp][/yellow] Warning: Failed to save artifacts: {e}")

    if output_path:
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(report)
            if verbose:
                console.print(
                    Panel.fit(
                        f"Report written to [bold]{output_path}[/bold]",
                        border_style="green",
                    )
                )
        except OSError as exc:
            console.print(
                f"[bold red][hdrp][/bold red] Failed to write report to {output_path}: {exc}"
            )
            return 1
    else:
        # Print to stdout as plain text (no Rich markup parsing).
        console.print(report, markup=False)

    return 0




def _run_cli(
    query: str,
    mode: str,
    provider: Optional[str],
    api_key: Optional[str],
    output: Optional[str],
    verbose: bool,
) -> None:
    """Run a single HDRP research query."""
    provider_display = provider or "auto"
    mode_display = mode.upper()

    console.print(
        Panel.fit(
            f"[bold cyan]HDRP Research[/bold cyan]\n\n"
            f"[bold]Query:[/bold] {query}\n"
            f"[bold]Mode:[/bold] {mode_display}\n"
            f"[bold]Provider:[/bold] {provider_display}",
            border_style="cyan",
        )
    )

    if mode.lower() == "orchestrator":
        from HDRP.orchestrated_runner import run_orchestrated
        exit_code = run_orchestrated(
            query=query,
            provider=provider or "",
            api_key=api_key,
            output_path=output,
            verbose=verbose,
        )
    else:
        exit_code = _run_pipeline(
            query=query,
            provider=provider or "",
            api_key=api_key,
            output_path=output,
            verbose=verbose,
        )

    raise typer.Exit(code=exit_code)


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    query: Optional[str] = typer.Option(
        None,
        "--query",
        "-q",
        help="Research query or objective to investigate.",
    ),
    mode: str = typer.Option(
        "python",
        "--mode",
        "-m",
        help="Execution mode: 'python' (direct pipeline) or 'orchestrator' (Go DAG execution).",
    ),
    provider: Optional[str] = typer.Option(
        None,
        "--provider",
        "-p",
        help=(
            "Search provider to use ('google' or 'simulated'). "
            "If omitted, HDRP_SEARCH_PROVIDER/GOOGLE_* env vars are used."
        ),
    ),
    api_key: Optional[str] = typer.Option(
        None,
        "--api-key",
        help="Explicit API key for Google; overrides GOOGLE_API_KEY when set.",
    ),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="If provided, write the final report to this file instead of stdout.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose logging to the terminal.",
    ),
) -> None:
    """Run a single HDRP research query (default command)."""
    if ctx.invoked_subcommand is not None:
        return
    if query is None:
        raise typer.MissingParameter(param=ctx.command.params[0])
    _run_cli(query, mode, provider, api_key, output, verbose)


@app.command("run")
def run_command(
    query: str = typer.Option(
        ...,
        "--query",
        "-q",
        help="Research query or objective to investigate.",
    ),
    mode: str = typer.Option(
        "python",
        "--mode",
        "-m",
        help="Execution mode: 'python' (direct pipeline) or 'orchestrator' (Go DAG execution).",
    ),
    provider: Optional[str] = typer.Option(
        None,
        "--provider",
        "-p",
        help=(
            "Search provider to use ('google' or 'simulated'). "
            "If omitted, HDRP_SEARCH_PROVIDER/GOOGLE_* env vars are used."
        ),
    ),
    api_key: Optional[str] = typer.Option(
        None,
        "--api-key",
        help="Explicit API key for Google; overrides GOOGLE_API_KEY when set.",
    ),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="If provided, write the final report to this file instead of stdout.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose logging to the terminal.",
    ),
) -> None:
    """Run a single HDRP research query."""
    _run_cli(query, mode, provider, api_key, output, verbose)


def run_query_programmatic(
    query: str,
    provider: str = "",
    api_key: Optional[str] = None,
    verbose: bool = False,
    run_id: Optional[str] = None,
    progress_callback: Optional[callable] = None,
) -> dict:
    """
    Execute a query programmatically (for dashboard integration).
    
    Args:
        query: Research query to execute
        provider: Search provider ('google', 'simulated', or empty for auto)
        api_key: Optional API key
        verbose: Enable verbose logging
        run_id: Optional run ID (will generate if not provided)
        progress_callback: Optional callback(stage, percent) for progress updates
        
    Returns:

        dict: {"success": bool, "run_id": str, "report": str, "error": str}
    """
    # Initialize logger with provided or generated run_id
    run_logger = ResearchLogger("cli", run_id=run_id)
    actual_run_id = run_logger.run_id
    
    try:
        # Progress update helper
        def update_progress(stage: str, percent: float):
            if progress_callback:
                progress_callback(stage, percent)
        
        update_progress("Initializing search provider", 10)
        
        # Log the query immediately for dashboard visibility
        run_logger.log(
            "query_submitted",
            {"query": query, "provider": provider}
        )

        
        # Build search provider
        try:
            search_provider = _build_search_provider(provider, api_key)
        except (SearchError, APIKeyError) as exc:
            return {
                "success": False,
                "run_id": actual_run_id,
                "report": "",
                "error": f"Configuration Error: {exc}",
            }
        except Exception as exc:
            return {
                "success": False,
                "run_id": actual_run_id,
                "report": "",
                "error": f"Failed to initialize search provider: {exc}",
            }
        
        update_progress("Initializing services", 20)
        
        # Initialize services
        researcher = ResearcherService(search_provider, run_id=actual_run_id)
        critic = CriticService(run_id=actual_run_id)
        synthesizer = SynthesizerService()
        
        update_progress(f"Researching: {query}", 30)
        
        # Research
        try:
            claims = researcher.research(query, source_node_id="root_research")
        except Exception as exc:
            return {
                "success": False,
                "run_id": actual_run_id,
                "report": "",
                "error": f"Research failed: {exc}",
            }
        
        if not claims:
            return {
                "success": True,
                "run_id": actual_run_id,
                "report": "No information found for this query.",
                "error": "",
            }
        
        update_progress(f"Verifying {len(claims)} claims", 60)
        
        # Critic: verify claims
        critique_results = critic.verify(claims, task=query)
        verified_count = sum(1 for r in critique_results if r.is_valid)
        
        update_progress("Synthesizing final report", 80)
        
        # Synthesize report
        context = {
            "report_title": f"HDRP Research Report: {query}",
            "introduction": (
                "This report was generated by the Hierarchical Deep Research Planner (HDRP) "
                "pipeline using structured claims with explicit source traceability."
            ),
        }
        report = synthesizer.synthesize(critique_results, context=context)
        
        update_progress("Saving report artifacts", 90)
        
        # Save report and metadata to artifacts directory
        try:
            _save_report_artifacts(actual_run_id, query, report, claims, critique_results)
        except Exception as e:
            # Log but don't fail if artifact saving fails
            run_logger.log("artifact_save_failed", {"error": str(e)})
        
        update_progress("Completed", 100)
        
        return {
            "success": True,
            "run_id": actual_run_id,
            "report": report,
            "error": "",
            "stats": {
                "total_claims": len(claims),
                "verified_claims": verified_count,
                "rejected_claims": len(critique_results) - verified_count,
            }
        }
    
    except Exception as exc:
        return {
            "success": False,
            "run_id": actual_run_id,
            "report": "",
            "error": f"Unexpected error: {exc}",
        }


def main() -> None:
    """Entrypoint used by `python -m HDRP.cli` or a console_script."""
    app()


if __name__ == "__main__":
    main()