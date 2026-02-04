#!/usr/bin/env python3
"""
HDRP Dashboard API Layer

Manages query execution in background threads with real-time status tracking.
Supports both Python-only and orchestrator execution modes.
"""

import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum


class ExecutionStatus(Enum):
    """Execution status states."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ExecutionProgress:
    """Progress information for a running query."""
    status: ExecutionStatus
    run_id: str
    query: str
    started_at: str
    completed_at: Optional[str] = None
    progress_percent: float = 0.0
    current_stage: str = "Initializing..."
    claims_extracted: int = 0
    claims_verified: int = 0
    claims_rejected: int = 0
    error_message: Optional[str] = None
    report: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "status": self.status.value,
            "run_id": self.run_id,
            "query": self.query,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "progress_percent": self.progress_percent,
            "current_stage": self.current_stage,
            "claims_extracted": self.claims_extracted,
            "claims_verified": self.claims_verified,
            "claims_rejected": self.claims_rejected,
            "error_message": self.error_message,
            "report": self.report,
        }


class QueryExecutor:
    """
    Manages query execution in background threads.
    
    Thread-safe execution tracker that supports multiple concurrent queries.
    """
    
    def __init__(self):
        """Initialize the query executor."""
        self._executions: Dict[str, ExecutionProgress] = {}
        self._lock = threading.Lock()
        self._cancel_flags: Dict[str, threading.Event] = {}
    
    def execute_query(
        self,
        query: str,
        provider: str = "simulated",
        mode: str = "python",
        max_results: int = 10,
        verbose: bool = False,
        api_key: Optional[str] = None,
    ) -> str:
        """
        Start query execution in a background thread.
        
        Args:
            query: Research query to execute
            provider: Search provider ('simulated' or 'google')
            mode: Execution mode ('python' or 'orchestrator')
            max_results: Maximum search results
            verbose: Enable verbose logging
            api_key: API key for search provider
            
        Returns:
            run_id: Unique identifier for this execution
        """
        run_id = str(uuid.uuid4())
        
        # Create progress tracker
        progress = ExecutionProgress(
            status=ExecutionStatus.QUEUED,
            run_id=run_id,
            query=query,
            started_at=datetime.now().isoformat(),
        )
        
        # Create cancel flag
        cancel_flag = threading.Event()
        
        with self._lock:
            self._executions[run_id] = progress
            self._cancel_flags[run_id] = cancel_flag
        
        # Start execution thread
        thread = threading.Thread(
            target=self._execute_in_background,
            args=(run_id, query, provider, mode, max_results, verbose, api_key, cancel_flag),
            daemon=True,
        )
        thread.start()
        
        return run_id
    
    def _execute_in_background(
        self,
        run_id: str,
        query: str,
        provider: str,
        mode: str,
        max_results: int,
        verbose: bool,
        api_key: Optional[str],
        cancel_flag: threading.Event,
    ):
        """Execute query in background thread."""
        try:
            # Update status to running
            self._update_progress(run_id, status=ExecutionStatus.RUNNING, current_stage="Starting execution...")
            
            if cancel_flag.is_set():
                self._update_progress(run_id, status=ExecutionStatus.CANCELLED)
                return
            
            # Execute based on mode
            if mode == "orchestrator":
                result = self._execute_orchestrator_mode(run_id, query, provider, api_key, verbose, cancel_flag)
            else:
                result = self._execute_python_mode(run_id, query, provider, api_key, verbose, cancel_flag)
            
            if cancel_flag.is_set():
                self._update_progress(run_id, status=ExecutionStatus.CANCELLED)
                return
            
            # Update with results
            if result["success"]:
                self._update_progress(
                    run_id,
                    status=ExecutionStatus.COMPLETED,
                    current_stage="Completed successfully",
                    progress_percent=100.0,
                    report=result.get("report", ""),
                    completed_at=datetime.now().isoformat(),
                )
            else:
                self._update_progress(
                    run_id,
                    status=ExecutionStatus.FAILED,
                    current_stage="Execution failed",
                    error_message=result.get("error", "Unknown error"),
                    completed_at=datetime.now().isoformat(),
                )
        
        except Exception as e:
            self._update_progress(
                run_id,
                status=ExecutionStatus.FAILED,
                current_stage="Execution failed",
                error_message=str(e),
                completed_at=datetime.now().isoformat(),
            )
    
    def _execute_python_mode(
        self,
        run_id: str,
        query: str,
        provider: str,
        api_key: Optional[str],
        verbose: bool,
        cancel_flag: threading.Event,
    ) -> Dict[str, Any]:
        """Execute query using Python-only pipeline."""
        from HDRP.cli import run_query_programmatic
        
        self._update_progress(run_id, current_stage="Initializing Python pipeline...", progress_percent=5.0)
        
        if cancel_flag.is_set():
            return {"success": False, "error": "Cancelled"}
        
        # Execute the query
        result = run_query_programmatic(
            query=query,
            provider=provider,
            api_key=api_key,
            verbose=verbose,
            run_id=run_id,
            progress_callback=lambda stage, percent: self._update_progress(
                run_id, current_stage=stage, progress_percent=percent
            ) if not cancel_flag.is_set() else None,
        )
        
        return result
    
    def _execute_orchestrator_mode(
        self,
        run_id: str,
        query: str,
        provider: str,
        api_key: Optional[str],
        verbose: bool,
        cancel_flag: threading.Event,
    ) -> Dict[str, Any]:
        """Execute query using Go orchestrator."""
        from HDRP.services.shared.pipeline_runner import OrchestratedPipelineRunner
        
        self._update_progress(run_id, current_stage="Starting orchestrator services...", progress_percent=5.0)
        
        if cancel_flag.is_set():
            return {"success": False, "error": "Cancelled"}
        
        # Create orchestrated runner with progress callback
        runner = OrchestratedPipelineRunner(
            provider=provider,
            api_key=api_key,
            verbose=verbose,
            run_id=run_id,
            progress_callback=lambda stage, percent: self._update_progress(
                run_id, current_stage=stage, progress_percent=percent
            ) if not cancel_flag.is_set() else None,
        )
        
        # Execute through orchestrator
        result = runner.execute(query=query)
        
        return result
    
    def _update_progress(self, run_id: str, **kwargs):
        """Update execution progress (thread-safe)."""
        with self._lock:
            if run_id in self._executions:
                progress = self._executions[run_id]
                for key, value in kwargs.items():
                    if hasattr(progress, key):
                        setattr(progress, key, value)
    
    def get_status(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current execution status.
        
        Args:
            run_id: Execution identifier
            
        Returns:
            Progress dictionary or None if not found
        """
        with self._lock:
            progress = self._executions.get(run_id)
            if progress:
                return progress.to_dict()
            return None
    
    def cancel_query(self, run_id: str) -> bool:
        """
        Cancel a running query.
        
        Args:
            run_id: Execution identifier
            
        Returns:
            True if cancelled, False if not found or already completed
        """
        with self._lock:
            if run_id in self._cancel_flags:
                progress = self._executions.get(run_id)
                if progress and progress.status in [ExecutionStatus.QUEUED, ExecutionStatus.RUNNING]:
                    self._cancel_flags[run_id].set()
                    progress.status = ExecutionStatus.CANCELLED
                    progress.current_stage = "Cancelled by user"
                    progress.completed_at = datetime.now().isoformat()
                    return True
        return False
    
    def get_all_executions(self) -> List[Dict[str, Any]]:
        """Get all executions (for debugging/monitoring)."""
        with self._lock:
            return [p.to_dict() for p in self._executions.values()]
    
    def cleanup_old_executions(self, max_age_hours: int = 24):
        """Remove old execution records."""
        cutoff = datetime.now().timestamp() - (max_age_hours * 3600)
        
        with self._lock:
            to_remove = []
            for run_id, progress in self._executions.items():
                started = datetime.fromisoformat(progress.started_at).timestamp()
                if started < cutoff and progress.status in [
                    ExecutionStatus.COMPLETED,
                    ExecutionStatus.FAILED,
                    ExecutionStatus.CANCELLED,
                ]:
                    to_remove.append(run_id)
            
            for run_id in to_remove:
                del self._executions[run_id]
                if run_id in self._cancel_flags:
                    del self._cancel_flags[run_id]


# Global executor instance
_executor = QueryExecutor()


def get_executor() -> QueryExecutor:
    """Get the global query executor instance."""
    return _executor
