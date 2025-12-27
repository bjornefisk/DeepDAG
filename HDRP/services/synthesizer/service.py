from typing import List
from HDRP.services.shared.claims import AtomicClaim, CritiqueResult

class SynthesizerService:
    """Service responsible for composing the final research report.
    
    It takes verified claims and structures them into a coherent narrative, 
    ensuring every fact is properly cited with its source URL.
    """
    
    def synthesize(self, verification_results: List[CritiqueResult]) -> str:
        """Converts a list of verification results into a markdown report with citations.
        
        Only claims marked as valid (is_valid=True) are included in the report.
        Claims are grouped by their source DAG node ID if available.
        Each statement is followed by a source link and the supporting text found by the researcher.
        """
        # Enforce No Verification No Synthesis: Filter for valid claims only
        verified_claims = [res.claim for res in verification_results if res.is_valid]
        
        if not verified_claims:
            return "No verified information found."
            
        report = "# Research Report\n\n"
        
        # Group by source_node_id
        grouped_claims = {}
        for claim in verified_claims:
            node_id = claim.source_node_id or "General Findings"
            if node_id not in grouped_claims:
                grouped_claims[node_id] = []
            grouped_claims[node_id].append(claim)
            
        # Generate sections
        # If we have node IDs, we likely want to sort them or present them in some order.
        # For now, we sort by node ID to ensure deterministic output.
        sorted_nodes = sorted(grouped_claims.keys())
        
        for node_id in sorted_nodes:
            if node_id == "General Findings":
                section_title = "General Findings"
            else:
                section_title = f"Node: {node_id}"
                
            report += f"## {section_title}\n\n"
            
            for i, claim in enumerate(grouped_claims[node_id], 1):
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
