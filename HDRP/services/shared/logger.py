import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Constants
LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../logs"))

class JsonFormatter(logging.Formatter):
    """
    Formatter to output logs as JSON Lines, matching the Go Orchestrator's schema.
    """
    def format(self, record):
        log_record = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "component": getattr(record, "component", "unknown"),
            "run_id": getattr(record, "run_id", "unknown"),
            "event": getattr(record, "event", record.msg),
            "payload": getattr(record, "payload", {})
        }
        return json.dumps(log_record)

class ResearchLogger:
    def __init__(self, component_name: str, run_id: Optional[str] = None):
        self.component = component_name
        self.run_id = run_id or str(uuid.uuid4())
        self.logger = logging.getLogger(f"HDRP.{component_name}")
        self.logger.setLevel(logging.INFO)
        
        # Ensure we don't add multiple handlers if initialized multiple times
        if not self.logger.handlers:
            # Create log directory if it doesn't exist
            os.makedirs(LOG_DIR, exist_ok=True)
            
            # File handler: writes to HDRP/logs/<run_id>.jsonl
            log_file = os.path.join(LOG_DIR, f"{self.run_id}.jsonl")
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(JsonFormatter())
            self.logger.addHandler(file_handler)
            
            # Console handler (optional, for debugging)
            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(JsonFormatter())
            self.logger.addHandler(stream_handler)

    def log(self, event: str, payload: Dict[str, Any] = None):
        """
        Log a specific research event.
        
        :param event: The name of the event (e.g., 'dag_update', 'claim_verified')
        :param payload: Dictionary containing the specific data
        """
        if payload is None:
            payload = {}
            
        extra = {
            "component": self.component,
            "run_id": self.run_id,
            "event": event,
            "payload": payload
        }
        
        # We pass 'event' as the message, but the formatter uses the 'event' attribute
        self.logger.info(event, extra=extra)
        
        # Flush all handlers immediately for real-time access
        for handler in self.logger.handlers:
            handler.flush()


    def set_run_id(self, run_id: str):
        """Update the run_id if it changes (e.g. passed via gRPC metadata)"""
        self.run_id = run_id
        # Note: Updating the file handler dynamically is complex; 
        # in a real microservice, we might just log to stdout and let the orchestrator collect it,
        # or append to the new file. For now, we assume one service instance might handle one run 
        # or we accept that logs might be split if the ID changes late.

# Example Usage:
# logger = ResearchLogger("critic", run_id="123-abc")
# logger.log("verification_start", {"claim": "GPU supply is tight"})
