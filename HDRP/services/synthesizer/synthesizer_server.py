#!/usr/bin/env python3
"""Synthesizer Service gRPC Server.

Wraps SynthesizerService with gRPC interface for report generation.
"""

import grpc
import logging

# Setup paths before imports
from HDRP.services.shared.grpc_base import setup_grpc_paths, run_server_main
setup_grpc_paths()

from HDRP.api.gen.python.HDRP.api.proto import hdrp_services_pb2
from HDRP.api.gen.python.HDRP.api.proto import hdrp_services_pb2_grpc
from HDRP.services.synthesizer.service import SynthesizerService
from HDRP.services.shared.claims import AtomicClaim, CritiqueResult
from HDRP.services.shared.telemetry import trace_rpc, add_span_attributes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SynthesizerServicer(hdrp_services_pb2_grpc.SynthesizerServiceServicer):
    """Implements SynthesizerService gRPC interface."""
    
    def __init__(self):
        self.synthesizer = SynthesizerService()
    
    @trace_rpc("Synthesize")
    def Synthesize(self, request, context):
        """Synthesizes verified claims into a markdown report.
        
        Args:
            request: SynthesizeRequest with verification results and context.
            context: gRPC context.
            
        Returns:
            SynthesizeResponse with markdown report.
        """
        from HDRP.services.shared.errors import (
            handle_rpc_error, SynthesizerError
        )
        
        try:
            # Validate request
            if not request.verification_results:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details('At least one verification result is required')
                return hdrp_services_pb2.SynthesizeResponse(
                    report="# Error\n\nNo verification results provided.",
                    artifact_uri=""
                )
            
            run_id = request.run_id
            if not run_id:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details('run_id is required')
                return hdrp_services_pb2.SynthesizeResponse(
                    report="# Error\n\nrun_id is required.",
                    artifact_uri=""
                )
            
            ctx = dict(request.context) if request.context else {}
            
            logger.info(f"Synthesize request: run_id={run_id}, results={len(request.verification_results)}")
            
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
                    reason=pb_result.reasoning,
                    entailment_score=getattr(pb_result, 'entailment_score', 0.0)
                )
                critique_results.append(result)
            
            # Synthesize report with error handling (supports partial results)
            report = self.synthesizer.synthesize(
                verification_results=critique_results,
                context=ctx,
                graph_data=None,  # Could be passed from request if available
                run_id=run_id
            )
            
            logger.info(f"Synthesis completed: report length={len(report)} chars")
            
            # Add span attributes
            add_span_attributes(
                report_length=len(report),
                verification_results_count=len(request.verification_results)
            )
            
            # For MVP, artifact_uri is empty (could be extended to save to file)
            return hdrp_services_pb2.SynthesizeResponse(
                report=report,
                artifact_uri=""
            )
        
        except ValueError as e:
            logger.error(f"Validation error: {e}")
            handle_rpc_error(
                e, context, run_id=request.run_id, service="synthesizer",
                additional_context={"result_count": len(request.verification_results)}
            )
            return hdrp_services_pb2.SynthesizeResponse(
                report="# Error\n\nInvalid input provided.",
                artifact_uri=""
            )
        
        except TimeoutError as e:
            logger.error(f"Timeout error: {e}")
            handle_rpc_error(
                e, context, run_id=request.run_id, service="synthesizer",
                additional_context={"result_count": len(request.verification_results)}
            )
            return hdrp_services_pb2.SynthesizeResponse(
                report="# Error\n\nReport generation timed out.",
                artifact_uri=""
            )
            
        except Exception as e:
            # Graceful degradation: generate partial report if possible
            logger.error(f"Synthesis failed: {e}", exc_info=True)
            
            wrapped = SynthesizerError(
                str(e),
                user_message="Unable to generate complete report. Partial results may be available."
            )
            handle_rpc_error(
                wrapped, context, run_id=request.run_id, service="synthesizer",
                additional_context={"result_count": len(request.verification_results)}
            )
            
            # Return partial error report instead of completely failing
            return hdrp_services_pb2.SynthesizeResponse(
                report="# Research Report (Partial)\n\n**Note:** Report generation encountered errors. Some content may be missing.\n\n" + 
                      f"Run ID: {run_id}\n\n**Error:** {str(e)}",
                artifact_uri=""
            )


if __name__ == '__main__':
    run_server_main(
        service_name="synthesizer",
        default_port=50054,
        servicer_factory=SynthesizerServicer,
        add_to_server_fn=hdrp_services_pb2_grpc.add_SynthesizerServiceServicer_to_server,
        default_metrics_port=9093
    )
