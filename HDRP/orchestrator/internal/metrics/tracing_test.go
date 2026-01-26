package metrics

import (
	"context"
	"testing"
)

func TestTracingNoopDoesNotPanic(t *testing.T) {
	ctx := context.Background()

	_, span := StartSpan(ctx, "noop")
	if span == nil {
		t.Fatal("expected non-nil span")
	}

	AddSpanAttributes(ctx)
	AddSpanEvent(ctx, "event")
	RecordSpanError(ctx, nil)

	if err := ShutdownTracing(); err != nil {
		t.Fatalf("ShutdownTracing failed: %v", err)
	}
}
