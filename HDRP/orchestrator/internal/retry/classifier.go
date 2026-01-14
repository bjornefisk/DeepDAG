package retry

import (
	"context"
	"errors"
	"net"
	"strings"
	"syscall"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// ErrorType represents the classification of an error.
type ErrorType int

const (
	// ErrorTypeUnknown represents errors that cannot be definitively classified.
	ErrorTypeUnknown ErrorType = iota
	// ErrorTypeTransient represents temporary errors that may succeed on retry.
	ErrorTypeTransient
	// ErrorTypePermanent represents errors that will not succeed even with retries.
	ErrorTypePermanent
)

// String returns the string representation of ErrorType.
func (e ErrorType) String() string {
	switch e {
	case ErrorTypeTransient:
		return "Transient"
	case ErrorTypePermanent:
		return "Permanent"
	default:
		return "Unknown"
	}
}

// ClassifyError analyzes an error and determines if it's transient or permanent.
func ClassifyError(err error) ErrorType {
	if err == nil {
		return ErrorTypePermanent // No error means no retry
	}

	// Context-related errors
	if errors.Is(err, context.DeadlineExceeded) {
		return ErrorTypeTransient // Timeout might work with more time
	}
	if errors.Is(err, context.Canceled) {
		return ErrorTypePermanent // Explicit cancellation should not retry
	}

	// Network errors
	var netErr net.Error
	if errors.As(err, &netErr) {
		if netErr.Timeout() {
			return ErrorTypeTransient
		}
		// Other network errors could be transient (connection refused, etc.)
		return ErrorTypeTransient
	}

	// System call errors
	var syscallErr *syscall.Errno
	if errors.As(err, &syscallErr) {
		switch *syscallErr {
		case syscall.ECONNREFUSED, syscall.ECONNRESET, syscall.ETIMEDOUT, syscall.ENETUNREACH:
			return ErrorTypeTransient
		default:
			return ErrorTypePermanent
		}
	}

	// gRPC status errors
	if st, ok := status.FromError(err); ok {
		return classifyGRPCStatus(st.Code())
	}

	// String-based heuristics for common error messages
	errStr := strings.ToLower(err.Error())
	
	// Transient error patterns
	transientPatterns := []string{
		"timeout",
		"deadline exceeded",
		"connection refused",
		"connection reset",
		"temporary failure",
		"unavailable",
		"rate limit",
		"too many requests",
		"service unavailable",
		"gateway timeout",
		"network unreachable",
	}
	
	for _, pattern := range transientPatterns {
		if strings.Contains(errStr, pattern) {
			return ErrorTypeTransient
		}
	}

	// Permanent error patterns
	permanentPatterns := []string{
		"invalid",
		"validation failed",
		"not found",
		"unauthorized",
		"forbidden",
		"bad request",
		"missing",
		"malformed",
	}
	
	for _, pattern := range permanentPatterns {
		if strings.Contains(errStr, pattern) {
			return ErrorTypePermanent
		}
	}

	// Default to transient for unknown errors (conservative approach)
	// Better to retry unnecessarily than to give up on recoverable errors
	return ErrorTypeTransient
}

// classifyGRPCStatus classifies gRPC status codes as transient or permanent.
func classifyGRPCStatus(code codes.Code) ErrorType {
	switch code {
	// Transient errors
	case codes.Unavailable,        // Service unavailable
		codes.DeadlineExceeded,    // Timeout
		codes.ResourceExhausted,   // Rate limiting
		codes.Aborted,             // Conflict, may succeed on retry
		codes.Internal,            // Internal server error
		codes.Unknown:             // Unknown error, might be transient
		return ErrorTypeTransient

	// Permanent errors
	case codes.InvalidArgument,    // Bad input
		codes.NotFound,            // Resource doesn't exist
		codes.AlreadyExists,       // Duplicate
		codes.PermissionDenied,    // Authorization issue
		codes.Unauthenticated,     // Authentication issue
		codes.FailedPrecondition,  // Precondition not met
		codes.OutOfRange,          // Out of valid range
		codes.Unimplemented:       // Not implemented
		return ErrorTypePermanent

	// Cautious defaults
	case codes.Canceled:
		return ErrorTypePermanent // Explicit cancellation
	default:
		return ErrorTypeTransient // Unknown codes treated as transient
	}
}

// IsRetryable returns true if the error is classified as transient.
func IsRetryable(err error) bool {
	return ClassifyError(err) == ErrorTypeTransient
}
