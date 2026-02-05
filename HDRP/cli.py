#!/usr/bin/env python3
"""
HDRP CLI

Typer/Rich-powered command-line interface for running the HDRP research
pipeline end-to-end using the Python services and pluggable search
providers (Google or simulated).
"""


from pathlib import Path

import os
import json
from datetime import datetime, timezone
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from HDRP.tools.search.base import SearchError
from HDRP.tools.search.api_key_validator import APIKeyError
from HDRP.services.shared.pipeline_runner import (
    build_search_provider,
    PipelineRunner,
    OrchestratedPipelineRunner,
)


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


# _build_search_provider moved to services.shared.pipeline_runner



def execute_pipeline(
    query: str,
    provider: str = "",
    api_key: Optional[str] = None,
    output_path: Optional[str] = None,
    verbose: bool = False,
    run_id: Optional[str] = None,
    progress_callback: Optional[callable] = None,
    return_dict: bool = False,
) -> dict:
    """Core pipeline execution logic used by both CLI and programmatic interfaces.
    
    Args:
        query: Research query to execute
        provider: Search provider ('google', 'simulated', or empty for auto)
        api_key: Optional API key
        output_path: Optional path to write report file
        verbose: Enable verbose logging
        run_id: Optional run ID (will generate if not provided)
        progress_callback: Optional callback(stage, percent) for progress updates
        return_dict: If True, return dict; if False, return exit code
        
    Returns:
        If return_dict=True: {"success": bool, "run_id": str, "report": str, "error": str, "stats": {...}}
        If return_dict=False: int exit code (0=success, 1=failure)
    """
    # Build search provider
    try:
        search_provider = build_search_provider(provider, api_key)
    except SystemExit:
        # Re-raise to allow clean exit with message (CLI only)
        if not return_dict:
            raise
        return {
            "success": False,
            "run_id": run_id or "",
            "report": "",
            "error": f"Unknown provider '{provider}'",
        }
    except (SearchError, APIKeyError) as exc:
        error_msg = f"Configuration Error: {exc}"
        if not return_dict:
            console.print(Panel.fit(
                f"[bold red]Configuration Error[/bold red]\\n\\n{exc}",
                border_style="red",
                title="[bold]HDRP Setup Required[/bold]",
            ))
            return 1
        return {
            "success": False,
            "run_id": run_id or "",
            "report": "",
            "error": error_msg,
        }
    except Exception as exc:
        error_msg = f"Failed to initialize search provider: {exc}"
        if not return_dict:
            console.print(f"[bold red][hdrp][/bold red] {error_msg}")
            return 1
        return {
            "success": False,
            "run_id": run_id or "",
            "report": "",
            "error": error_msg,
        }
    
    # Use unified PipelineRunner
    runner = PipelineRunner(
        search_provider=search_provider,
        run_id=run_id,
        verbose=verbose,
        progress_callback=progress_callback,
    )
    
    result = runner.execute(query=query, output_path=output_path)
    
    # Handle CLI-specific output formatting
    if not return_dict:
        if not result["success"]:
            return 1
        if not output_path and result["report"]:
            # Print to stdout as plain text (no Rich markup parsing) - CLI only
            console.print(result["report"], markup=False)
        return 0
    
    return result


def _run_cli(
    query: str,
    mode: str,
    provider: Optional[str],
    api_key: Optional[str],
    output: Optional[str],
    verbose: bool,
) -> None:
    """Run a single HDRP research query (CLI wrapper)."""
    provider_display = provider or "auto"
    mode_display = mode.upper()

    console.print(
        Panel.fit(
            f"[bold cyan]HDRP Research[/bold cyan]\\n\\n"
            f"[bold]Query:[/bold] {query}\\n"
            f"[bold]Mode:[/bold] {mode_display}\\n"
            f"[bold]Provider:[/bold] {provider_display}",
            border_style="cyan",
        )
    )

    if mode.lower() == "orchestrator":
        # Use unified OrchestratedPipelineRunner
        runner = OrchestratedPipelineRunner(
            provider=provider or "",
            api_key=api_key,
            verbose=verbose,
        )
        result = runner.execute(query=query, output_path=output)
        
        # Print results for CLI
        if not result["success"]:
            console.print(f"[bold red]Error:[/bold red] {result['error']}")
            exit_code = 1
        else:
            if not output and result["report"]:
                console.print(result["report"], markup=False)
            exit_code = 0
    else:
        exit_code = execute_pipeline(
            query=query,
            provider=provider or "",
            api_key=api_key,
            output_path=output,
            verbose=verbose,
            return_dict=False,
        )

    raise typer.Exit(code=exit_code)


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
    return execute_pipeline(
        query=query,
        provider=provider,
        api_key=api_key,
        verbose=verbose,
        run_id=run_id,
        progress_callback=progress_callback,
        return_dict=True,
    )


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


def main() -> None:
    """Entrypoint used by `python -m HDRP.cli` or a console_script."""
    app()


if __name__ == "__main__":
    main()