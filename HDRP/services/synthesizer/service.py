from typing import List, Dict, Optional
from HDRP.services.shared.claims import AtomicClaim, CritiqueResult
from datetime import datetime
import json
import os
from pathlib import Path

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
    
    def create_artifact_bundle(
        self,
        verification_results: List[CritiqueResult],
        output_dir: str,
        graph_data: Optional[Dict] = None,
        context: dict = None,
        run_id: str = None,
        query: str = ""
    ) -> Dict[str, str]:
        """Create a complete artifact bundle with report, DAG visualization, and metadata.
        
        Args:
            verification_results: List of verified claims
            output_dir: Base directory for artifact output (e.g., "HDRP/artifacts")
            graph_data: Optional DAG structure dictionary with 'nodes' and 'edges'
            context: Optional context dict (report_title, section_headers, etc.)
            run_id: Optional run identifier for organizing outputs
            query: Original research query/topic
            
        Returns:
            Dictionary mapping output types to file paths:
            {
                'report': 'path/to/report.md',
                'dag': 'path/to/dag.json',
                'metadata': 'path/to/metadata.json',
                'claims': 'path/to/claims.json'
            }
        """
        from HDRP.services.synthesizer.humanizer import ReportHumanizer
        from HDRP.services.synthesizer.dag_visualizer import DAGVisualizer
        
        if context is None:
            context = {}
        
        # Generate run-specific directory
        if run_id is None:
            run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        
        artifact_dir = Path(output_dir) / run_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        
        # Extract verified claims
        verified_claims = [res.claim for res in verification_results if res.is_valid]
        
        # 1. Generate base technical report
        base_report = self.synthesize(verification_results, context)
        
        # 2. Apply humanization
        humanizer = ReportHumanizer()
        humanized_report = humanizer.humanize_full_report(
            base_report=base_report,
            claims=verified_claims,
            topic=query,
            context=context
        )
        
        # 3. Generate DAG visualization
        visualizer = DAGVisualizer()
        dag_section = visualizer.generate_with_metadata(
            graph_data=graph_data,
            claims=verified_claims,
            metadata=context
        )
        
        # 4. Combine into final report with DAG
        final_report = humanized_report
        
        # Insert DAG visualization before conclusions
        if "## Conclusions" in final_report:
            parts = final_report.split("## Conclusions")
            final_report = parts[0] + "\n" + dag_section + "\n## Conclusions" + parts[1]
        else:
            # Add at end before bibliography
            if "## Bibliography" in final_report:
                parts = final_report.split("## Bibliography")
                final_report = parts[0] + "\n" + dag_section + "\n## Bibliography" + parts[1]
            else:
                final_report += "\n" + dag_section
        
        # 5. Generate metadata
        metadata = self._generate_metadata(
            verification_results=verification_results,
            run_id=run_id,
            query=query,
            context=context
        )
        
        # 6. Write all files
        output_files = {}
        
        # Write humanized report
        report_path = artifact_dir / "report.md"
        report_path.write_text(final_report, encoding='utf-8')
        output_files['report'] = str(report_path)
        
        # Write DAG JSON (if available)
        if graph_data:
            dag_path = artifact_dir / "dag.json"
            dag_path.write_text(
                json.dumps(graph_data, indent=2),
                encoding='utf-8'
            )
            output_files['dag'] = str(dag_path)
        
        # Write metadata JSON
        metadata_path = artifact_dir / "metadata.json"
        metadata_path.write_text(
            json.dumps(metadata, indent=2),
            encoding='utf-8'
        )
        output_files['metadata'] = str(metadata_path)
        
        # Write structured claims JSON
        claims_data = [
            {
                'claim_id': c.claim_id,
                'statement': c.statement,
                'support_text': c.support_text,
                'source_url': c.source_url,
                'source_title': c.source_title,
                'source_rank': c.source_rank,
                'source_node_id': c.source_node_id,
                'extracted_at': c.extracted_at,
                'confidence': c.confidence
            }
            for c in verified_claims
        ]
        claims_path = artifact_dir / "claims.json"
        claims_path.write_text(
            json.dumps(claims_data, indent=2),
            encoding='utf-8'
        )
        output_files['claims'] = str(claims_path)
        
        return output_files
    
    def _generate_metadata(
        self,
        verification_results: List[CritiqueResult],
        run_id: str,
        query: str,
        context: dict
    ) -> Dict:
        """Generate comprehensive metadata for the artifact bundle.
        
        Returns:
            Dictionary with execution metadata, statistics, and provenance
        """
        verified_claims = [res.claim for res in verification_results if res.is_valid]
        rejected_claims = [res for res in verification_results if not res.is_valid]
        
        # Collect timestamps
        timestamps = [c.extracted_at for c in verified_claims if c.extracted_at]
        earliest = min(timestamps) if timestamps else None
        latest = max(timestamps) if timestamps else None
        
        # Calculate statistics
        unique_sources = set(c.source_url for c in verified_claims if c.source_url)
        avg_confidence = sum(c.confidence for c in verified_claims) / len(verified_claims) if verified_claims else 0
        
        # Source distribution
        source_stats = {}
        for claim in verified_claims:
            if claim.source_url:
                if claim.source_url not in source_stats:
                    source_stats[claim.source_url] = {
                        'title': claim.source_title or 'Untitled',
                        'rank': claim.source_rank,
                        'claim_count': 0
                    }
                source_stats[claim.source_url]['claim_count'] += 1
        
        # Node distribution
        node_stats = {}
        for claim in verified_claims:
            node_id = claim.source_node_id or 'unknown'
            node_stats[node_id] = node_stats.get(node_id, 0) + 1
        
        metadata = {
            'bundle_info': {
                'run_id': run_id,
                'generated_at': datetime.utcnow().isoformat() + 'Z',
                'query': query,
                'report_title': context.get('report_title', 'Research Report')
            },
            'statistics': {
                'total_claims': len(verification_results),
                'verified_claims': len(verified_claims),
                'rejected_claims': len(rejected_claims),
                'unique_sources': len(unique_sources),
                'average_confidence': round(avg_confidence, 3),
                'research_period': {
                    'start': earliest,
                    'end': latest
                }
            },
            'sources': [
                {
                    'url': url,
                    'title': stats['title'],
                    'rank': stats['rank'],
                    'claims': stats['claim_count']
                }
                for url, stats in source_stats.items()
            ],
            'dag_nodes': {
                node_id: count
                for node_id, count in node_stats.items()
            },
            'rejection_summary': [
                {
                    'claim_id': res.claim.claim_id,
                    'reason': res.reason,
                    'statement': res.claim.statement[:100]  # Truncate for brevity
                }
                for res in rejected_claims[:10]  # Limit to first 10
            ],
            'provenance': {
                'system': 'HDRP',
                'version': '1.0.0',
                'pipeline': ['Researcher', 'Critic', 'Synthesizer'],
                'verification_enabled': True
            }
        }
        
        return metadata
