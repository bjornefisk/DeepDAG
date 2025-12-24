from typing import List
from HDRP.tools.search.base import SearchProvider
from HDRP.services.shared.claims import ClaimExtractor, AtomicClaim

class ResearcherService:
    """Service responsible for executing research tasks.
    
    It uses a SearchProvider to find information and a ClaimExtractor to 
    turn unstructured search results into verified atomic claims with 
    explicit source attribution.
    """
    def __init__(self, search_provider: SearchProvider):
        self.search_provider = search_provider
        self.extractor = ClaimExtractor()

    def research(self, query: str) -> List[AtomicClaim]:
        """Performs research on a given query and returns a list of atomic claims.
        
        Each claim will include the source URL and the support text where it was found.
        """
        search_response = self.search_provider.search(query)
        all_claims = []
        
        for result in search_response.results:
            # For the MVP standard, we extract claims directly from the search snippets.
            # This ensures that 'support_text' is always tied to a verified search result.
            extraction = self.extractor.extract(result.snippet, source_url=result.url)
            all_claims.extend(extraction.claims)
            
        return all_claims
