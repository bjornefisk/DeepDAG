package retry

import (
	"context"
	"errors"
	"fmt"
	"syscall"
	"testing"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

func TestClassifyContextErrors(t *testing.T) {
	tests := []struct {
		name     string
		err      error
		expected ErrorType
	}{
		{"DeadlineExceeded", context.DeadlineExceeded, ErrorTypeTransient},
		{"Canceled", context.Canceled, ErrorTypePermanent},
		{"Nil", nil, ErrorTypePermanent},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := ClassifyError(tt.err)
			if result != tt.expected {
				t.Errorf("Expected %v, got %v", tt.expected, result)
			}
		})
	}
}

func TestClassifyGRPCErrors(t *testing.T) {
	tests := []struct {
		name     string
		code     codes.Code
		expected ErrorType
	}{
		// Transient errors
		{" Unavailable", codes.Unavailable, ErrorTypeTransient},
		{"DeadlineExceeded", codes.DeadlineExceeded, ErrorTypeTransient},
		{"ResourceExhausted", codes.ResourceExhausted, ErrorTypeTransient},
		{"Aborted", codes.Aborted, ErrorTypeTransient},
		{"Internal", codes.Internal, ErrorTypeTransient},

		// Permanent errors
		{"InvalidArgument", codes.InvalidArgument, ErrorTypePermanent},
		{"NotFound", codes.NotFound, ErrorTypePermanent},
		{"AlreadyExists", codes.AlreadyExists, ErrorTypePermanent},
		{"PermissionDenied", codes.PermissionDenied, ErrorTypePermanent},
		{"Unauthenticated", codes.Unauthenticated, ErrorTypePermanent},
		{"Canceled", codes.Canceled, ErrorTypePermanent},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := status.Error(tt.code, "test error")
			result := ClassifyError(err)
			if result != tt.expected {
				t.Errorf("Code %v: expected %v, got %v", tt.code, tt.expected, result)
			}
		})
	}
}

func TestClassifyStringPatterns(t *testing.T) {
	tests := []struct {
		name     string
		err      error
		expected ErrorType
	}{
		// Transient patterns
		{"Timeout", errors.New("connection timeout"), ErrorTypeTransient},
		{"Unavailable", errors.New("service unavailable"), ErrorTypeTransient},
		{"RateLimit", errors.New("rate limit exceeded"), ErrorTypeTransient},
		{"ConnectionRefused", errors.New("connection refused"), ErrorTypeTransient},

		// Permanent patterns
		{"Invalid", errors.New("invalid input"), ErrorTypePermanent},
		{"ValidationFailed", errors.New("validation failed"), ErrorTypePermanent},
		{"NotFound", errors.New("resource not found"), ErrorTypePermanent},
		{"Unauthorized", errors.New("unauthorized access"), ErrorTypePermanent},

		// Unknown defaults to transient
		{"UnknownError", errors.New("something went wrong"), ErrorTypeTransient},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := ClassifyError(tt.err)
			if result != tt.expected {
				t.Errorf("Expected %v, got %v", tt.expected, result)
			}
		})
	}
}

func TestClassifySyscallErrors(t *testing.T) {
	tests := []struct {
		name     string
		errno    syscall.Errno
		expected ErrorType
	}{
		{"ECONNREFUSED", syscall.ECONNREFUSED, ErrorTypeTransient},
		{"ECONNRESET", syscall.ECONNRESET, ErrorTypeTransient},
		{"ETIMEDOUT", syscall.ETIMEDOUT, ErrorTypeTransient},
		{"ENETUNREACH", syscall.ENETUNREACH, ErrorTypeTransient},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := fmt.Errorf("syscall error: %w", tt.errno)
			result := ClassifyError(err)
			if result != tt.expected {
				t.Errorf("Errno %v: expected %v, got %v", tt.errno, tt.expected, result)
			}
		})
	}
}

func TestIsRetryable(t *testing.T) {
	tests := []struct {
		name     string
		err      error
		expected bool
	}{
		{"TransientError", context.DeadlineExceeded, true},
		{"PermanentError", context.Canceled, false},
		{"TimeoutString", errors.New("timeout occurred"), true},
		{"ValidationError", errors.New("validation failed"), false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := IsRetryable(tt.err)
			if result != tt.expected {
				t.Errorf("Expected %v, got %v", tt.expected, result)
			}
		})
	}
}
