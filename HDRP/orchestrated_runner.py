#!/usr/bin/env python3
"""Orchestrated Pipeline Runner.

Manages Python gRPC service lifecycle and communicates with Go orchestrator.

DEPRECATED: Most logic has been moved to services.shared.pipeline_runner.OrchestratedPipelineRunner.
This module now provides thin backward-compatible wrappers.
"""

from typing import Optional
from rich.console import Console
from HDRP.services.shared.pipeline_runner import OrchestratedPipelineRunner

console = Console()


def run_orchestrated(
    query: str,
    provider: str,
    api_key: Optional[str],
    output_path: Optional[str],
    verbose: bool
) -> int:
    """Runs a query through the Go orchestrator.
    
    DEPRECATED: This is now a thin wrapper around OrchestratedPipelineRunner.
    
    Args:
        query: Research query
        provider: Search provider type
        api_key: Optional API key
        output_path: Optional output file path
        verbose: Enable verbose logging
        
    Returns:
        Exit code (0=success, 1=failure)
    """
    runner = OrchestratedPipelineRunner(
        provider=provider,
        api_key=api_key,
        verbose=verbose,
    )
    
    result = runner.execute(query=query, output_path=output_path)
    
    # CLI-style output for orchestrated mode
    if not result["success"]:
        console.print(f"[bold red]Error:[/bold red] {result['error']}")
        return 1
    
    if not output_path and result["report"]:
        console.print(result["report"], markup=False)
    
    return 0


def run_orchestrated_programmatic(
    query: str,
    provider: str = "",
    api_key: Optional[str] = None,
    verbose: bool = False,
    run_id: Optional[str] = None,
    progress_callback: Optional[callable] = None,
) -> dict:
    """Execute query through Go orchestrator (for dashboard integration).
    
    DEPRECATED: This is now a thin wrapper around OrchestratedPipelineRunner.
    
    Args:
        query: Research query to execute
        provider: Search provider
        api_key: Optional API key
        verbose: Enable verbose logging
        run_id: Optional run ID
        progress_callback: Optional callback(stage, percent) for progress updates
        
    Returns:
        dict: {"success": bool, "run_id": str, "report": str, "error": str}
    """
    runner = OrchestratedPipelineRunner(
        provider=provider,
        api_key=api_key,
        verbose=verbose,
        run_id=run_id,
        progress_callback=progress_callback,
    )
    
    return runner.execute(query=query)
