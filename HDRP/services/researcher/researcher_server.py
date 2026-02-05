#!/usr/bin/env python3
"""Researcher Service gRPC Server.

Wraps ResearcherService with gRPC interface for claim extraction.
"""

import grpc
import logging
from typing import Optional

# Setup paths before imports
from HDRP.services.shared.grpc_base import setup_grpc_paths, run_server_main
setup_grpc_paths()

from HDRP.api.gen.python import hdrp_services_pb2
from HDRP.api.gen.python import hdrp_services_pb2_grpc
from HDRP.services.researcher.service import ResearcherService
from HDRP.tools.search.factory import SearchFactory
from HDRP.services.shared.telemetry import trace_rpc, add_span_attributes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ResearcherServicer(hdrp_services_pb2_grpc.ResearcherServiceServicer):
    """Implements ResearcherService gRPC interface."""
    
    def __init__(self):
        # Initialize search provider from environment
        self.search_provider = SearchFactory.from_env()
        logger.info(f"Initialized search provider: {type(self.search_provider).__name__}")
    
    @trace_rpc("Research")
    def Research(self, request, context):
        """Executes research on a query and returns atomic claims.
        
        Args:
            request: ResearchRequest with query, source_node_id, run_id.
            context: gRPC context.
            
        Returns:
            ResearchResponse with extracted claims.
        """
        from HDRP.services.shared.errors import (
            handle_rpc_error, ResearcherError, SearchProviderError
        )
        
        try:
            # Validate request
            query = request.query.strip()
            if not query:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details('Query cannot be empty or whitespace only')
                return hdrp_services_pb2.ResearchResponse(claims=[], total_sources=0)
            
            if len(query) > 500:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details('Query exceeds maximum length of 500 characters')
                return hdrp_services_pb2.ResearchResponse(claims=[], total_sources=0)
            
            source_node_id = request.source_node_id or "root"
            run_id = request.run_id
            
            if not run_id:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details('run_id is required')
                return hdrp_services_pb2.ResearchResponse(claims=[], total_sources=0)
            
            logger.info(f"Research request: query='{query}', node={source_node_id}, run_id={run_id}")
            
            # Create researcher service instance
            researcher = ResearcherService(
                search_provider=self.search_provider,
                run_id=run_id
            )
            
            # Execute research with error handling
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
            
            # Add span attributes for tracing
            add_span_attributes(
                claims_extracted=len(pb_claims),
                total_sources=len(set(c.source_url for c in claims)),
                query_length=len(query)
            )
            
            return hdrp_services_pb2.ResearchResponse(
                claims=pb_claims,
                total_sources=len(set(c.source_url for c in claims))
            )
        
        except ValueError as e:
            logger.error(f"Validation error: {e}")
            handle_rpc_error(
                e, context, run_id=request.run_id, service="researcher",
                additional_context={"query": request.query}
            )
            return hdrp_services_pb2.ResearchResponse(claims=[], total_sources=0)
        
        except TimeoutError as e:
            logger.error(f"Timeout error: {e}")
            handle_rpc_error(
                e, context, run_id=request.run_id, service="researcher",
                additional_context={"query": request.query}
            )
            return hdrp_services_pb2.ResearchResponse(claims=[], total_sources=0)
        
        except Exception as e:
            # Graceful degradation: return empty claims instead of crashing
            logger.error(f"Research failed: {e}", exc_info=True)
            
            # Wrap in ResearcherError for better user messages
            wrapped = ResearcherError(
                str(e),
                user_message="Unable to complete research. The search service may be unavailable."
            )
            handle_rpc_error(
                wrapped, context, run_id=request.run_id, service="researcher",
                additional_context={"query": request.query, "source_node_id": request.source_node_id}
            )
            
            # Return empty claims instead of failing
            return hdrp_services_pb2.ResearchResponse(claims=[], total_sources=0)


if __name__ == '__main__':
    run_server_main(
        service_name="researcher",
        default_port=50052,
        servicer_factory=ResearcherServicer,
        add_to_server_fn=hdrp_services_pb2_grpc.add_ResearcherServiceServicer_to_server,
        default_metrics_port=9091
    )
