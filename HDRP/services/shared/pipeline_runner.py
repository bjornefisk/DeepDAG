#!/usr/bin/env python3
"""
Unified Pipeline Runner

Consolidates pipeline execution logic from cli.py, orchestrated_runner.py,
and benchmark scripts to eliminate code duplication.
"""

import os
import sys
import time
import json
import subprocess
import requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Callable

from rich.console import Console

from HDRP.tools.search.factory import SearchFactory
from HDRP.tools.search.base import SearchProvider, SearchError
from HDRP.tools.search.api_key_validator import APIKeyError
from HDRP.services.researcher.service import ResearcherService
from HDRP.services.critic.service import CriticService
from HDRP.services.synthesizer.service import SynthesizerService
from HDRP.services.shared.logger import ResearchLogger
from HDRP.services.shared.errors import HDRPError, format_user_error, report_error


# Path to artifacts directory
ARTIFACTS_DIR = Path(__file__).parent.parent / "artifacts"


def build_search_provider(
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    cx: Optional[str] = None,
) -> SearchProvider:
    """
    Build a search provider using the existing SearchFactory.
    
    Consolidates logic from:
    - cli.py:_build_search_provider
    - benchmark.py:_build_search_provider
    - compare.py:_build_search_provider
    
    Args:
        provider: Provider type ('google', 'tavily', 'simulated', or None for auto)
        api_key: Optional API key
        cx: Optional Google Custom Search Engine ID
    
    Returns:
        SearchProvider instance
    
    Raises:
        SystemExit: If provider is unknown
        SearchError: If provider configuration fails
        APIKeyError: If API key is invalid
    """
    provider_type = (provider or "").strip().lower()

    if not provider_type:
        # Let factory decide based on HDRP_SEARCH_PROVIDER and friends
        return SearchFactory.from_env()

    if provider_type == "google":
        # Explicit key wins; otherwise rely on settings
        effective_key = api_key
        if not effective_key:
            from HDRP.services.shared.settings import get_settings
            settings = get_settings()
            if settings.search.google.api_key:
                effective_key = settings.search.google.api_key.get_secret_value()
        
        provider_kwargs = {}
        if cx:
            provider_kwargs["cx"] = cx
        return SearchFactory.get_provider("google", api_key=effective_key, **provider_kwargs)

    if provider_type == "simulated":
        return SearchFactory.get_provider("simulated")

    if provider_type == "tavily":
        if api_key:
            return SearchFactory.get_provider("tavily", api_key=api_key)
        else:
            # Will use TAVILY_API_KEY from env
            return SearchFactory.from_env(default_provider="tavily")

    raise SystemExit(f"Unknown provider '{provider}'. Use 'google', 'tavily', or 'simulated'.")


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


