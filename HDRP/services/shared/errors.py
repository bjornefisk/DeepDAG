"""Shared error handling module for HDRP services.

Provides structured error hierarchy, Sentry integration, and user-friendly
error messages for graceful degradation.
"""

import os
import traceback
from typing import Optional, Dict, Any


class HDRPError(Exception):
    """Base exception for all HDRP errors.
    
    All HDRP errors include:
    - run_id: Execution context identifier
    - service: Which service raised the error
    - metadata: Additional context for debugging
    """
    
    def __init__(
        self,
        message: str,
        run_id: Optional[str] = None,
        service: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.run_id = run_id
        self.service = service
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for logging/serialization."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "run_id": self.run_id,
            "service": self.service,
            "metadata": self.metadata
        }


class ServiceError(HDRPError):
    """Base class for service-level errors."""
    pass


class ResearcherError(ServiceError):
    """Errors from the Researcher service (search, extraction)."""
    
    def __init__(self, message: str, run_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        super().__init__(message, run_id=run_id, service="researcher", metadata=metadata)


class CriticError(ServiceError):
    """Errors from the Critic service (verification)."""
    
    def __init__(self, message: str, run_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        super().__init__(message, run_id=run_id, service="critic", metadata=metadata)


class SynthesizerError(ServiceError):
    """Errors from the Synthesizer service (report generation)."""
    
    def __init__(self, message: str, run_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        super().__init__(message, run_id=run_id, service="synthesizer", metadata=metadata)


class PrincipalError(ServiceError):
    """Errors from the Principal service (query decomposition)."""
    
    def __init__(self, message: str, run_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        super().__init__(message, run_id=run_id, service="principal", metadata=metadata)


def _get_sentry_client():
    """Lazy-load Sentry SDK if DSN is configured.
    
    Returns:
        sentry_sdk module if available and configured, None otherwise
    """
    sentry_dsn = os.environ.get("SENTRY_DSN")
    if not sentry_dsn:
        return None
    
    try:
        import sentry_sdk
        # Initialize if not already done
        if not sentry_sdk.Hub.current.client:
            sentry_sdk.init(
                dsn=sentry_dsn,
                traces_sample_rate=0.1,
                profiles_sample_rate=0.1,
            )
        return sentry_sdk
    except ImportError:
        return None


def report_error(
    error: Exception,
    run_id: Optional[str] = None,
    service: Optional[str] = None,
    extra_context: Optional[Dict[str, Any]] = None
) -> None:
    """Report error to Sentry with structured context.
    
    Args:
        error: The exception to report
        run_id: Execution context identifier
        service: Service name where error occurred
        extra_context: Additional metadata for debugging
    """
    sentry = _get_sentry_client()
    if not sentry:
        return
    
    context = extra_context or {}
    
    # Add run_id and service as tags for filtering
    with sentry.push_scope() as scope:
        if run_id:
            scope.set_tag("run_id", run_id)
        if service:
            scope.set_tag("service", service)
        
        # Add all extra context
        for key, value in context.items():
            scope.set_context(key, value)
        
        # If it's an HDRPError, add its metadata
        if isinstance(error, HDRPError):
            scope.set_context("hdrp_error", error.to_dict())
        
        sentry.capture_exception(error)


def format_user_error(error: Exception, include_details: bool = False) -> str:
    """Convert exception to user-friendly message (no stack traces).
    
    Args:
        error: The exception to format
        include_details: Whether to include technical details (for verbose mode)
    
    Returns:
        Clean error message suitable for end users
    """
    if isinstance(error, HDRPError):
        service_name = error.service or "service"
        base_message = f"{service_name.title()} service encountered an error"
        
        if include_details:
            return f"{base_message}: {error.message}"
        else:
            return f"{base_message}. Continuing with partial results..."
    
    # Generic exception
    error_type = type(error).__name__
    if include_details:
        return f"Error ({error_type}): {str(error)}"
    else:
        return "An unexpected error occurred. Continuing with partial results..."


def wrap_service_error(
    func,
    error_class: type,
    run_id: Optional[str] = None,
    default_return=None,
    metadata: Optional[Dict[str, Any]] = None
):
    """Decorator to wrap service methods with error handling.
    
    Args:
        func: Function to wrap
        error_class: HDRPError subclass to raise on error
        run_id: Execution context identifier
        default_return: Value to return on error (enables graceful degradation)
        metadata: Additional context for error reporting
    
    Usage:
        @wrap_service_error(ResearcherError, run_id=self.run_id, default_return=[])
        def research(self, query):
            # ... implementation
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Don't double-wrap HDRP errors
            if isinstance(e, HDRPError):
                wrapped_error = e
            else:
                wrapped_error = error_class(
                    message=str(e),
                    run_id=run_id,
                    metadata={**(metadata or {}), "original_error": type(e).__name__}
                )
            
            # Report to Sentry
            report_error(
                wrapped_error,
                run_id=run_id,
                service=wrapped_error.service if isinstance(wrapped_error, HDRPError) else None,
                extra_context=metadata
            )
            
            # Return default or re-raise
            if default_return is not None:
                return default_return
            else:
                raise wrapped_error
    
    return wrapper
