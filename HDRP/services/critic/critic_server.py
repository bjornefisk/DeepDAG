#!/usr/bin/env python3
"""Critic Service gRPC Server.

Wraps CriticService with gRPC interface for claim verification.
"""

import grpc
from concurrent import futures
import logging
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from HDRP.api.gen.python.HDRP.api.proto import hdrp_services_pb2
from HDRP.api.gen.python.HDRP.api.proto import hdrp_services_pb2_grpc
from HDRP.services.critic.service import CriticService
from HDRP.services.shared.claims import AtomicClaim

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CriticServicer(hdrp_services_pb2_grpc.CriticServiceServicer):
    """Implements CriticService gRPC interface."""
    
    def Verify(self, request, context):
        """Verifies claims against source text and task relevance.
        
        Args:
            request: VerifyRequest with claims and task.
            context: gRPC context.
            
        Returns:
            VerifyResponse with verification results.
        """
        task = request.task
        run_id = request.run_id
        
        logger.info(f"Verify request: task='{task}', run_id={run_id}, claims={len(request.claims)}")
        
        try:
            # Convert protobuf claims to AtomicClaim objects
            claims = []
            for pb_claim in request.claims:
                claim = AtomicClaim(
                    statement=pb_claim.statement,
                    source_url=pb_claim.source_url,
                    support_text=pb_claim.support_text,
                    source_node_id=pb_claim.source_node_id or None,
                    timestamp=pb_claim.timestamp,
                    source_title=pb_claim.source_title or None,
                    source_rank=pb_claim.source_rank if pb_claim.source_rank > 0 else None
                )
                claims.append(claim)
            
            # Create critic service instance
            critic = CriticService(run_id=run_id)
            
            # Verify claims
            critique_results = critic.verify(claims, task=task)
            
            # Convert CritiqueResult objects to protobuf messages
            pb_results = []
            verified_count = 0
            rejected_count = 0
            
            for result in critique_results:
                # Convert the claim back to protobuf
                pb_claim = hdrp_services_pb2.AtomicClaim(
                    statement=result.claim.statement,
                    source_url=result.claim.source_url,
                    support_text=result.claim.support_text,
                    source_node_id=result.claim.source_node_id or "",
                    timestamp=result.claim.timestamp,
                    source_title=result.claim.source_title or "",
                    source_rank=result.claim.source_rank or 0
                )
                
                pb_result = hdrp_services_pb2.CritiqueResult(
                    claim=pb_claim,
                    is_valid=result.is_valid,
                    reasoning=result.reasoning,
                    confidence=1.0  # Default confidence
                )
                pb_results.append(pb_result)
                
                if result.is_valid:
                    verified_count += 1
                else:
                    rejected_count += 1
            
            logger.info(f"Verification completed: verified={verified_count}, rejected={rejected_count}")
            
            return hdrp_services_pb2.VerifyResponse(
                results=pb_results,
                verified_count=verified_count,
                rejected_count=rejected_count
            )
            
        except Exception as e:
            logger.error(f"Verification failed: {e}", exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Verification failed: {str(e)}")
            return hdrp_services_pb2.VerifyResponse(
                results=[],
                verified_count=0,
                rejected_count=0
            )


def serve(port: int = 50053):
    """Starts the Critic gRPC server."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    hdrp_services_pb2_grpc.add_CriticServiceServicer_to_server(
        CriticServicer(), server
    )
    
    address = f'[::]:{port}'
    server.add_insecure_port(address)
    server.start()
    
    logger.info(f"Critic Service started on {address}")
    
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Shutting down Critic Service...")
        server.stop(0)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Critic Service gRPC Server')
    parser.add_argument('--port', type=int, default=50053, help='Server port')
    args = parser.parse_args()
    
    serve(args.port)
