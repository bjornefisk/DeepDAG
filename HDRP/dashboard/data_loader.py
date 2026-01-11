"""
Data loader module for reading HDRP run logs.

Provides functions to parse JSONL log files and extract run data
for dashboard visualization.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


# Path to logs directory  
LOGS_DIR = Path(__file__).parent.parent / "logs"



@dataclass
class ClaimData:
    """Parsed claim data for display."""
    claim_id: str
    statement: str
    source_url: Optional[str] = None
    source_title: Optional[str] = None
    confidence: float = 0.0
    is_verified: Optional[bool] = None
    verification_reason: Optional[str] = None
    entailment_score: float = 0.0
    extracted_at: Optional[str] = None
    source_node_id: Optional[str] = None


@dataclass
class RunData:
    """Parsed run data for display."""
    run_id: str
    query: str = ""
    timestamp: str = ""
    component: str = ""
    status: str = "unknown"
    claims: List[ClaimData] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    dag_data: Optional[Dict[str, Any]] = None
    
    # Computed stats
    total_claims: int = 0
    verified_claims: int = 0
    rejected_claims: int = 0
    unique_sources: int = 0
    execution_time_ms: float = 0.0


def list_available_runs() -> List[Dict[str, Any]]:
    """List all available runs from the logs directory.
    
    Returns:
        List of dictionaries with run_id, filename, timestamp, and size.
    """
    runs = []
    
    if not LOGS_DIR.exists():
        return runs
    
    for log_file in LOGS_DIR.glob("*.jsonl"):
        # Skip README and other non-log files
        if log_file.name == "README.md":
            continue
            
        run_id = log_file.stem
        stat = log_file.stat()
        
        # Try to read first event for timestamp
        timestamp = None
        query = ""
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                first_line = f.readline()
                if first_line:
                    event = json.loads(first_line)
                    timestamp = event.get('timestamp', '')
                    # Try to extract query from payload
                    payload = event.get('payload', {})
                    if isinstance(payload, dict):
                        query = payload.get('query', '')
        except (json.JSONDecodeError, IOError):
            pass
        
        runs.append({
            'run_id': run_id,
            'filename': log_file.name,
            'timestamp': timestamp or datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'size_bytes': stat.st_size,
            'query': query[:100] + '...' if len(query) > 100 else query,
        })
    
    # Sort by timestamp descending (newest first)
    runs.sort(key=lambda x: x['timestamp'], reverse=True)
    return runs


def load_run(run_id: str) -> Optional[RunData]:
    """Load and parse a specific run's log file.
    
    Args:
        run_id: The run ID (filename stem) to load.
        
    Returns:
        RunData object with parsed events, claims, and metrics.
    """
    log_file = LOGS_DIR / f"{run_id}.jsonl"
    
    if not log_file.exists():
        return None
    
    run_data = RunData(run_id=run_id)
    claims_map: Dict[str, ClaimData] = {}
    sources = set()
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                    
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                
                run_data.events.append(event)
                
                # Extract metadata from event
                timestamp = event.get('timestamp', '')
                component = event.get('component', '')
                event_type = event.get('event', '')
                payload = event.get('payload', {})
                
                if not run_data.timestamp and timestamp:
                    run_data.timestamp = timestamp
                if not run_data.component and component:
                    run_data.component = component
                
                # Process different event types
                if event_type == 'claims_extracted':
                    # Handle claim extraction events
                    if isinstance(payload, dict):
                        run_data.query = payload.get('query', run_data.query)
                        claims_list = payload.get('claims', [])
                        for claim_data in claims_list:
                            if isinstance(claim_data, dict):
                                claim = _parse_claim(claim_data)
                                claims_map[claim.claim_id] = claim
                                if claim.source_url:
                                    sources.add(claim.source_url)
                
                elif event_type == 'claim_verified' or event_type == 'verification_result':
                    # Handle verification events
                    if isinstance(payload, dict):
                        claim_id = payload.get('claim_id', '')
                        is_valid = payload.get('is_valid', payload.get('verified', False))
                        reason = payload.get('reason', '')
                        entailment = payload.get('entailment_score', 0.0)
                        
                        if claim_id in claims_map:
                            claims_map[claim_id].is_verified = is_valid
                            claims_map[claim_id].verification_reason = reason
                            claims_map[claim_id].entailment_score = entailment
                        else:
                            # Create claim from verification event
                            claim = ClaimData(
                                claim_id=claim_id,
                                statement=payload.get('statement', payload.get('claim', '')),
                                is_verified=is_valid,
                                verification_reason=reason,
                                entailment_score=entailment,
                            )
                            claims_map[claim_id] = claim
                
                elif event_type == 'research_start' or event_type == 'pipeline_start':
                    if isinstance(payload, dict):
                        run_data.query = payload.get('query', run_data.query)
                
                elif event_type == 'dag_update' or event_type == 'graph_update':
                    if isinstance(payload, dict):
                        run_data.dag_data = payload
                
                elif event_type == 'metrics' or event_type == 'run_complete':
                    if isinstance(payload, dict):
                        run_data.metrics.update(payload)
                        run_data.execution_time_ms = payload.get('execution_time_ms', 0.0)
                        run_data.status = 'completed'
        
        # Finalize run data
        run_data.claims = list(claims_map.values())
        run_data.total_claims = len(run_data.claims)
        run_data.verified_claims = sum(1 for c in run_data.claims if c.is_verified is True)
        run_data.rejected_claims = sum(1 for c in run_data.claims if c.is_verified is False)
        run_data.unique_sources = len(sources)
        
        if not run_data.status:
            run_data.status = 'completed' if run_data.events else 'empty'
        
        return run_data
        
    except IOError as e:
        print(f"Error reading log file: {e}")
        return None


def _parse_claim(data: Dict[str, Any]) -> ClaimData:
    """Parse a claim dictionary into ClaimData."""
    return ClaimData(
        claim_id=data.get('claim_id', data.get('id', '')),
        statement=data.get('statement', data.get('claim', '')),
        source_url=data.get('source_url', ''),
        source_title=data.get('source_title', ''),
        confidence=float(data.get('confidence', 0.0)),
        extracted_at=data.get('extracted_at', ''),
        source_node_id=data.get('source_node_id', ''),
    )


def get_run_summary_stats() -> Dict[str, Any]:
    """Get summary statistics across all runs.
    
    Returns:
        Dictionary with total runs, claims, etc.
    """
    runs = list_available_runs()
    total_claims = 0
    total_verified = 0
    
    for run_info in runs[:10]:  # Limit to recent runs for performance
        run = load_run(run_info['run_id'])
        if run:
            total_claims += run.total_claims
            total_verified += run.verified_claims
    
    return {
        'total_runs': len(runs),
        'recent_runs': len(runs[:10]),
        'total_claims': total_claims,
        'total_verified': total_verified,
        'verification_rate': total_verified / total_claims if total_claims > 0 else 0,
    }


# Demo data for testing when no logs available
def get_demo_data() -> RunData:
    """Generate demo data for testing the dashboard."""
    return RunData(
        run_id="demo-run-001",
        query="What are the latest trends in AI research?",
        timestamp=datetime.now().isoformat(),
        status="completed",
        claims=[
            ClaimData(
                claim_id="claim-1",
                statement="Large language models have shown remarkable capabilities in reasoning tasks.",
                source_url="https://arxiv.org/example1",
                source_title="Advances in LLM Reasoning",
                confidence=0.85,
                is_verified=True,
                verification_reason="Claim is supported by source text.",
                entailment_score=0.92,
            ),
            ClaimData(
                claim_id="claim-2", 
                statement="Transformer architectures remain dominant in NLP applications.",
                source_url="https://arxiv.org/example2",
                source_title="Survey of NLP Architectures",
                confidence=0.78,
                is_verified=True,
                verification_reason="Verified against source.",
                entailment_score=0.88,
            ),
            ClaimData(
                claim_id="claim-3",
                statement="Multimodal models are emerging as a key research direction.",
                source_url="https://example.com/blog",
                source_title="AI Trends 2025",
                confidence=0.65,
                is_verified=False,
                verification_reason="Source does not fully support claim.",
                entailment_score=0.35,
            ),
        ],
        total_claims=3,
        verified_claims=2,
        rejected_claims=1,
        unique_sources=3,
        execution_time_ms=1250.5,
        metrics={
            "performance": {"total_execution_time_ms": 1250.5, "search_calls_count": 5},
            "quality": {"precision": 0.67, "entailment_score": 0.72},
        }
    )


def get_latest_events(run_id: str, since_line: int = 0) -> List[Dict[str, Any]]:
    """
    Get new log events since a specific line number.
    
    Args:
        run_id: The run ID to get events for
        since_line: Line number to start from (0-indexed)
        
    Returns:
        List of new events as dictionaries
    """
    log_file = LOGS_DIR / f"{run_id}.jsonl"
    
    if not log_file.exists():
        return []
    
    events = []
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f):
                if line_num < since_line:
                    continue
                
                line = line.strip()
                if not line:
                    continue
                
                try:
                    event = json.loads(line)
                    events.append(event)
                except json.JSONDecodeError:
                    continue
    
    except IOError:
        pass
    
    return events


def get_run_progress(run_id: str) -> Optional[Dict[str, Any]]:
    """
    Get progress information for a running query.
    
    Args:
        run_id: The run ID to get progress for
        
    Returns:
        Dictionary with progress information
    """
    log_file = LOGS_DIR / f"{run_id}.jsonl"
    
    if not log_file.exists():
        return None
    
    progress = {
        "status": "running",
        "current_stage": "Initializing...",
        "progress_percent": 0.0,
        "claims_extracted": 0,
        "claims_verified": 0,
        "claims_rejected": 0,
        "total_events": 0,
    }
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    event = json.loads(line)
                    progress["total_events"] += 1
                    
                    event_type = event.get('event', '')
                    payload = event.get('payload', {})
                    
                    # Track progress based on event types
                    if event_type == 'research_start' or event_type == 'pipeline_start':
                        progress["current_stage"] = "Starting research..."
                        progress["progress_percent"] = 10.0
                    
                    elif event_type == 'claims_extracted':
                        claims_list = payload.get('claims', [])
                        progress["claims_extracted"] += len(claims_list)
                        progress["current_stage"] = f"Extracted {progress['claims_extracted']} claims"
                        progress["progress_percent"] = 40.0
                    
                    elif event_type == 'claim_verified' or event_type == 'verification_result':
                        is_valid = payload.get('is_valid', payload.get('verified', False))
                        if is_valid:
                            progress["claims_verified"] += 1
                        else:
                            progress["claims_rejected"] += 1
                        
                        total_verified = progress["claims_verified"] + progress["claims_rejected"]
                        progress["current_stage"] = f"Verifying claims ({total_verified}/{progress['claims_extracted']})"
                        progress["progress_percent"] = 40.0 + (total_verified / max(progress['claims_extracted'], 1)) * 40.0
                    
                    elif event_type == 'synthesis_start':
                        progress["current_stage"] = "Synthesizing final report..."
                        progress["progress_percent"] = 85.0
                    
                    elif event_type == 'run_complete' or event_type == 'pipeline_complete':
                        progress["status"] = "completed"
                        progress["current_stage"] = "Completed successfully"
                        progress["progress_percent"] = 100.0
                    
                    elif event_type == 'error' or event_type == 'pipeline_failed':
                        progress["status"] = "failed"
                        progress["current_stage"] = "Execution failed"
                        progress["error_message"] = payload.get('error', 'Unknown error')
                
                except json.JSONDecodeError:
                    continue
    
    except IOError:
        return None
    
    return progress