class PipelineRunner:
    """
    Unified pipeline runner for direct Python execution.
    
    Consolidates logic from cli.py:execute_pipeline.
    """
    
    def __init__(
        self,
        search_provider: SearchProvider,
        run_id: Optional[str] = None,
        verbose: bool = False,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ):
        """
        Initialize pipeline runner.
        
        Args:
            search_provider: SearchProvider instance
            run_id: Optional run ID (will generate if not provided)
            verbose: Enable verbose logging
            progress_callback: Optional callback(stage, percent) for progress updates
        """
        self.search_provider = search_provider
        self.verbose = verbose
        self.progress_callback = progress_callback
        self.console = Console()
        
        # Initialize logger with provided or generated run_id
        self.logger = ResearchLogger("pipeline_runner", run_id=run_id)
        self.run_id = self.logger.run_id
    
    def _update_progress(self, stage: str, percent: float):
        """Update progress if callback is set."""
        if self.progress_callback:
            self.progress_callback(stage, percent)
    
    def execute(
        self,
        query: str,
        output_path: Optional[str] = None,
    ) -> dict:
        """
        Execute the pipeline.
        
        Args:
            query: Research query to execute
            output_path: Optional path to write report file
            
        Returns:
            dict: {
                "success": bool,
                "run_id": str,
                "report": str,
                "error": str,
                "stats": {...}  # Only on success
            }
        """
        try:
            if self.verbose:
                self.console.print(f"[bold cyan][hdrp][/bold cyan] run_id={self.run_id}")
            
            self._update_progress("Initializing pipeline", 10)
            
            # Log the query for dashboard visibility
            self.logger.log("query_submitted", {"query": query})
            
            # Initialize services
            self._update_progress("Initializing services", 20)
            researcher = ResearcherService(self.search_provider, run_id=self.run_id)
            critic = CriticService(run_id=self.run_id)
            synthesizer = SynthesizerService()
            
            if self.verbose:
                self.console.print(f"[bold cyan][hdrp][/bold cyan] Researching: [italic]{query}[/italic]")
            
            self._update_progress(f"Researching: {query}", 30)
            
            # Step 1: Research
            try:
                claims = researcher.research(query, source_node_id="root_research")
            except Exception as exc:
                error_msg = f"Research failed: {exc}"
                self.console.print(f"[bold red][hdrp][/bold red] {error_msg}")
                return {
                    "success": False,
                    "run_id": self.run_id,
                    "report": "",
                    "error": error_msg,
                }
            
            if self.verbose:
                self.console.print(f"[bold cyan][hdrp][/bold cyan] Retrieved {len(claims)} raw claims")
            
            if not claims:
                no_results_msg = "No information found for this query."
                if self.verbose:
                    self.console.print(f"[yellow]{no_results_msg}[/yellow]")
                return {
                    "success": True,
                    "run_id": self.run_id,
                    "report": no_results_msg,
                    "error": "",
                }
            
            self._update_progress(f"Verifying {len(claims)} claims", 60)
            
            # Step 2: Critic - verify claims
            critique_results = critic.verify(claims, task=query)
            verified_count = sum(1 for r in critique_results if r.is_valid)
            
            if self.verbose:
                rejected_count = len(critique_results) - verified_count
                self.console.print(
                    f"[bold cyan][hdrp][/bold cyan] Verified={verified_count}, "
                    f"Rejected={rejected_count}"
                )
            
            self._update_progress("Synthesizing final report", 80)
            
            # Step 3: Synthesize human-readable report
            context = {
                "report_title": f"HDRP Research Report: {query}",
                "introduction": (
                    "This report was generated by the Hierarchical Deep Research Planner (HDRP) "
                    "pipeline using structured claims with explicit source traceability."
                ),
            }
            report = synthesizer.synthesize(critique_results, context=context)
            
            self._update_progress("Saving report artifacts", 90)
            
            # Step 4: Save report artifacts
            try:
                _save_report_artifacts(self.run_id, query, report, claims, critique_results)
                if self.verbose:
                    self.console.print(f"[bold cyan][hdrp][/bold cyan] Artifacts saved to artifacts/{self.run_id}/")
            except Exception as e:
                if self.verbose:
                    self.console.print(f"[yellow][hdrp][/yellow] Warning: Failed to save artifacts: {e}")
                self.logger.log("artifact_save_failed", {"error": str(e)})
            
            # Step 5: Output report
            if output_path:
                try:
                    with open(output_path, "w", encoding="utf-8") as f:
                        f.write(report)
                    if self.verbose:
                        self.console.print(f"[green]Report written to {output_path}[/green]")
                except OSError as exc:
                    error_msg = f"Failed to write report to {output_path}: {exc}"
                    self.console.print(f"[bold red][hdrp][/bold red] {error_msg}")
                    return {
                        "success": False,
                        "run_id": self.run_id,
                        "report": report,
                        "error": error_msg,
                    }
            
            self._update_progress("Completed", 100)
            
            # Return success
            return {
                "success": True,
                "run_id": self.run_id,
                "report": report,
                "error": "",
                "stats": {
                    "total_claims": len(claims),
                    "verified_claims": verified_count,
                    "rejected_claims": len(critique_results) - verified_count,
                }
            }
        
        except Exception as exc:
            error_msg = f"Unexpected error: {exc}"
            self.console.print(f"[bold red][hdrp][/bold red] {error_msg}")
            return {
                "success": False,
                "run_id": self.run_id,
                "report": "",
                "error": error_msg,
            }


