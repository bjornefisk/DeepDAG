from typing import List, Dict, Optional
from HDRP.services.shared.claims import AtomicClaim, CritiqueResult
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from HDRP.services.synthesizer.report_formatter import DeepResearchReportFormatter

class SynthesizerService:
    """Service responsible for composing the final research report.
    
    It takes verified claims and structures them into a coherent narrative, 
    ensuring every fact is properly cited with its source URL.
    """
    
    def __init__(self):
        self.formatter = DeepResearchReportFormatter()
    
    def synthesize(self, verification_results: List[CritiqueResult], context: dict = None, graph_data: dict = None, run_id: str = None) -> str:
        """Converts a list of verification results into a Deep Research Report.
        
        Args:
            verification_results: List of all verification results (verified and rejected).
            context: Optional dictionary for customization.
                     Keys:
                     - 'report_title': (str) Title of the report.
                     - 'section_headers': (dict) Map of node_id to section title.
                     - 'query': (str) Original research query.
            graph_data: Optional DAG structure with nodes and edges.
            run_id: Optional run identifier.
        
        Returns:
            Formatted markdown report following Deep Research Report Skeleton structure.
        """
        if context is None:
            context = {}
        
        if run_id is None:
            run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        
        query = context.get("query", "")
        
        # Use new formatter to generate the report
        report = self.formatter.format_full_report(
            verification_results=verification_results,
            graph_data=graph_data,
            context=context,
            run_id=run_id,
            query=query
        )
        
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
            run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        
        artifact_dir = Path(output_dir) / run_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        
        # Extract verified claims
        verified_claims = [res.claim for res in verification_results if res.is_valid]
        
        # Add query to context for report generation
        if query and 'query' not in context:
            context['query'] = query
        
        # 1. Generate report with new Deep Research Report format
        # The new format already includes executive synthesis, evidence traceability,
        # DAG execution summary, and bibliography - no additional humanization needed
        final_report = self.synthesize(
            verification_results=verification_results,
            context=context,
            graph_data=graph_data,
            run_id=run_id
        )
        
        # 2. Generate metadata
        metadata = self._generate_metadata(
            verification_results=verification_results,
            run_id=run_id,
            query=query,
            context=context,
            graph_data=graph_data
        )
        
        # 3. Write all files
        output_files = {}
        
        # Write final report
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
        context: dict,
        graph_data: Optional[Dict] = None
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
        
        # DAG statistics
        dag_stats = {}
        if graph_data and 'nodes' in graph_data:
            nodes = graph_data['nodes']
            edges = graph_data.get('edges', [])
            
            # Count nodes by type
            total_nodes = len(nodes)
            nodes_with_outgoing = set(edge['from'] for edge in edges)
            leaf_nodes = [n for n in nodes if n['id'] not in nodes_with_outgoing and n.get('type') == 'researcher']
            
            dag_stats = {
                'total_nodes': total_nodes,
                'leaf_research_nodes': len(leaf_nodes),
                'dynamic_expansions': len(nodes_with_outgoing),
                'node_types': {}
            }
            
            # Count by type
            for node in nodes:
                node_type = node.get('type', 'unknown')
                dag_stats['node_types'][node_type] = dag_stats['node_types'].get(node_type, 0) + 1
        
        metadata = {
            'bundle_info': {
                'run_id': run_id,
                'generated_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                'query': query,
                'report_title': context.get('report_title', 'Deep Research Report')
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
            'dag_statistics': dag_stats,
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
