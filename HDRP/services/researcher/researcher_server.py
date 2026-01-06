#!/usr/bin/env python3
"""Researcher Service gRPC Server.

Wraps ResearcherService with gRPC interface for claim extraction.
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
from HDRP.services.researcher.service import ResearcherService
from HDRP.tools.search.factory import SearchFactory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ResearcherServicer(hdrp_services_pb2_grpc.ResearcherServiceServicer):
    """Implements ResearcherService gRPC interface."""
    
    def __init__(self):
        # Initialize search provider from environment
        self.search_provider = SearchFactory.from_env()
        logger.info(f"Initialized search provider: {type(self.search_provider).__name__}")
    
    def Research(self, request, context):
        """Executes research on a query and returns atomic claims.
        
        Args:
            request: ResearchRequest with query, source_node_id, run_id.
            context: gRPC context.
            
        Returns:
            ResearchResponse with extracted claims.
        """
        query = request.query
        source_node_id = request.source_node_id or "root"
        run_id = request.run_id
        
        logger.info(f"Research request: query='{query}', node={source_node_id}, run_id={run_id}")
        
        try:
            # Create researcher service instance
            researcher = ResearcherService(
                search_provider=self.search_provider,
                run_id=run_id
            )
            
            # Execute research
            claims = researcher.research(query, source_node_id=source_node_id)
            
            # Convert AtomicClaim objects to protobuf messages
            pb_claims = []
            for claim in claims:
                pb_claim = hdrp_services_pb2.AtomicClaim(
                    statement=claim.statement,
                    source_url=claim.source_url,
                    support_text=claim.support_text,
                    source_node_id=claim.source_node_id or "",
                    timestamp=claim.timestamp,
                    source_title=claim.source_title or "",
                    source_rank=claim.source_rank or 0
                )
                pb_claims.append(pb_claim)
            
            logger.info(f"Research completed: {len(pb_claims)} claims extracted")
            
            return hdrp_services_pb2.ResearchResponse(
                claims=pb_claims,
                total_sources=len(set(c.source_url for c in claims))
            )
            
        except Exception as e:
            logger.error(f"Research failed: {e}", exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Research failed: {str(e)}")
            return hdrp_services_pb2.ResearchResponse(claims=[], total_sources=0)


def serve(port: int = 50052):
    """Starts the Researcher gRPC server."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    hdrp_services_pb2_grpc.add_ResearcherServiceServicer_to_server(
        ResearcherServicer(), server
    )
    
    address = f'[::]:{port}'
    server.add_insecure_port(address)
    server.start()
    
    logger.info(f"Researcher Service started on {address}")
    
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Shutting down Researcher Service...")
        server.stop(0)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Researcher Service gRPC Server')
    parser.add_argument('--port', type=int, default=50052, help='Server port')
    args = parser.parse_args()
    
    serve(args.port)
