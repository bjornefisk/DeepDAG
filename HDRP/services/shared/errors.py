"""Shared error handling infrastructure for HDRP services.

Provides custom exceptions, gRPC error mapping, user-facing error messages,
and Sentry integration with run_id context.
"""

import logging
import os
import traceback
from typing import Optional, Dict, Any, List
import grpc

logger = logging.getLogger(__name__)

# Sentry integration (lazy loaded)
_sentry_initialized = False
try:  # pragma: no cover - optional dependency
    import sentry_sdk
except Exception:  # pragma: no cover - optional dependency
    sentry_sdk = None


def init_sentry(dsn: Optional[str] = None):
    """Initialize Sentry SDK with configuration.
    
    Args:
        dsn: Sentry DSN. If not provided, reads from centralized settings.
    """
    global _sentry_initialized
    
    if _sentry_initialized:
        return
    
    try:
        if sentry_sdk is None:
            logger.warning("sentry-sdk not installed, error tracking disabled")
            return

        from HDRP.services.shared.settings import get_settings

        settings = get_settings()

        # Get DSN from parameter, settings, or environment
        effective_dsn = dsn
        if not effective_dsn and settings.observability.sentry.dsn:
            effective_dsn = settings.observability.sentry.dsn.get_secret_value()
        if not effective_dsn:
            effective_dsn = os.getenv("SENTRY_DSN")

        if not effective_dsn:
            logger.info("Sentry DSN not configured, error tracking disabled")
            return

        sentry_sdk.init(
            dsn=effective_dsn,
            traces_sample_rate=settings.observability.sentry.traces_sample_rate,
            profiles_sample_rate=0.1,
            environment=settings.observability.sentry.environment,
        )

        _sentry_initialized = True
        logger.info("Sentry error tracking initialized")

    except Exception as e:
        logger.error(f"Failed to initialize Sentry: {e}")


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
        metadata: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None
    ):
        super().__init__(message)
        self.message = message
        self.run_id = run_id
        self.service = service
        self.metadata = metadata or {}
        self.user_message = user_message
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for logging/serialization."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "run_id": self.run_id,
            "service": self.service,
            "metadata": self.metadata
        }


class HDRPServiceError(HDRPError):
    """Base exception for HDRP services with user-facing defaults."""

    def __init__(
        self,
        message: str,
        run_id: Optional[str] = None,
        service: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None
    ):
        super().__init__(
            message,
            run_id=run_id,
            service=service,
            metadata=metadata,
            user_message=user_message or message,
        )


class ServiceError(HDRPServiceError):
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


class SearchProviderError(ResearcherError):
    """Error from search provider."""
    pass


def report_error(
    error: Exception,
    run_id: Optional[str] = None,
    service: Optional[str] = None,
    extra_context: Optional[Dict[str, Any]] = None
) -> None:
    """Report error to Sentry with structured context."""
    init_sentry()
    
    try:
        import sentry_sdk
        
        with sentry_sdk.push_scope() as scope:
            # Set tags
            if run_id:
                scope.set_tag("run_id", run_id)
            elif isinstance(error, HDRPError) and error.run_id:
                scope.set_tag("run_id", error.run_id)
                
            if service:
                scope.set_tag("service", service)
            elif isinstance(error, HDRPError) and error.service:
                scope.set_tag("service", error.service)
            
            # Set context
            if extra_context:
                for key, value in extra_context.items():
                    scope.set_context(key, value)
            
            if isinstance(error, HDRPError):
                scope.set_context("hdrp_error", error.to_dict())
            
            sentry_sdk.capture_exception(error)
            
    except ImportError:
        logger.error(f"Error in {service or 'unknown'}: {error}", exc_info=True)
    except Exception as e:
        logger.error(f"Failed to report error to Sentry: {e}")


# Legacy alias for capture_exception if needed by other components
capture_exception = report_error


def format_user_error(error: Exception, include_details: bool = False) -> str:
    """Convert exception to user-facing error message (no stack traces)."""
    # Map common exceptions to friendly messages
    if isinstance(error, ResearcherError):
        return "Unable to complete research. The search service may be unavailable."
    if isinstance(error, CriticError):
        return "Unable to verify claims. Continuing with unverified results."
    if isinstance(error, SynthesizerError):
        return "Unable to generate complete report. Partial results available."
    if isinstance(error, PrincipalError):
        return "Unable to decompose query. Using simplified research plan."

    if isinstance(error, HDRPError):
        if error.user_message:
            return error.user_message

        service_name = error.service or "service"
        base_message = f"{service_name.title()} service encountered an error"

        if include_details:
            return f"{base_message}: {error.message}"
        else:
            return f"{base_message}. Continuing with partial results..."
    
    if isinstance(error, ValueError):
        return f"Invalid input: {str(error)}"
    if isinstance(error, TimeoutError):
        return "Request took too long to process. Please try a simpler query."
    if isinstance(error, ConnectionError):
        return "Service connection failed. Please check your network connection."
    
    # Generic fallback
    if include_details:
        return f"Error ({type(error).__name__}): {str(error)}"
    else:
        return "An unexpected error occurred. Our team has been notified."


# Legacy alias
get_user_friendly_message = format_user_error


def map_to_grpc_status(exc: Exception) -> grpc.StatusCode:
    """Map exception to appropriate gRPC status code."""
    if isinstance(exc, ValueError):
        return grpc.StatusCode.INVALID_ARGUMENT
    if isinstance(exc, TimeoutError):
        return grpc.StatusCode.DEADLINE_EXCEEDED
    if isinstance(exc, (ConnectionError, SearchProviderError)):
        return grpc.StatusCode.UNAVAILABLE
    if isinstance(exc, PermissionError):
        return grpc.StatusCode.PERMISSION_DENIED
    if isinstance(exc, NotImplementedError):
        return grpc.StatusCode.UNIMPLEMENTED
    
    return grpc.StatusCode.INTERNAL


def handle_rpc_error(
    exc: Exception,
    context: grpc.ServicerContext,
    run_id: Optional[str] = None,
    service: Optional[str] = None,
    additional_context: Optional[Dict[str, Any]] = None
):
    """Handle RPC error by setting gRPC status and capturing in Sentry."""
    logger.error(f"RPC error in {service}: {exc}", exc_info=True)
    capture_exception(exc, run_id=run_id, service=service, extra_context=additional_context)
    
    status_code = map_to_grpc_status(exc)
    user_message = format_user_error(exc)
    
    context.set_code(status_code)
    context.set_details(user_message)


def wrap_service_error(
    func,
    error_class: type,
    run_id: Optional[str] = None,
    default_return=None,
    metadata: Optional[Dict[str, Any]] = None
):
    """Decorator to wrap service methods with error handling."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if isinstance(e, HDRPError):
                wrapped_error = e
            else:
                wrapped_error = error_class(
                    message=str(e),
                    run_id=run_id,
                    metadata={**(metadata or {}), "original_error": type(e).__name__}
                )
            
            report_error(
                wrapped_error,
                run_id=run_id,
                service=wrapped_error.service if isinstance(wrapped_error, HDRPError) else None,
                extra_context=metadata
            )
            
            if default_return is not None:
                return default_return
            else:
                raise wrapped_error
    return wrapper


def can_continue_with_partial_results(service: str, error: Exception) -> bool:
    """Determine if execution can continue with partial results."""
    # Logic from remote branch
    if service in ["researcher", "critic", "synthesizer", "principal"]:
        return True
    return False
