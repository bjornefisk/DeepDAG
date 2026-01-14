#!/usr/bin/env python3
"""Orchestrated Pipeline Runner.

Manages Python gRPC service lifecycle and communicates with Go orchestrator.
"""

import os
import sys
import time
import subprocess
import requests
import json
from typing import Optional
from rich.console import Console

console = Console()


def start_service_server(service_name: str, port: int, script_path: str) -> subprocess.Popen:
    """Starts a Python gRPC service server in the background."""
    cmd = [sys.executable, script_path, "--port", str(port)]
    
    console.print(f"[cyan]Starting {service_name} service on port {port}...[/cyan]")
    
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


def wait_for_service(host: str, port: int, timeout: int = 10) -> bool:
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


def run_orchestrated(
    query: str,
    provider: str,
    api_key: Optional[str],
    output_path: Optional[str],
    verbose: bool
) -> int:
    """Runs a query through the Go orchestrator.
    
    Starts all required services and sends the query to the orchestrator.
    """
    services = []
    orchestrator_proc = None
    
    try:
        # Set environment variables for search provider
        if provider:
            os.environ["HDRP_SEARCH_PROVIDER"] = provider
        if api_key:
            os.environ["GOOGLE_API_KEY"] = api_key
        
        # Start Python service servers
        service_configs = [
            ("Principal", 50051, "HDRP/services/principal/principal_server.py"),
            ("Researcher", 50052, "HDRP/services/researcher/researcher_server.py"),
            ("Critic", 50053, "HDRP/services/critic/critic_server.py"),
            ("Synthesizer", 50054, "HDRP/services/synthesizer/synthesizer_server.py"),
        ]
        
        for service_name, port, script_path in service_configs:
            proc = start_service_server(service_name, port, script_path)
            services.append((service_name, proc))
            
            if not wait_for_service("localhost", port, timeout=5):
                console.print(f"[red]Warning: {service_name} may not be ready[/red]")
        
        # Start Go orchestrator
        orchestrator_port = 50055
        orchestrator_path = "HDRP/orchestrator/server"
        
        if not os.path.exists(orchestrator_path):
            console.print(f"[yellow]Orchestrator binary not found, building...[/yellow]")
            build_result = subprocess.run(
                ["go", "build", "-o", "server", "./cmd/server"],
                cwd="HDRP/orchestrator",
                capture_output=True,
                text=True
            )
            if build_result.returncode != 0:
                console.print(f"[red]Failed to build orchestrator:[/red]\n{build_result.stderr}")
                return 1
        
        console.print(f"[cyan]Starting Go orchestrator on port {orchestrator_port}...[/cyan]")
        orchestrator_proc = subprocess.Popen(
            [orchestrator_path, "-port", str(orchestrator_port)],
            stdout=subprocess.PIPE if not verbose else None,
            stderr=subprocess.PIPE if not verbose else None,
            text=True
        )
        
        # Wait for orchestrator to be ready
        time.sleep(2)
        
        if orchestrator_proc.poll() is not None:
            stdout, stderr = orchestrator_proc.communicate()
            console.print(f"[red]Orchestrator failed to start:[/red]\n{stderr}")
            return 1
        
        # Send query to orchestrator
        console.print(f"[bold cyan]Sending query to orchestrator...[/bold cyan]")
        
        request_data = {
            "query": query,
            "provider": provider or "simulated",
        }
        
        response = requests.post(
            f"http://localhost:{orchestrator_port}/execute",
            json=request_data,
            timeout=300  # 5 minute timeout
        )
        
        if response.status_code != 200:
            console.print(f"[red]Orchestrator request failed: {response.status_code}[/red]")
            console.print(response.text)
            return 1
        
        result = response.json()
        
        if not result.get("success"):
            console.print(f"[red]Execution failed:[/red] {result.get('error_message', 'Unknown error')}")
            return 1
        
        report = result.get("report", "")
        
        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(report)
            console.print(f"[green]Report written to {output_path}[/green]")
        else:
            console.print(report, markup=False)
        
        if verbose:
            console.print(f"[cyan]Run ID: {result.get('run_id')}[/cyan]")
        
        return 0
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        return 1
    except Exception as e:
        # Initialize Sentry if not already done
        from HDRP.services.shared.errors import init_sentry, capture_exception, get_user_friendly_message
        init_sentry()
        
        # Capture exception with context
        capture_exception(
            e,
            run_id=os.getenv("HDRP_RUN_ID"),
            service="orchestrator",
            context={
                "query": query,
                "provider": provider,
                "verbose": verbose
            }
        )
        
        # Show user-friendly message instead of stack trace
        user_message = get_user_friendly_message(e)
        console.print(f"[red]Error:[/red] {user_message}")
        
        # Only show stack trace in verbose mode
        if verbose:
            import traceback
            traceback.print_exc()
        
        return 1
    finally:
        # Cleanup: stop all services
        console.print("\n[cyan]Shutting down services...[/cyan]")
        
        if orchestrator_proc:
            orchestrator_proc.terminate()
            try:
                orchestrator_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                orchestrator_proc.kill()
        
        for service_name, proc in services:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()


