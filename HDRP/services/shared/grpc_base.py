#!/usr/bin/env python3
"""Shared gRPC server utilities.

Consolidates common boilerplate for all HDRP gRPC service servers.
"""

import grpc
from concurrent import futures
import logging
import argparse
import sys
import os


def setup_grpc_paths():
    """Add project root and gRPC gen paths to sys.path for imports."""
    root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
    grpc_gen_path = os.path.join(root_path, "HDRP/api/gen/python/HDRP/api")
    
    if root_path not in sys.path:
        sys.path.insert(0, root_path)
    if grpc_gen_path not in sys.path:
        sys.path.insert(0, grpc_gen_path)


def create_grpc_server(
    servicer_instance,
    add_to_server_fn,
    port: int,
    service_name: str,
    enable_tracing: bool = False,
    otlp_endpoint: str = None,
    metrics_port: int = None
):
    """Create and start a gRPC server with optional telemetry.
    
    Args:
        servicer_instance: Instance of the gRPC servicer implementation
        add_to_server_fn: Function to add servicer to server (e.g., add_ResearcherServiceServicer_to_server)
        port: Port number to listen on
        service_name: Name of the service for logging/telemetry
        enable_tracing: Enable OpenTelemetry tracing
        otlp_endpoint: OTLP endpoint for traces
        metrics_port: Port for Prometheus metrics (if tracing enabled)
    
    Returns:
        The started gRPC server instance
    """
    logger = logging.getLogger(__name__)
    
    # Initialize telemetry if requested
    if enable_tracing:
        from HDRP.services.shared.telemetry import init_telemetry
        init_telemetry(
            service_name=service_name,
            otlp_endpoint=otlp_endpoint,
            metrics_port=metrics_port
        )
        logger.info(f"Telemetry initialized for {service_name} service")
    
    # Create and configure server
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    add_to_server_fn(servicer_instance, server)
    
    address = f'[::]:{port}'
    server.add_insecure_port(address)
    server.start()
    
    logger.info(f"{service_name.capitalize()} Service started on {address}")
    if enable_tracing and metrics_port:
        logger.info(f"Prometheus metrics available on port {metrics_port}")
    
    return server


def run_server_main(
    service_name: str,
    default_port: int,
    servicer_factory,
    add_to_server_fn,
    default_metrics_port: int = None
):
    """Standard main function for gRPC servers.
    
    Handles argparse, logging setup, and server lifecycle.
    
    Args:
        service_name: Name of the service (e.g., "researcher")
        default_port: Default port number
        servicer_factory: Callable that returns servicer instance
        add_to_server_fn: Function to add servicer to server
        default_metrics_port: Default metrics port for telemetry
    """
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # Parse arguments
    parser = argparse.ArgumentParser(
        description=f'{service_name.capitalize()} Service gRPC Server'
    )
    parser.add_argument('--port', type=int, default=default_port, help='Server port')
    parser.add_argument('--enable-tracing', action='store_true', help='Enable OpenTelemetry tracing')
    parser.add_argument('--otlp-endpoint', type=str, default=None, help='OTLP endpoint for traces')
    args = parser.parse_args()
    
    # Create servicer instance
    servicer = servicer_factory()
    
    # Start server
    server = create_grpc_server(
        servicer_instance=servicer,
        add_to_server_fn=add_to_server_fn,
        port=args.port,
        service_name=service_name,
        enable_tracing=args.enable_tracing,
        otlp_endpoint=args.otlp_endpoint,
        metrics_port=default_metrics_port
    )
    
    # Wait for termination
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info(f"Shutting down {service_name.capitalize()} Service...")
        server.stop(0)
