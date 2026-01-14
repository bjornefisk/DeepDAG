#!/usr/bin/env python3
"""Principal Service gRPC Server.

Decomposes complex queries into DAG structures with atomic research tasks.
"""

import grpc
from concurrent import futures
import logging
from typing import Optional
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from HDRP.api.gen.python.HDRP.api.proto import hdrp_services_pb2
from HDRP.api.gen.python.HDRP.api.proto import hdrp_services_pb2_grpc
from HDRP.services.principal.service import PrincipalService
from HDRP.services.shared.logger import ResearchLogger

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PrincipalServicer(hdrp_services_pb2_grpc.PrincipalServiceServicer):
    """Implements PrincipalService gRPC interface."""
    
    def __init__(self):
        self.logger = ResearchLogger("principal_server")
        self.service = PrincipalService()
    
    def DecomposeQuery(self, request, context):
        """Decomposes a query into a DAG of atomic research tasks.
        
        Uses LLM to identify dependencies and parallel work streams.
        Falls back to linear DAG if LLM is unavailable.
        """
        try:
            # Validate query (protobuf validation should catch empty strings, but we add business logic)
            query = request.query.strip()
            if not query:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details('Query cannot be empty or whitespace only')
                return hdrp_services_pb2.DecompositionResponse()
            
            if len(query) > 500:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details('Query exceeds maximum length of 500 characters')
                return hdrp_services_pb2.DecompositionResponse()
            
            run_id = request.run_id or self.logger.run_id
            
            self.logger.log("decompose_query", {
                "query": query,
                "run_id": run_id
            })
            
            # Use LLM-based decomposition service
            response = self.service.decompose_query(query, run_id)
            
            return response
            
        except ValueError as e:
            self.logger.log("decompose_error", {
                "error": str(e),
                "error_type": "ValueError"
            })
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(f'Invalid input: {str(e)}')
            return hdrp_services_pb2.DecompositionResponse()
        
        except Exception as e:
            self.logger.log("decompose_error", {
                "error": str(e),
                "error_type": type(e).__name__
            })
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f'Internal error: {str(e)}')
            return hdrp_services_pb2.DecompositionResponse()


def serve(port: int = 50051):
    """Starts the Principal gRPC server."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    hdrp_services_pb2_grpc.add_PrincipalServiceServicer_to_server(
        PrincipalServicer(), server
    )
    
    address = f'[::]:{port}'
    server.add_insecure_port(address)
    server.start()
    
    logger.info(f"Principal Service started on {address}")
    
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Shutting down Principal Service...")
        server.stop(0)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Principal Service gRPC Server')
    parser.add_argument('--port', type=int, default=50051, help='Server port')
    args = parser.parse_args()
    
    serve(args.port)
