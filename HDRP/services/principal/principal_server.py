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

# Add project root and gRPC gen path to sys.path
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
grpc_gen_path = os.path.join(root_path, "HDRP/api/gen/python/HDRP/api")
if root_path not in sys.path:
    sys.path.insert(0, root_path)
if grpc_gen_path not in sys.path:
    sys.path.insert(0, grpc_gen_path)

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
        from HDRP.services.shared.errors import (
            handle_rpc_error, PrincipalError
        )
        
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
            
            # Use LLM-based decomposition service (has built-in fallback to linear DAG)
            response = self.service.decompose_query(query, run_id)
            
            return response
            
        except ValueError as e:
            self.logger.log("decompose_error", {
                "error": str(e),
                "error_type": "ValueError"
            })
            handle_rpc_error(
                e, context, run_id=request.run_id, service="principal",
                additional_context={"query": request.query}
            )
            return hdrp_services_pb2.DecompositionResponse()
        
        except Exception as e:
            # Graceful degradation: service already has fallback to linear DAG
            # but if it completely fails, return empty response
            self.logger.log("decompose_error", {
                "error": str(e),
                "error_type": type(e).__name__
            })
            
            wrapped = PrincipalError(
                str(e),
                user_message="Unable to decompose query. Using simplified research plan."
            )
            handle_rpc_error(
                wrapped, context, run_id=request.run_id, service="principal",
                additional_context={"query": request.query}
            )
            
            # Return empty response (orchestrator should handle this)
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
