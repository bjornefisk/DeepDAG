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
from HDRP.services.shared.logger import ResearchLogger

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PrincipalServicer(hdrp_services_pb2_grpc.PrincipalServiceServicer):
    """Implements PrincipalService gRPC interface."""
    
    def __init__(self):
        self.logger = ResearchLogger("principal_server")
    
    def DecomposeQuery(self, request, context):
        """Decomposes a query into a DAG of atomic research tasks.
        
        For MVP, creates a linear DAG: query -> researcher -> critic -> synthesizer.
        Production would use an LLM to identify dependencies and entities.
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
            
            # Create a simple linear DAG for MVP
            # Node IDs follow the pattern: <type>_<index>
            nodes = [
                hdrp_services_pb2.Node(
                    id="researcher_1",
                    type="researcher",
                    config={"query": query},
                    status="CREATED",
                    relevance_score=1.0,
                    depth=0
                ),
                hdrp_services_pb2.Node(
                    id="critic_1",
                    type="critic",
                    config={"task": query},
                    status="CREATED",
                    relevance_score=1.0,
                    depth=1
                ),
                hdrp_services_pb2.Node(
                    id="synthesizer_1",
                    type="synthesizer",
                    config={"query": query},
                    status="CREATED",
                    relevance_score=1.0,
                    depth=2
                )
            ]
            
            edges = [
                hdrp_services_pb2.Edge(from_="researcher_1", to="critic_1"),
                hdrp_services_pb2.Edge(from_="critic_1", to="synthesizer_1")
            ]
            
            graph = hdrp_services_pb2.Graph(
                id=run_id,
                nodes=nodes,
                edges=edges,
                metadata={
                    "goal": query,
                    "run_id": run_id
                }
            )
            
            subtasks = [query]  # For MVP, single task
            
            return hdrp_services_pb2.DecompositionResponse(
                graph=graph,
                subtasks=subtasks
            )
            
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
