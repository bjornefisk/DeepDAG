#!/usr/bin/env python3
"""Critic Service gRPC Server.

Wraps CriticService with gRPC interface for claim verification.
"""

import grpc
import logging

from HDRP.services.shared.grpc_base import run_server_main

from HDRP.api.gen.python import hdrp_services_pb2
from HDRP.api.gen.python import hdrp_services_pb2_grpc
from HDRP.services.critic.service import CriticService
from HDRP.services.critic.nli_http_client import NLIHttpClient
from HDRP.services.shared.claims import AtomicClaim
from HDRP.services.shared.telemetry import trace_rpc, add_span_attributes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CriticServicer(hdrp_services_pb2_grpc.CriticServiceServicer):
    """Implements CriticService gRPC interface."""

    def __init__(self) -> None:
        self._nli_client = NLIHttpClient()
    
    @trace_rpc("Verify")
    def Verify(self, request, context):
        """Verifies claims against source text and task relevance.
        
        Args:
            request: VerifyRequest with claims and task.
            context: gRPC context.
            
        Returns:
            VerifyResponse with verification results.
        """
        from HDRP.services.shared.errors import (
            handle_rpc_error, CriticError
        )
        
        try:
            # Validate request
            if not request.claims:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details('At least one claim is required')
                return hdrp_services_pb2.VerifyResponse(
                    results=[],
                    verified_count=0,
                    rejected_count=0
                )
            
            task = request.task.strip()
            if not task:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details('Task cannot be empty')
                return hdrp_services_pb2.VerifyResponse(
                    results=[],
                    verified_count=0,
                    rejected_count=0
                )
            
            run_id = request.run_id
            if not run_id:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details('run_id is required')
                return hdrp_services_pb2.VerifyResponse(
                    results=[],
                    verified_count=0,
                    rejected_count=0
                )
            
            logger.info(f"Verify request: task='{task}', run_id={run_id}, claims={len(request.claims)}")
            
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
            
            metadata = dict(context.invocation_metadata())
            nli_variant = metadata.get("x-model-variant")

            # Create critic service instance
            critic = CriticService(
                run_id=run_id,
                nli_client=self._nli_client,
                nli_variant=nli_variant,
            )
            
            # Verify claims with error handling
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
            
            # Add span attributes
            add_span_attributes(
                claims_total=len(request.claims),
                verified_count=verified_count,
                rejected_count=rejected_count
            )
            
            return hdrp_services_pb2.VerifyResponse(
                results=pb_results,
                verified_count=verified_count,
                rejected_count=rejected_count
            )
        
        except ValueError as e:
            logger.error(f"Validation error: {e}")
            handle_rpc_error(
                e, context, run_id=request.run_id, service="critic",
                additional_context={"task": request.task, "claim_count": len(request.claims)}
            )
            return hdrp_services_pb2.VerifyResponse(
                results=[],
                verified_count=0,
                rejected_count=0
            )
        
        except TimeoutError as e:
            logger.error(f"Timeout error: {e}")
            handle_rpc_error(
                e, context, run_id=request.run_id, service="critic",
                additional_context={"task": request.task}
            )
            return hdrp_services_pb2.VerifyResponse(
                results=[],
                verified_count=0,
                rejected_count=0
            )
            
        except Exception as e:
            # Graceful degradation: return empty verification results
            logger.error(f"Verification failed: {e}", exc_info=True)
            
            wrapped = CriticError(
                str(e),
                user_message="Unable to verify claims. Continuing with unverified results."
            )
            handle_rpc_error(
                wrapped, context, run_id=request.run_id, service="critic",
                additional_context={"task": request.task, "claim_count": len(request.claims)}
            )
            
            # Return empty results instead of failing
            return hdrp_services_pb2.VerifyResponse(
                results=[],
                verified_count=0,
                rejected_count=0
            )


if __name__ == '__main__':
    run_server_main(
        service_name="critic",
        default_port=50053,
        servicer_factory=CriticServicer,
        add_to_server_fn=hdrp_services_pb2_grpc.add_CriticServiceServicer_to_server,
        default_metrics_port=9092
    )
