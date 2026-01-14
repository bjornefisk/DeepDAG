from typing import List, Optional
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from HDRP.tools.search.base import SearchProvider, SearchError
from HDRP.services.shared.claims import ClaimExtractor, AtomicClaim
from HDRP.services.shared.logger import ResearchLogger
from HDRP.services.shared.profiling_utils import profile_block, enable_profiling_env

class ResearcherService:
    """Service responsible for executing research tasks.
    
    It uses a SearchProvider to find information and a ClaimExtractor to 
    turn unstructured search results into verified atomic claims with 
    explicit source attribution.
    
    Optimized with concurrent claim extraction for improved performance.
    """
    def __init__(self, search_provider: SearchProvider, run_id: Optional[str] = None):
        self.search_provider = search_provider
        self.extractor = ClaimExtractor()
        self.logger = ResearchLogger("researcher", run_id=run_id)
        self.enable_profiling = enable_profiling_env()
        # Thread pool for concurrent claim extraction
        self._executor = ThreadPoolExecutor(max_workers=4)

    def research(self, query: str, source_node_id: Optional[str] = None) -> List[AtomicClaim]:
        """Performs research on a given query and returns a list of atomic claims.
        
        Each claim will include the source URL and the support text where it was found.
        Optimized with concurrent claim extraction.
        """
        max_retries = 2
        search_response = None
        
        self.logger.log("research_started", {
            "query": query,
            "source_node_id": source_node_id
        })

        # Search with retry logic
        for attempt in range(max_retries + 1):
            try:
                if self.enable_profiling:
                    with profile_block(f"search_{query[:30]}", "profiling_data"):
                        search_response = self.search_provider.search(query)
                else:
                    search_response = self.search_provider.search(query)
                break
            except SearchError as e:
                if attempt < max_retries:
                    self.logger.log("research_retry", {
                        "query": query,
                        "error": str(e),
                        "attempt": attempt + 1
                    })
                    time.sleep(1)
                    continue
                else:
                    self.logger.log("research_failed", {
                        "query": query,
                        "error": str(e),
                        "type": type(e).__name__
                    })
                    raise e
            except Exception as e:
                self.logger.log("research_failed", {
                    "query": query,
                    "error": str(e),
                    "type": type(e).__name__
                })
                raise e

        if not search_response.results:
            self.logger.log("research_failed", {
                "query": query,
                "error": "No results found",
                "type": "EmptyResults"
            })
            return []

        # Concurrent claim extraction from all search results
        if self.enable_profiling:
            with profile_block(f"claim_extraction_{query[:30]}", "profiling_data"):
                all_claims = self._extract_claims_concurrent(
                    search_response.results, source_node_id
                )
        else:
            all_claims = self._extract_claims_concurrent(
                search_response.results, source_node_id
            )
            
        return all_claims
    
    def _extract_claims_concurrent(self, results, source_node_id: Optional[str]) -> List[AtomicClaim]:
        """Extract claims from search results concurrently.
        
        Uses ThreadPoolExecutor to process multiple search results in parallel.
        """
        def extract_from_result(idx_and_result):
            idx, result = idx_and_result
            extraction = self.extractor.extract(
                result.snippet, 
                source_url=result.url, 
                source_node_id=source_node_id,
                source_title=result.title,
                source_rank=idx
            )
            
            # Log traceability metadata for debugging
            if extraction.claims:
                self.logger.log("claims_extracted", {
                    "source_title": result.title,
                    "source_url": result.url,
                    "source_rank": idx,
                    "claims_count": len(extraction.claims)
                })
            
            return extraction.claims
        
        # Process results concurrently
        indexed_results = list(enumerate(results, 1))
        all_claims = []
        
        # Use thread pool to parallelize claim extraction
        futures = [
            self._executor.submit(extract_from_result, item)
            for item in indexed_results
        ]
        
        for future in futures:
            try:
                claims = future.result(timeout=10)
                all_claims.extend(claims)
            except Exception as e:
                self.logger.log("extraction_error", {
                    "error": str(e),
                    "type": type(e).__name__
                })
        
        return all_claims
    
    def __del__(self):
        """Cleanup thread pool on deletion."""
        if hasattr(self, '_executor'):
            self._executor.shutdown(wait=False)