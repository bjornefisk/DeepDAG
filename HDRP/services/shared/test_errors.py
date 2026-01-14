"""Tests for shared error handling module."""

import pytest
from unittest.mock import patch, MagicMock
import grpc

from HDRP.services.shared.errors import (
    HDRPServiceError,
    ResearcherError,
    CriticError,
    SynthesizerError,
    PrincipalError,
    get_user_friendly_message,
    map_to_grpc_status,
    handle_rpc_error,
    can_continue_with_partial_results,
)


class TestCustomExceptions:
    """Test custom exception classes"""
    
    def test_hdrp_service_error_with_user_message(self):
        """Test HDRPServiceError with custom user message"""
        exc = HDRPServiceError("Internal error", user_message="Service unavailable")
        
        assert str(exc) == "Internal error"
        assert exc.user_message == "Service unavailable"
    
    def test_hdrp_service_error_without_user_message(self):
        """Test HDRPServiceError defaults to main message"""
        exc = HDRPServiceError("Internal error")
        
        assert str(exc) == "Internal error"
        assert exc.user_message == "Internal error"
    
    def test_researcher_error_inherits_from_base(self):
        """Test ResearcherError is HDRPServiceError"""
        exc = ResearcherError("Search failed")
        
        assert isinstance(exc, HDRPServiceError)
        assert str(exc) == "Search failed"


class TestUserFriendlyMessages:
    """Test user-facing error message generation"""
    
    def test_get_user_friendly_message_for_researcher_error(self):
        """Test friendly message for ResearcherError"""
        exc = ResearcherError("API key invalid")
        message = get_user_friendly_message(exc)
        
        assert "search service" in message.lower()
        assert "unavailable" in message.lower()
    
    def test_get_user_friendly_message_for_critic_error(self):
        """Test friendly message for CriticError"""
        exc = CriticError("Verification failed")
        message = get_user_friendly_message(exc)
        
        assert "verify claims" in message.lower()
    
    def test_get_user_friendly_message_for_synthesizer_error(self):
        """Test friendly message for SynthesizerError"""
        exc = SynthesizerError("Report generation failed")
        message = get_user_friendly_message(exc)
        
        assert "report" in message.lower()
    
    def test_get_user_friendly_message_for_principal_error(self):
        """Test friendly message for PrincipalError"""
        exc = PrincipalError("LLM unavailable")
        message = get_user_friendly_message(exc)
        
        assert "decompose" in message.lower() or "simplified" in message.lower()
    
    def test_get_user_friendly_message_for_value_error(self):
        """Test friendly message for ValueError"""
        exc = ValueError("Invalid query length")
        message = get_user_friendly_message(exc)
        
        assert "invalid input" in message.lower()
        assert "Invalid query length" in message
    
    def test_get_user_friendly_message_for_timeout(self):
        """Test friendly message for TimeoutError"""
        exc = TimeoutError()
        message = get_user_friendly_message(exc)
        
        assert "too long" in message.lower() or "timeout" in message.lower()
    
    def test_get_user_friendly_message_for_generic_error(self):
        """Test generic error gets safe fallback message"""
        exc = RuntimeError("Something broke internally")
        message = get_user_friendly_message(exc)
        
        assert "unexpected error" in message.lower()
        assert "Something broke internally" not in message  # Should hide internals


class TestGrpcErrorMapping:
    """Test gRPC status code mapping"""
    
    def test_map_value_error_to_invalid_argument(self):
        """Test ValueError maps to INVALID_ARGUMENT"""
        exc = ValueError("Bad input")
        status = map_to_grpc_status(exc)
        
        assert status == grpc.StatusCode.INVALID_ARGUMENT
    
    def test_map_timeout_to_deadline_exceeded(self):
        """Test TimeoutError maps to DEADLINE_EXCEEDED"""
        exc = TimeoutError()
        status = map_to_grpc_status(exc)
        
        assert status == grpc.StatusCode.DEADLINE_EXCEEDED
    
    def test_map_generic_error_to_internal(self):
        """Test generic exceptions map to INTERNAL"""
        exc = RuntimeError("Something failed")
        status = map_to_grpc_status(exc)
        
        assert status == grpc.StatusCode.INTERNAL


class TestHandleRpcError:
    """Test RPC error handling helper"""
    
    @patch('HDRP.services.shared.errors.capture_exception')
    def test_handle_rpc_error_sets_status(self, mock_capture):
        """Test handle_rpc_error sets gRPC status correctly"""
        mock_context = MagicMock(spec=grpc.ServicerContext)
        exc = ValueError("Invalid query")
        
        handle_rpc_error(exc, mock_context, run_id="test_123", service="researcher")
        
        mock_context.set_code.assert_called_once_with(grpc.StatusCode.INVALID_ARGUMENT)
        mock_context.set_details.assert_called_once()
        details_arg = mock_context.set_details.call_args[0][0]
        assert "invalid input" in details_arg.lower()
    
    @patch('HDRP.services.shared.errors.capture_exception')
    def test_handle_rpc_error_captures_to_sentry(self, mock_capture):
        """Test handle_rpc_error calls Sentry capture"""
        mock_context = MagicMock(spec=grpc.ServicerContext)
        exc = ResearcherError("Search failed")
        
        handle_rpc_error(
            exc, mock_context, 
            run_id="test_123", 
            service="researcher",
            additional_context={"query": "test query"}
        )
        
        mock_capture.assert_called_once()
        call_args = mock_capture.call_args
        assert call_args[0][0] == exc
        assert call_args[1]['run_id'] == "test_123"
        assert call_args[1]['service'] == "researcher"


class TestSentryIntegration:
    """Test Sentry integration helpers"""
    
    @patch('HDRP.services.shared.errors.sentry_sdk')
    def test_capture_exception_with_run_id(self, mock_sentry):
        """Test capture_exception tags with run_id"""
        from HDRP.services.shared.errors import capture_exception
        
        exc = Exception("Test error")
        capture_exception(exc, run_id="run_456", service="critic")
        
        # Verify Sentry SDK was called
        mock_sentry.push_scope.assert_called()
    
    @patch('HDRP.services.shared.errors.os.getenv')
    @patch('HDRP.services.shared.errors.sentry_sdk')
    def test_init_sentry_skips_without_dsn(self, mock_sentry, mock_getenv):
        """Test init_sentry skips if no DSN configured"""
        from HDRP.services.shared.errors import init_sentry
        
        mock_getenv.return_value = None
        
        # Reset global state
        from HDRP.services.shared import errors
        errors._sentry_initialized = False
        
        init_sentry()
        
        # Should not initialize SDK without DSN
        mock_sentry.init.assert_not_called()


class TestGracefulDegradation:
    """Test graceful degradation utilities"""
    
    def test_can_continue_with_researcher_failure(self):
        """Test researcher failures allow continuation"""
        exc = ResearcherError("Search failed")
        
        assert can_continue_with_partial_results("researcher", exc) is True
    
    def test_can_continue_with_critic_failure(self):
        """Test critic failures allow continuation"""
        exc = CriticError("Verification failed")
        
        assert can_continue_with_partial_results("critic", exc) is True
    
    def test_can_continue_with_synthesizer_failure(self):
        """Test synthesizer failures allow continuation"""
        exc = SynthesizerError("Report failed")
        
        assert can_continue_with_partial_results("synthesizer", exc) is True
    
    def test_can_continue_with_principal_failure(self):
        """Test principal failures use fallback"""
        exc = PrincipalError("LLM failed")
        
        assert can_continue_with_partial_results("principal", exc) is True