class OrchestratedPipelineRunner:
    """
    Unified pipeline runner for Go orchestrator execution.
    
    Consolidates logic from orchestrated_runner.py:run_orchestrated and
    run_orchestrated_programmatic.
    """
    
    def __init__(
        self,
        provider: str = "",
        api_key: Optional[str] = None,
        verbose: bool = False,
        run_id: Optional[str] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ):
        """
        Initialize orchestrated pipeline runner.
        
        Args:
            provider: Search provider type
            api_key: Optional API key
            verbose: Enable verbose logging
            run_id: Optional run ID
            progress_callback: Optional callback(stage, percent) for progress updates
        """
        self.provider = provider
        self.api_key = api_key
        self.verbose = verbose
        self.run_id = run_id
        self.progress_callback = progress_callback
        self.console = Console()
        
        self.services = []
        self.orchestrator_proc = None
    
    def _update_progress(self, stage: str, percent: float):
        """Update progress if callback is set."""
        if self.progress_callback:
            self.progress_callback(stage, percent)
    
    def _start_service_server(self, service_name: str, port: int, script_path: str) -> subprocess.Popen:
        """Starts a Python gRPC service server in the background."""
        cmd = [sys.executable, script_path, "--port", str(port)]
        
        if self.verbose:
            self.console.print(f"[cyan]Starting {service_name} service on port {port}...[/cyan]")
        
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Give it a moment to start
        time.sleep(1)
        
        if proc.poll() is not None:
            stdout, stderr = proc.communicate()
            raise RuntimeError(f"{service_name} failed to start:\n{stderr}")
        
        return proc
    
    def _wait_for_service(self, host: str, port: int, timeout: int = 10) -> bool:
        """Waits for a service to become available."""
        import socket
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex((host, port))
                sock.close()
                
                if result == 0:
                    return True
            except Exception:
                pass
            
            time.sleep(0.5)
        
        return False
    
    def execute(
        self,
        query: str,
        output_path: Optional[str] = None,
    ) -> dict:
        """
        Execute the pipeline through Go orchestrator.
        
        Args:
            query: Research query to execute
            output_path: Optional path to write report file
            
        Returns:
            dict: {
                "success": bool,
                "run_id": str,
                "report": str,
                "error": str
            }
        """
        try:
            # Progress update helper
            self._update_progress("Setting up environment", 5)
            
            # Set environment variables
            if self.provider:
                os.environ["HDRP_SEARCH_PROVIDER"] = self.provider
            if self.api_key:
                os.environ["GOOGLE_API_KEY"] = self.api_key
            if self.run_id:
                os.environ["HDRP_RUN_ID"] = self.run_id
            
            self._update_progress("Starting Python services", 10)
            
            # Start Python service servers
            service_configs = [
                ("Principal", 50051, "HDRP/services/principal/principal_server.py"),
                ("Researcher", 50052, "HDRP/services/researcher/researcher_server.py"),
                ("Critic", 50053, "HDRP/services/critic/critic_server.py"),
                ("Synthesizer", 50054, "HDRP/services/synthesizer/synthesizer_server.py"),
            ]
            
            for idx, (service_name, port, script_path) in enumerate(service_configs):
                proc = self._start_service_server(service_name, port, script_path)
                self.services.append((service_name, proc))
                
                if not self._wait_for_service("localhost", port, timeout=5):
                    return {
                        "success": False,
                        "run_id": self.run_id or "",
                        "report": "",
                        "error": f"{service_name} service failed to start",
                    }
                
                progress = 10 + ((idx + 1) / len(service_configs)) * 20
                self._update_progress(f"Started {service_name} service", progress)
            
            self._update_progress("Starting Go orchestrator", 30)
            
            # Start Go orchestrator
            orchestrator_port = 50055
            orchestrator_path = "HDRP/orchestrator/server"
            
            if not os.path.exists(orchestrator_path):
                self._update_progress("Building orchestrator binary", 35)
                if self.verbose:
                    self.console.print(f"[yellow]Orchestrator binary not found, building...[/yellow]")
                build_result = subprocess.run(
                    ["go", "build", "-o", "server", "./cmd/server"],
                    cwd="HDRP/orchestrator",
                    capture_output=True,
                    text=True
                )
                if build_result.returncode != 0:
                    return {
                        "success": False,
                        "run_id": self.run_id or "",
                        "report": "",
                        "error": f"Failed to build orchestrator: {build_result.stderr}",
                    }
            
            if self.verbose:
                self.console.print(f"[cyan]Starting Go orchestrator on port {orchestrator_port}...[/cyan]")
            
            self.orchestrator_proc = subprocess.Popen(
                [orchestrator_path, "-port", str(orchestrator_port)],
                stdout=subprocess.PIPE if not self.verbose else None,
                stderr=subprocess.PIPE if not self.verbose else None,
                text=True
            )
            
            # Wait for orchestrator
            time.sleep(2)
            
            if self.orchestrator_proc.poll() is not None:
                stdout, stderr = self.orchestrator_proc.communicate()
                return {
                    "success": False,
                    "run_id": self.run_id or "",
                    "report": "",
                    "error": f"Orchestrator failed to start: {stderr}",
                }
            
            self._update_progress("Sending query to orchestrator", 40)
            
            if self.verbose:
                self.console.print(f"[bold cyan]Sending query to orchestrator...[/bold cyan]")
            
            # Send query
            request_data = {
                "query": query,
                "provider": self.provider or "simulated",
            }
            
            response = requests.post(
                f"http://localhost:{orchestrator_port}/execute",
                json=request_data,
                timeout=300
            )
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "run_id": self.run_id or "",
                    "report": "",
                    "error": f"Orchestrator request failed: {response.status_code} - {response.text}",
                }
            
            result = response.json()
            
            if not result.get("success"):
                return {
                    "success": False,
                    "run_id": result.get("run_id", self.run_id or ""),
                    "report": "",
                    "error": result.get("error_message", "Unknown error"),
                }
            
            report = result.get("report", "")
            
            # Output report
            if output_path:
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(report)
                if self.verbose:
                    self.console.print(f"[green]Report written to {output_path}[/green]")
            
            if self.verbose:
                self.console.print(f"[cyan]Run ID: {result.get('run_id')}[/cyan]")
            
            self._update_progress("Completed", 100)
            
            return {
                "success": True,
                "run_id": result.get("run_id", self.run_id or ""),
                "report": report,
                "error": "",
            }
        
        except HDRPError as e:
            # Structured HDRP error - use user-friendly message
            user_message = format_user_error(e, include_details=self.verbose)
            
            # Report to Sentry
            report_error(e, run_id=self.run_id, extra_context={"caller": "orchestrated"})
            
            return {
                "success": False,
                "run_id": self.run_id or "",
                "report": "",
                "error": user_message,
            }
        
        except Exception as e:
            # Unexpected error - use user-friendly message
            user_message = format_user_error(e, include_details=self.verbose)
            
            # Report to Sentry
            report_error(
                e,
                run_id=self.run_id,
                extra_context={"caller": "orchestrated", "original_error": type(e).__name__}
            )
            
            return {
                "success": False,
                "run_id": self.run_id or "",
                "report": "",
                "error": user_message,
            }
        
        finally:
            # Cleanup: stop all services
            if self.verbose:
                self.console.print("\n[cyan]Shutting down services...[/cyan]")
            
            if self.orchestrator_proc:
                self.orchestrator_proc.terminate()
                try:
                    self.orchestrator_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.orchestrator_proc.kill()
            
            for service_name, proc in self.services:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
