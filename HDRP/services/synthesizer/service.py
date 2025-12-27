from typing import List
from HDRP.services.shared.claims import AtomicClaim, CritiqueResult

class SynthesizerService:
    """Service responsible for composing the final research report.
    
    It takes verified claims and structures them into a coherent narrative, 
    ensuring every fact is properly cited with its source URL.
    """
    
    def synthesize(self, verification_results: List[CritiqueResult], context: dict = None) -> str:
        """Converts a list of verification results into a markdown report with citations.
        
        Args:
            verification_results: List of verified claims.
            context: Optional dictionary for customization.
                     Keys:
                     - 'report_title': (str) Title of the report.
                     - 'section_headers': (dict) Map of node_id to section title.
                     - 'introduction': (str) Optional intro text.
        
        Only claims marked as valid (is_valid=True) are included in the report.
        Claims are grouped by their source DAG node ID if available.
        """
        if context is None:
            context = {}

        report_title = context.get("report_title", "Research Report")
        section_headers = context.get("section_headers", {})
        introduction = context.get("introduction", "")

        # Enforce No Verification No Synthesis: Filter for valid claims only
        verified_claims = [res.claim for res in verification_results if res.is_valid]
        
        if not verified_claims:
            return "No verified information found."
            
        report = f"# {report_title}\n\n"
        
        if introduction:
            report += f"{introduction}\n\n"
        
        # Group by source_node_id
        grouped_claims = {}
        for claim in verified_claims:
            node_id = claim.source_node_id or "General Findings"
            if node_id not in grouped_claims:
                grouped_claims[node_id] = []
            grouped_claims[node_id].append(claim)
            
        # Generate sections
        sorted_nodes = sorted(grouped_claims.keys())
        
        # Generate Table of Contents if multiple sections
        if len(sorted_nodes) > 1:
            report += "## Table of Contents\n\n"
            for node_id in sorted_nodes:
                header = section_headers.get(node_id, f"Node: {node_id}" if node_id != "General Findings" else "General Findings")
                # Simple anchor link generation (lowercase, replace spaces with -)
                anchor = header.lower().replace(" ", "-").replace(":", "")
                report += f"- [{header}](#{anchor})\n"
            report += "\n"

        for node_id in sorted_nodes:
            # Determine section title
            if node_id == "General Findings":
                section_title = "General Findings"
            else:
                section_title = section_headers.get(node_id, f"Node: {node_id}")
                
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
