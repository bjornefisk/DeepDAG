from typing import List, Dict
from HDRP.services.shared.claims import AtomicClaim, CritiqueResult
from datetime import datetime

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

        # Enforce verification invariant: reject unverified claims
        verified_claims = [res.claim for res in verification_results if res.is_valid]
        
        if not verified_claims:
            return "No verified information found."
        
        # Collect traceability metadata for report
        timestamps = [c.extracted_at for c in verified_claims if c.extracted_at]
        earliest = min(timestamps) if timestamps else None
        latest = max(timestamps) if timestamps else None
            
        report = f"# {report_title}\n\n"
        
        # Add metadata section with traceability info
        report += "## Research Metadata\n\n"
        report += f"- **Total Verified Claims**: {len(verified_claims)}\n"
        if earliest and latest:
            report += f"- **Research Period**: {earliest} to {latest}\n"
        unique_sources_count = len(set(c.source_url for c in verified_claims if c.source_url))
        report += f"- **Unique Sources**: {unique_sources_count}\n"
        report += f"- **Generated**: {datetime.utcnow().isoformat()}Z\n\n"
        
        if introduction:
            report += f"{introduction}\n\n"
        
        # Build global citation index (source_url -> citation number)
        # Also build a source details map for richer bibliography
        citation_map = {}
        source_details = {}  # url -> {title, rank, claim_count}
        
        for claim in verified_claims:
            if claim.source_url:
                if claim.source_url not in source_details:
                    source_details[claim.source_url] = {
                        'title': claim.source_title or "Untitled Source",
                        'rank': claim.source_rank,
                        'count': 0
                    }
                source_details[claim.source_url]['count'] += 1
        
        unique_sources = sorted(list(source_details.keys()))
        for idx, source_url in enumerate(unique_sources, 1):
            citation_map[source_url] = idx
        
        # Group claims by DAG node for sectioning
        grouped_claims = {}
        for claim in verified_claims:
            node_id = claim.source_node_id or "General Findings"
            if node_id not in grouped_claims:
                grouped_claims[node_id] = []
            grouped_claims[node_id].append(claim)
            
        sorted_nodes = sorted(grouped_claims.keys())
        
        # Generate TOC for multi-section reports
        if len(sorted_nodes) > 1:
            report += "## Table of Contents\n\n"
            for node_id in sorted_nodes:
                header = section_headers.get(node_id, f"Node: {node_id}" if node_id != "General Findings" else "General Findings")
                # Generate markdown anchor (lowercase, normalize punctuation)
                anchor = header.lower().replace(" ", "-").replace(":", "")
                report += f"- [{header}](#{anchor})\n"
            report += "\n"

        for node_id in sorted_nodes:
            if node_id == "General Findings":
                section_title = "General Findings"
            else:
                section_title = section_headers.get(node_id, f"Node: {node_id}")
                
            report += f"## {section_title}\n\n"
            
            for i, claim in enumerate(grouped_claims[node_id], 1):
                # Embed inline citation number with preserved source link
                citation_num = citation_map.get(claim.source_url, "")
                report += f"{i}. {claim.statement} [{citation_num}]\n"
                
                # Add support text as an indented quote for transparency
                if claim.support_text and claim.support_text != claim.statement:
                    # Truncate very long support text
                    support_display = claim.support_text if len(claim.support_text) <= 150 else claim.support_text[:147] + "..."
                    report += f"   > *\"{support_display}\"*\n"
                report += "\n"
        
        report += "## Bibliography\n\n"
        for source in unique_sources:
            num = citation_map[source]
            details = source_details[source]
            title = details['title']
            rank = details['rank']
            claim_count = details['count']
            
            # Format: [1] Title - URL (Search rank: 1, Claims: 3)
            report += f"[{num}] **{title}**\n"
            report += f"    {source}\n"
            if rank:
                report += f"    *Search rank: {rank}, Claims sourced: {claim_count}*\n"
            report += "\n"
            
        return report
