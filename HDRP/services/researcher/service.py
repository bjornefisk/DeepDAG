from typing import List, Optional
import time
from HDRP.tools.search.base import SearchProvider, SearchError
from HDRP.services.shared.claims import ClaimExtractor, AtomicClaim
from HDRP.services.shared.logger import ResearchLogger

class ResearcherService:
    """Service responsible for executing research tasks.
    
    It uses a SearchProvider to find information and a ClaimExtractor to 
    turn unstructured search results into verified atomic claims with 
    explicit source attribution.
    """
    def __init__(self, search_provider: SearchProvider, run_id: Optional[str] = None):
        self.search_provider = search_provider
        self.extractor = ClaimExtractor()
        self.logger = ResearchLogger("researcher", run_id=run_id)

    def research(self, query: str, source_node_id: Optional[str] = None) -> List[AtomicClaim]:
        """Performs research on a given query and returns a list of atomic claims.
        
        Each claim will include the source URL and the support text where it was found.
        """
        max_retries = 2
        search_response = None

        for attempt in range(max_retries + 1):
            try:
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

        all_claims = []
        
        for idx, result in enumerate(search_response.results, 1):
            # For the MVP standard, we extract claims directly from the search snippets.
            # This ensures that 'support_text' is always tied to a verified search result.
            # We now pass full traceability metadata: title and search rank position.
            extraction = self.extractor.extract(
                result.snippet, 
                source_url=result.url, 
                source_node_id=source_node_id,
                source_title=result.title,
                source_rank=idx
            )
            all_claims.extend(extraction.claims)
            
            # Log traceability metadata for debugging
            if extraction.claims:
                self.logger.log("claims_extracted", {
                    "source_title": result.title,
                    "source_url": result.url,
                    "source_rank": idx,
                    "claims_count": len(extraction.claims)
                })
            
        return all_claims