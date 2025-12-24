from typing import List, Tuple
from HDRP.services.shared.claims import AtomicClaim

class CriticService:
    """Service responsible for verifying claims found by the Researcher.
    
    It ensures that every claim has a valid source URL and supporting text, 
    and (in production) would use an LLM to verify the semantic alignment 
    between the statement and the support text.
    """
    
    def verify(self, claims: List[AtomicClaim]) -> List[Tuple[AtomicClaim, bool, str]]:
        """Verifies a list of claims.
        
        Returns a list of tuples: (claim, is_valid, reason)
        """
        results = []
        for claim in claims:
            if not claim.source_url:
                results.append((claim, False, "Missing source URL"))
                continue
                
            if not claim.support_text:
                results.append((claim, False, "Missing support text"))
                continue
                
            if len(claim.support_text) < 10:
                results.append((claim, False, "Support text too short to be credible"))
                continue

            # MVP: If it has source and support, we consider it 'verified' at this stage.
            # A more advanced critic would check if the statement is actually 
            # supported by the text using an LLM.
            results.append((claim, True, "Verified: Source and support text present"))
            
        return results
