package metrics

import (
	"context"
	"log"
	"time"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.4.0"
	"go.opentelemetry.io/otel/trace"
)

var (
	tracerProvider *sdktrace.TracerProvider
	tracer         trace.Tracer
)

// InitTracing initializes OpenTelemetry tracing with OTLP exporter
func InitTracing(serviceName, otlpEndpoint string) error {
	ctx := context.Background()

	// Create OTLP HTTP exporter
	exporter, err := otlptracehttp.New(ctx,
		otlptracehttp.WithEndpoint(otlpEndpoint),
		otlptracehttp.WithInsecure(), // Use insecure for local development
	)
	if err != nil {
		return err
	}

	// Create resource with service information
	res, err := resource.New(ctx,
		resource.WithAttributes(
			semconv.ServiceNameKey.String(serviceName),
			semconv.ServiceVersionKey.String("1.0.0"),
			attribute.String("environment", "development"),
		),
	)
	if err != nil {
		return err
	}

	// Create trace provider
	tracerProvider = sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exporter),
		sdktrace.WithResource(res),
		sdktrace.WithSampler(sdktrace.AlwaysSample()),
	)

	otel.SetTracerProvider(tracerProvider)
	tracer = tracerProvider.Tracer(serviceName)

	log.Printf("[Tracing] Initialized OpenTelemetry with OTLP endpoint: %s", otlpEndpoint)
	return nil
}

// StartSpan starts a new span with the given name
func StartSpan(ctx context.Context, spanName string, attrs ...attribute.KeyValue) (context.Context, trace.Span) {
	if tracer == nil {
		// Tracing not initialized, return no-op span
		return ctx, trace.SpanFromContext(ctx)
	}
	return tracer.Start(ctx, spanName, trace.WithAttributes(attrs...))
}

// AddSpanAttributes adds attributes to the current span
func AddSpanAttributes(ctx context.Context, attrs ...attribute.KeyValue) {
	span := trace.SpanFromContext(ctx)
	if span.IsRecording() {
		span.SetAttributes(attrs...)
	}
}

// AddSpanEvent adds an event to the current span
func AddSpanEvent(ctx context.Context, name string, attrs ...attribute.KeyValue) {
	span := trace.SpanFromContext(ctx)
	if span.IsRecording() {
		span.AddEvent(name, trace.WithAttributes(attrs...))
	}
}

// RecordSpanError records an error on the current span
func RecordSpanError(ctx context.Context, err error) {
	span := trace.SpanFromContext(ctx)
	if span.IsRecording() && err != nil {
		span.RecordError(err)
	}
}

// ShutdownTracing gracefully shuts down the trace provider
func ShutdownTracing() error {
	if tracerProvider == nil {
		return nil
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	return tracerProvider.Shutdown(ctx)
}
