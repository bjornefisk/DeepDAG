#!/usr/bin/env python3
"""Synthesizer Service gRPC Server.

Wraps SynthesizerService with gRPC interface for report generation.
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
from HDRP.services.synthesizer.service import SynthesizerService
from HDRP.services.shared.claims import AtomicClaim, CritiqueResult

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SynthesizerServicer(hdrp_services_pb2_grpc.SynthesizerServiceServicer):
    """Implements SynthesizerService gRPC interface."""
    
    def __init__(self):
        self.synthesizer = SynthesizerService()
    
    def Synthesize(self, request, context):
        """Synthesizes verified claims into a markdown report.
        
        Args:
            request: SynthesizeRequest with verification results and context.
            context: gRPC context.
            
        Returns:
            SynthesizeResponse with markdown report.
        """
        run_id = request.run_id
        ctx = dict(request.context) if request.context else {}
        
        logger.info(f"Synthesize request: run_id={run_id}, results={len(request.verification_results)}")
        
        try:
            # Convert protobuf verification results to CritiqueResult objects
            critique_results = []
            for pb_result in request.verification_results:
                # Convert protobuf claim to AtomicClaim
                claim = AtomicClaim(
                    statement=pb_result.claim.statement,
                    source_url=pb_result.claim.source_url,
                    support_text=pb_result.claim.support_text,
                    source_node_id=pb_result.claim.source_node_id or None,
                    timestamp=pb_result.claim.timestamp,
                    source_title=pb_result.claim.source_title or None,
                    source_rank=pb_result.claim.source_rank if pb_result.claim.source_rank > 0 else None
                )
                
                # Create CritiqueResult
                result = CritiqueResult(
                    claim=claim,
                    is_valid=pb_result.is_valid,
                    reasoning=pb_result.reasoning
                )
                critique_results.append(result)
            
            # Synthesize report
            report = self.synthesizer.synthesize(
                verification_results=critique_results,
                context=ctx
            )
            
            logger.info(f"Synthesis completed: report length={len(report)} chars")
            
            # For MVP, artifact_uri is empty (could be extended to save to file)
            return hdrp_services_pb2.SynthesizeResponse(
                report=report,
                artifact_uri=""
            )
            
        except Exception as e:
            logger.error(f"Synthesis failed: {e}", exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Synthesis failed: {str(e)}")
            return hdrp_services_pb2.SynthesizeResponse(
                report="# Error\n\nFailed to generate report.",
                artifact_uri=""
            )


def serve(port: int = 50054):
    """Starts the Synthesizer gRPC server."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    hdrp_services_pb2_grpc.add_SynthesizerServiceServicer_to_server(
        SynthesizerServicer(), server
    )
    
    address = f'[::]:{port}'
    server.add_insecure_port(address)
    server.start()
    
    logger.info(f"Synthesizer Service started on {address}")
    
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Shutting down Synthesizer Service...")
        server.stop(0)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Synthesizer Service gRPC Server')
    parser.add_argument('--port', type=int, default=50054, help='Server port')
    args = parser.parse_args()
    
    serve(args.port)
