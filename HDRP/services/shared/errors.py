"""Shared error handling infrastructure for HDRP services.

Provides custom exceptions, gRPC error mapping, user-facing error messages,
and Sentry integration with run_id context.
"""

import logging
import os
from typing import Optional, Dict, Any
import grpc

logger = logging.getLogger(__name__)

# Sentry integration (lazy loaded)
_sentry_initialized = False


def init_sentry(dsn: Optional[str] = None):
    """Initialize Sentry SDK with configuration.
    
    Args:
        dsn: Sentry DSN. If not provided, reads from SENTRY_DSN env var.
    """
    global _sentry_initialized
    
    if _sentry_initialized:
        return
    
    try:
        import sentry_sdk
        
        dsn = dsn or os.getenv("SENTRY_DSN")
        if not dsn:
            logger.info("Sentry DSN not configured, error tracking disabled")
            return
        
        sentry_sdk.init(
            dsn=dsn,
            traces_sample_rate=0.1,
            profiles_sample_rate=0.1,
            environment=os.getenv("HDRP_ENV", "development"),
        )
        
        _sentry_initialized = True
        logger.info("Sentry error tracking initialized")
        
    except ImportError:
        logger.warning("sentry-sdk not installed, error tracking disabled")
    except Exception as e:
        logger.error(f"Failed to initialize Sentry: {e}")


def capture_exception(
    exc: Exception,
    run_id: Optional[str] = None,
    service: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
):
    """Capture exception with context and send to Sentry.
    
    Args:
        exc: Exception to capture
        run_id: Research run identifier
        service: Service name (e.g., "researcher", "critic")
        context: Additional context dictionary
    """
    try:
        import sentry_sdk
        
        with sentry_sdk.push_scope() as scope:
            if run_id:
                scope.set_tag("run_id", run_id)
            if service:
                scope.set_tag("service", service)
            
            if context:
                for key, value in context.items():
                    scope.set_context(key, value)
            
            sentry_sdk.capture_exception(exc)
            
    except ImportError:
        # Sentry not available, just log
        logger.error(f"Error in {service or 'unknown'}: {exc}", exc_info=True)
    except Exception as e:
        logger.error(f"Failed to capture exception in Sentry: {e}")


# Custom Exception Classes

class HDRPServiceError(Exception):
    """Base exception for all HDRP service errors."""
    
    def __init__(self, message: str, user_message: Optional[str] = None):
        super().__init__(message)
        self.user_message = user_message or message


class ResearcherError(HDRPServiceError):
    """Error during research/claim extraction."""
    pass


class CriticError(HDRPServiceError):
    """Error during claim verification."""
    pass


class SynthesizerError(HDRPServiceError):
    """Error during report synthesis."""
    pass


class PrincipalError(HDRPServiceError):
    """Error during query decomposition."""
    pass


class SearchProviderError(HDRPServiceError):
    """Error from search provider."""
    pass


# User-Facing Error Messages

def get_user_friendly_message(exc: Exception) -> str:
    """Convert exception to user-facing error message.
    
    Args:
        exc: Exception to convert
        
    Returns:
        User-friendly error message (no stack traces)
    """
    if isinstance(exc, HDRPServiceError) and exc.user_message:
        return exc.user_message
    
    # Map common exceptions to friendly messages
    if isinstance(exc, ResearcherError):
        return "Unable to complete research. The search service may be unavailable."
    
    if isinstance(exc, CriticError):
        return "Unable to verify claims. Continuing with unverified results."
    
    if isinstance(exc, SynthesizerError):
        return "Unable to generate complete report. Partial results available."
    
    if isinstance(exc, PrincipalError):
        return "Unable to decompose query. Using simplified research plan."
    
    if isinstance(exc, SearchProviderError):
        return "Search service is currently unavailable. Please try again later."
    
    if isinstance(exc, ValueError):
        return f"Invalid input: {str(exc)}"
    
    if isinstance(exc, TimeoutError):
        return "Request took too long to process. Please try a simpler query."
    
    if isinstance(exc, ConnectionError):
        return "Service connection failed. Please check your network connection."
    
    # Generic fallback
    return "An unexpected error occurred. Our team has been notified."


# gRPC Error Mapping

def map_to_grpc_status(exc: Exception) -> grpc.StatusCode:
    """Map exception to appropriate gRPC status code.
    
    Args:
        exc: Exception to map
        
    Returns:
        gRPC StatusCode
    """
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
    
    # Default to internal error
    return grpc.StatusCode.INTERNAL


def handle_rpc_error(
    exc: Exception,
    context: grpc.ServicerContext,
    run_id: Optional[str] = None,
    service: Optional[str] = None,
    additional_context: Optional[Dict[str, Any]] = None
):
    """Handle RPC error by setting gRPC status and capturing in Sentry.
    
    Args:
        exc: Exception that occurred
        context: gRPC context
        run_id: Research run identifier
        service: Service name
        additional_context: Additional context for Sentry
    """
    # Log error
    logger.error(f"RPC error in {service}: {exc}", exc_info=True)
    
    # Capture in Sentry
    capture_exception(exc, run_id=run_id, service=service, context=additional_context)
    
    # Set gRPC status
    status_code = map_to_grpc_status(exc)
    user_message = get_user_friendly_message(exc)
    
    context.set_code(status_code)
    context.set_details(user_message)


# Graceful Degradation Utilities

def can_continue_with_partial_results(service: str, error: Exception) -> bool:
    """Determine if execution can continue with partial results.
    
    Args:
        service: Service that failed
        error: Error that occurred
        
    Returns:
        True if can continue with partial results
    """
    # Researcher failures: return empty claims
    if service == "researcher":
        return True
    
    # Critic failures: return unverified claims
    if service == "critic":
        return True
    
    # Synthesizer can work with whatever verified claims are available
    if service == "synthesizer":
        return True
    
    # Principal failures should fall back to linear DAG
    if service == "principal":
        return True
    
    return False