def run_orchestrated_programmatic(
    query: str,
    provider: str = "",
    api_key: Optional[str] = None,
    verbose: bool = False,
    run_id: Optional[str] = None,
    progress_callback: Optional[callable] = None,
) -> dict:
    """
    Execute query through Go orchestrator (for dashboard integration).
    
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
    services = []
    orchestrator_proc = None
    
    try:
        # Progress update helper
        def update_progress(stage: str, percent: float):
            if progress_callback:
                progress_callback(stage, percent)
        
        update_progress("Setting up environment", 5)
        
        # Set environment variables
        if provider:
            os.environ["HDRP_SEARCH_PROVIDER"] = provider
        if api_key:
            os.environ["GOOGLE_API_KEY"] = api_key
        if run_id:
            os.environ["HDRP_RUN_ID"] = run_id
        
        update_progress("Starting Python services", 10)
        
        # Start Python service servers
        service_configs = [
            ("Principal", 50051, "HDRP/services/principal/principal_server.py"),
            ("Researcher", 50052, "HDRP/services/researcher/researcher_server.py"),
            ("Critic", 50053, "HDRP/services/critic/critic_server.py"),
            ("Synthesizer", 50054, "HDRP/services/synthesizer/synthesizer_server.py"),
        ]
        
        for idx, (service_name, port, script_path) in enumerate(service_configs):
            proc = start_service_server(service_name, port, script_path)
            services.append((service_name, proc))
            
            if not wait_for_service("localhost", port, timeout=5):
                return {
                    "success": False,
                    "run_id": run_id or "",
                    "report": "",
                    "error": f"{service_name} service failed to start",
                }
            
            progress = 10 + ((idx + 1) / len(service_configs)) * 20
            update_progress(f"Started {service_name} service", progress)
        
        update_progress("Starting Go orchestrator", 30)
        
        # Start Go orchestrator
        orchestrator_port = 50055
        orchestrator_path = "HDRP/orchestrator/server"
        
        if not os.path.exists(orchestrator_path):
            update_progress("Building orchestrator binary", 35)
            build_result = subprocess.run(
                ["go", "build", "-o", "server", "./cmd/server"],
                cwd="HDRP/orchestrator",
                capture_output=True,
                text=True
            )
            if build_result.returncode != 0:
                return {
                    "success": False,
                    "run_id": run_id or "",
                    "report": "",
                    "error": f"Failed to build orchestrator: {build_result.stderr}",
                }
        
        orchestrator_proc = subprocess.Popen(
            [orchestrator_path, "-port", str(orchestrator_port)],
            stdout=subprocess.PIPE if not verbose else None,
            stderr=subprocess.PIPE if not verbose else None,
            text=True
        )
        
        # Wait for orchestrator
        time.sleep(2)
        
        if orchestrator_proc.poll() is not None:
            stdout, stderr = orchestrator_proc.communicate()
            return {
                "success": False,
                "run_id": run_id or "",
                "report": "",
                "error": f"Orchestrator failed to start: {stderr}",
            }
        
        update_progress("Sending query to orchestrator", 40)
        
        # Send query
        request_data = {
            "query": query,
            "provider": provider or "simulated",
        }
        
        response = requests.post(
            f"http://localhost:{orchestrator_port}/execute",
            json=request_data,
            timeout=300
        )
        
        if response.status_code != 200:
            return {
                "success": False,
                "run_id": run_id or "",
                "report": "",
                "error": f"Orchestrator request failed: {response.status_code} - {response.text}",
            }
        
        result = response.json()
        
        if not result.get("success"):
            return {
                "success": False,
                "run_id": result.get("run_id", run_id or ""),
                "report": "",
                "error": result.get("error_message", "Unknown error"),
            }
        
        update_progress("Completed", 100)
        
        return {
            "success": True,
            "run_id": result.get("run_id", run_id or ""),
            "report": result.get("report", ""),
            "error": "",
        }
    
    
    except Exception as e:
        # Initialize Sentry and capture error
        from HDRP.services.shared.errors import init_sentry, capture_exception, get_user_friendly_message
        init_sentry()
        
        capture_exception(
            e,
            run_id=run_id,
            service="orchestrator_programmatic",
            context={
                "query": query,
                "provider": provider,
                "verbose": verbose
            }
        )
        
        # Return user-friendly error message
        user_message = get_user_friendly_message(e)
        
        return {
            "success": False,
            "run_id": run_id or "",
            "report": "",
            "error": user_message,
        }
    
    finally:
        # Cleanup: stop all services
        if orchestrator_proc:
            orchestrator_proc.terminate()
            try:
                orchestrator_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                orchestrator_proc.kill()
        
        for service_name, proc in services:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()

