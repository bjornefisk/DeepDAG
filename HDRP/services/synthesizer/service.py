from typing import List
from HDRP.services.shared.claims import AtomicClaim

class SynthesizerService:
    """Service responsible for composing the final research report.
    
    It takes verified claims and structures them into a coherent narrative, 
    ensuring every fact is properly cited with its source URL.
    """
    
    def synthesize(self, verified_claims: List[AtomicClaim]) -> str:
        """Converts a list of verified claims into a markdown report with citations.
        
        Each statement is followed by a source link and the supporting text found by the researcher.
        """
        if not verified_claims:
            return "No verified information found."
            
        report = "# Research Report\n\n"
        report += "## Key Findings\n\n"
        
        for i, claim in enumerate(verified_claims, 1):
            # Format: 1. Statement [Source](URL)
            #         > Support: Snippet
            report += f"{i}. {claim.statement} [Source]({claim.source_url})\n"
            if claim.support_text:
                report += f"   > *Support: {claim.support_text}*\n"
            report += "\n"
            
        report += "## Bibliography\n\n"
        unique_sources = sorted(list(set(c.source_url for c in verified_claims if c.source_url)))
        for source in unique_sources:
            report += f"- {source}\n"
            
        return report
