"""Shared telemetry module for HDRP Python services.

Provides OpenTelemetry distributed tracing and Prometheus metrics
for Python services with automatic instrumentation decorators.
"""

import functools
import logging
import os
from typing import Optional, Callable, Any, Dict
from prometheus_client import Counter, Histogram, start_http_server, REGISTRY
import grpc

logger = logging.getLogger(__name__)

# Lazy imports for OpenTelemetry
_otel_initialized = False
_tracer = None
_meter = None


def init_telemetry(
    service_name: str,
    otlp_endpoint: Optional[str] = None,
    metrics_port: int = 9091
) -> None:
    """Initialize OpenTelemetry tracing and Prometheus metrics.
    
    Args:
        service_name: Name of the service for tracing
        otlp_endpoint: OTLP endpoint for traces (e.g., 'http://localhost:4318')
        metrics_port: Port for Prometheus metrics HTTP server
    """
    global _otel_initialized, _tracer, _meter
    
    if _otel_initialized:
        return
    
    try:
        from opentelemetry import trace, metrics as otel_metrics
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.semconv.resource import ResourceAttributes
        
        # Get OTLP endpoint from env or parameter
        endpoint = otlp_endpoint or os.getenv("OTLP_ENDPOINT", "http://localhost:4318")
        
        # Create resource with service name
        resource = Resource(attributes={
            ResourceAttributes.SERVICE_NAME: service_name,
            ResourceAttributes.SERVICE_VERSION: "1.0.0",
        })
        
        # Set up tracing
        trace_provider = TracerProvider(resource=resource)
        
        # Only add exporter if endpoint is configured
        if endpoint:
            try:
                span_exporter = OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces")
                span_processor = BatchSpanProcessor(span_exporter)
                trace_provider.add_span_processor(span_processor)
                logger.info(f"OpenTelemetry tracing initialized with endpoint: {endpoint}")
            except Exception as e:
                logger.warning(f"Failed to initialize OTLP exporter: {e}. Tracing disabled.")
        
        trace.set_tracer_provider(trace_provider)
        _tracer = trace.get_tracer(service_name)
        
        # Set up metrics provider
        meter_provider = MeterProvider(resource=resource)
        otel_metrics.set_meter_provider(meter_provider)
        _meter = otel_metrics.get_meter(service_name)
        
        # Start Prometheus HTTP server for metrics
        try:
            start_http_server(metrics_port)
            logger.info(f"Prometheus metrics server started on port {metrics_port}")
        except Exception as e:
            logger.warning(f"Failed to start Prometheus metrics server: {e}")
        
        _otel_initialized = True
        
    except ImportError as e:
        logger.warning(f"OpenTelemetry not installed: {e}. Telemetry disabled.")
    except Exception as e:
        logger.error(f"Failed to initialize telemetry: {e}")


# Prometheus metrics
rpc_latency = Histogram(
    'hdrp_python_rpc_latency_seconds',
    'RPC call latency in seconds',
    ['service', 'method', 'status']
)

rpc_count = Counter(
    'hdrp_python_rpc_total',
    'Total RPC calls',
    ['service', 'method', 'status']
)


def extract_trace_context(context: grpc.ServicerContext) -> Optional[Any]:
    """Extract OpenTelemetry trace context from gRPC metadata.
    
    Args:
        context: gRPC servicer context
        
    Returns:
        Trace context or None if not available
    """
    if not _otel_initialized or not _tracer:
        return None
    
    try:
        from opentelemetry.propagate import extract
        
        # Extract metadata from gRPC context
        metadata = dict(context.invocation_metadata())
        
        # Extract trace context using W3C trace context propagation
        return extract(metadata)
        
    except Exception as e:
        logger.debug(f"Failed to extract trace context: {e}")
        return None


def trace_rpc(method_name: Optional[str] = None) -> Callable:
    """Decorator to automatically trace RPC methods.
    
    Args:
        method_name: Optional method name override
        
    Usage:
        @trace_rpc("Research")
        def Research(self, request, context):
            # method implementation
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, request, context: grpc.ServicerContext, *args, **kwargs) -> Any:
            service_name = self.__class__.__name__
            rpc_method = method_name or func.__name__
            
            # Extract parent trace context from gRPC metadata
            parent_context = extract_trace_context(context)
            
            # Start tracing span
            if _tracer:
                with _tracer.start_as_current_span(
                    f"{service_name}/{rpc_method}",
                    context=parent_context,
                    attributes={
                        "rpc.service": service_name,
                        "rpc.method": rpc_method,
                        "run.id": getattr(request, 'run_id', 'unknown'),
                    }
                ) as span:
                    try:
                        import time
                        start_time = time.time()
                        result = func(self, request, context, *args, **kwargs)
                        duration = time.time() - start_time
                        
                        # Record metrics
                        rpc_latency.labels(
                            service=service_name,
                            method=rpc_method,
                            status='success'
                        ).observe(duration)
                        rpc_count.labels(
                            service=service_name,
                            method=rpc_method,
                            status='success'
                        ).inc()
                        
                        # Add span attributes
                        span.set_attribute("rpc.status", "success")
                        span.set_attribute("rpc.duration_seconds", duration)
                        
                        return result
                        
                    except Exception as e:
                        import time
                        duration = time.time() - start_time if 'start_time' in locals() else 0
                        
                        # Record error metrics
                        rpc_latency.labels(
                            service=service_name,
                            method=rpc_method,
                            status='error'
                        ).observe(duration)
                        rpc_count.labels(
                            service=service_name,
                            method=rpc_method,
                            status='error'
                        ).inc()
                        
                        # Record error in span
                        span.record_exception(e)
                        span.set_attribute("rpc.status", "error")
                        span.set_attribute("error.type", type(e).__name__)
                        
                        raise
            else:
                # Telemetry not initialized, just run the function
                import time
                start_time = time.time()
                try:
                    result = func(self, request, context, *args, **kwargs)
                    duration = time.time() - start_time
                    rpc_latency.labels(
                        service=service_name,
                        method=rpc_method,
                        status='success'
                    ).observe(duration)
                    rpc_count.labels(
                        service=service_name,
                        method=rpc_method,
                        status='success'
                    ).inc()
                    return result
                except Exception as e:
                    duration = time.time() - start_time
                    rpc_latency.labels(
                        service=service_name,
                        method=rpc_method,
                        status='error'
                    ).observe(duration)
                    rpc_count.labels(
                        service=service_name,
                        method=rpc_method,
                        status='error'
                    ).inc()
                    raise
        
        return wrapper
    return decorator


def add_span_attributes(**attributes: Any) -> None:
    """Add attributes to the current active span.
    
    Args:
        **attributes: Key-value pairs to add as span attributes
    """
    if not _tracer:
        return
    
    try:
        from opentelemetry import trace
        span = trace.get_current_span()
        if span and span.is_recording():
            for key, value in attributes.items():
                span.set_attribute(key, value)
    except Exception as e:
        logger.debug(f"Failed to add span attributes: {e}")


def record_metric(name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
    """Record a custom metric.
    
    Args:
        name: Metric name
        value: Metric value
        labels: Optional metric labels
    """
    # This is a simple wrapper for custom metrics
    # In a production system, you'd register these dynamically
    logger.debug(f"Recording metric {name}={value} with labels={labels}")
