"""
Deep Research Report Formatter for HDRP.

Generates structured research reports following the Deep Research Report Skeleton format
with full traceability, verification details, and DAG execution summaries.
"""

from typing import List, Dict, Optional, Tuple
from HDRP.services.shared.claims import AtomicClaim, CritiqueResult
from datetime import datetime, timezone
import hashlib


class DeepResearchReportFormatter:
    """Formats verification results into the Deep Research Report structure."""
    
    def __init__(self):
        pass
    
    def generate_verification_hash(self, claim_id: str, source_url: str, is_valid: bool) -> str:
        """Generate a reproducible verification hash for a claim.
        
        Args:
            claim_id: Unique claim identifier
            source_url: Source URL where claim was found
            is_valid: Whether the claim was verified
            
        Returns:
            16-character hex hash for reproducibility
        """
        content = f"{claim_id}|{source_url}|{is_valid}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def compute_confidence_level(
        self, 
        claim_confidence: float, 
        entailment_score: float, 
        is_valid: bool
    ) -> str:
        """Map numeric confidence scores to High/Medium/Low labels.
        
        Considers both the claim's extraction confidence and the critic's
        entailment score for a holistic confidence assessment.
        
        Args:
            claim_confidence: Confidence from claim extraction (0.0-1.0)
            entailment_score: Critic's entailment score (0.0-1.0)
            is_valid: Whether the claim passed verification
            
        Returns:
            "High", "Medium", or "Low"
        """
        if not is_valid:
            return "Low"
        
        # Combine both scores with equal weight
        combined = (claim_confidence + entailment_score) / 2
        
        if combined >= 0.75:
            return "High"
        elif combined >= 0.50:
            return "Medium"
        else:
            return "Low"
    
    def format_full_report(
        self,
        verification_results: List[CritiqueResult],
        graph_data: Optional[Dict] = None,
        context: Optional[Dict] = None,
        run_id: str = "unknown",
        query: str = ""
    ) -> str:
        """Generate complete Deep Research Report.
        
        Args:
            verification_results: All verification results (verified and rejected)
            graph_data: DAG structure with nodes and edges
            context: Additional context (report_title, section_headers, etc.)
            run_id: Unique run identifier
            query: Original research query/topic
            
        Returns:
            Formatted markdown report following the Deep Research Report Skeleton
        """
        if context is None:
            context = {}
        
        report_title = context.get("report_title", "Deep Research Report")
        
        # Separate verified and rejected claims
        verified_results = [r for r in verification_results if r.is_valid]
        rejected_results = [r for r in verification_results if not r.is_valid]
        
        verified_claims = [r.claim for r in verified_results]
        
        # Build report sections
        report = self._format_header(report_title, run_id, query)
        report += self._format_executive_synthesis(verified_claims, context)
        report += self._format_verified_findings(verified_results, context)
        report += self._format_evidence_traceability(verified_results, rejected_results)
        report += self._format_dag_execution_summary(graph_data, verified_claims, rejected_results)
        report += self._format_bibliography(verified_claims)
        
        return report
    
    def _format_header(self, title: str, run_id: str, query: str) -> str:
        """Format report header with metadata."""
        timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        
        header = f"# HDRP Deep Research Report\n\n"
        header += f"**Topic**: {query if query else 'Research Investigation'}\n\n"
        header += f"**Pipeline**: Hierarchical Deep Research Planner (HDRP)\n\n"
        header += f"**Run ID**: `{run_id}`\n\n"
        header += f"**Generated**: {timestamp}\n\n"
        header += "---\n\n"
        
        return header
    
    def _format_executive_synthesis(
        self, 
        verified_claims: List[AtomicClaim],
        context: Dict
    ) -> str:
        """Format Section 1: Executive Synthesis."""
        section = "## 1. Executive Synthesis (Synthesizer Output)\n\n"
        
        if not verified_claims:
            section += "*No verified claims available for synthesis.*\n\n"
            return section
        
        # Generate high-level summary
        unique_sources = len(set(c.source_url for c in verified_claims if c.source_url))
        section += (
            f"This research investigation synthesizes {len(verified_claims)} verified findings "
            f"from {unique_sources} authoritative sources. Each claim has undergone rigorous "
            "verification by the HDRP Critic to ensure factual accuracy and proper grounding "
            "in source material. The following synthesis presents key insights derived exclusively "
            "from verified evidence.\n\n"
        )
        
        # Extract key takeaways
        key_takeaways = self._extract_key_takeaways(verified_claims, context)
        
        section += "### Key Takeaways\n\n"
        for takeaway in key_takeaways:
            section += f"- {takeaway}\n"
        section += "\n"
        
        section += "*This synthesis is derived exclusively from verified claims accepted by the HDRP Critic.*\n\n"
        
        return section
    
    def _extract_key_takeaways(
        self, 
        verified_claims: List[AtomicClaim],
        context: Dict
    ) -> List[str]:
        """Extract 3-5 key takeaways from verified claims.
        
        Groups claims by node/topic and generates high-level insights.
        """
        takeaways = []
        
        # Group claims by source node
        node_groups = {}
        for claim in verified_claims:
            node_id = claim.source_node_id or "general"
            if node_id not in node_groups:
                node_groups[node_id] = []
            node_groups[node_id].append(claim)
        
        section_headers = context.get('section_headers', {})
        
        # Generate takeaways from node groups
        for node_id, claims in list(node_groups.items())[:5]:  # Max 5 takeaways
            section_name = section_headers.get(node_id, f"Research area: {node_id}")
            claim_count = len(claims)
            source_count = len(set(c.source_url for c in claims if c.source_url))
            
            takeaway = (
                f"{section_name} is supported by {claim_count} verified finding"
                f"{'s' if claim_count != 1 else ''} from {source_count} source"
                f"{'s' if source_count != 1 else ''}"
            )
            takeaways.append(takeaway)
        
        # Add quality takeaway if we have high-confidence claims
        high_conf_count = sum(1 for c in verified_claims if c.confidence >= 0.8)
        if high_conf_count > len(verified_claims) * 0.6:
            takeaways.append(
                f"The majority of findings ({high_conf_count}/{len(verified_claims)}) "
                "demonstrate high confidence with strong source verification"
            )
        
        return takeaways[:5]  # Limit to 5 key takeaways
    
    def _format_verified_findings(
        self,
        verified_results: List[CritiqueResult],
        context: Dict
    ) -> str:
        """Format Section 2: Verified Findings."""
        section = "## 2. Verified Findings (Claim Layer)\n\n"
        section += "*Format: Each finding is atomic, verified, and anchored to DAG nodes.*\n\n"
        
        if not verified_results:
            section += "*No verified findings available.*\n\n"
            return section
        
        # Group by source node for organization
        node_groups = {}
        for result in verified_results:
            node_id = result.claim.source_node_id or "general"
            if node_id not in node_groups:
                node_groups[node_id] = []
            node_groups[node_id].append(result)
        
        finding_num = 1
        for node_id in sorted(node_groups.keys()):
            results = node_groups[node_id]
            
            for result in results:
                claim = result.claim
                confidence_level = self.compute_confidence_level(
                    claim.confidence,
                    result.entailment_score,
                    result.is_valid
                )
                
                # Generate short title from statement
                short_title = self._generate_short_title(claim.statement)
                
                section += f"### Finding {finding_num} — {short_title}\n\n"
                section += f"- **Claim ID**: `{claim.claim_id}`\n"
                section += f"- **Statement**: {claim.statement}\n"
                section += f"- **Confidence**: {confidence_level}\n"
                section += f"- **Derived From Nodes**: `{claim.source_node_id or 'N/A'}`\n"
                
                # Format sources
                if claim.source_url:
                    source_display = claim.source_title if claim.source_title else claim.source_url
                    section += f"- **Sources**: [{source_display}]({claim.source_url})\n"
                else:
                    section += f"- **Sources**: N/A\n"
                
                section += "\n"
                finding_num += 1
        
        return section
    
    def _generate_short_title(self, statement: str, max_words: int = 6) -> str:
        """Generate a short title from a claim statement."""
        words = statement.split()
        if len(words) <= max_words:
            return statement.rstrip('.')
        
        # Take first max_words and add ellipsis
        short = ' '.join(words[:max_words])
        return short.rstrip('.') + "..."
    
    def _format_evidence_traceability(
        self,
        verified_results: List[CritiqueResult],
        rejected_results: List[CritiqueResult]
    ) -> str:
        """Format Section 3: Evidence & Traceability."""
        section = "## 3. Evidence & Traceability (Critic-Verified)\n\n"
        section += "*Format: Each claim is traced to its supporting evidence.*\n\n"
        
        # Verified claims evidence
        if verified_results:
            section += "### Verified Claims Evidence\n\n"
            
            for result in verified_results:
                claim = result.claim
                verification_hash = self.generate_verification_hash(
                    claim.claim_id,
                    claim.source_url or "",
                    result.is_valid
                )
                
                section += f"#### Claim `{claim.claim_id}` Evidence\n\n"
                
                # Source info
                source_title = claim.source_title or "Untitled Source"
                if claim.source_url:
                    section += f"- **Source**: [{source_title}]({claim.source_url})\n"
                else:
                    section += f"- **Source**: {source_title}\n"
                
                # Entailing text (support text)
                support_display = claim.support_text or claim.statement
                if len(support_display) > 200:
                    support_display = support_display[:197] + "..."
                section += f"- **Entailing Text**: \"{support_display}\"\n"
                
                # Critic verdict
                section += f"- **Critic Verdict**: ✔ Entails\n"
                section += f"- **Entailment Score**: {result.entailment_score:.2f}\n"
                section += f"- **Verification Hash**: `{verification_hash}`\n"
                section += "\n"
        
        # Rejected claims in separate subsection
        if rejected_results:
            section += "### Rejected Claims\n\n"
            section += "*The following claims did not pass verification:*\n\n"
            
            for result in rejected_results:
                claim = result.claim
                verification_hash = self.generate_verification_hash(
                    claim.claim_id,
                    claim.source_url or "",
                    result.is_valid
                )
                
                section += f"#### Claim `{claim.claim_id}` (Rejected)\n\n"
                section += f"- **Statement**: {claim.statement}\n"
                
                # Source info
                if claim.source_url:
                    source_title = claim.source_title or "Untitled Source"
                    section += f"- **Source**: [{source_title}]({claim.source_url})\n"
                
                # Critic verdict
                section += f"- **Critic Verdict**: ✖ Rejected\n"
                section += f"- **Rejection Reason**: {result.reason}\n"
                section += f"- **Verification Hash**: `{verification_hash}`\n"
                section += "\n"
        
        return section
    
    def _format_dag_execution_summary(
        self,
        graph_data: Optional[Dict],
        verified_claims: List[AtomicClaim],
        rejected_results: List[CritiqueResult]
    ) -> str:
        """Format Section 4: DAG Execution Summary."""
        section = "## 4. DAG Execution Summary (System Layer)\n\n"
        
        # Graph statistics
        section += "### Graph Statistics\n\n"
        
        if graph_data and 'nodes' in graph_data:
            nodes = graph_data['nodes']
            total_nodes = len(nodes)
            
            # Count leaf nodes (researcher nodes with no outgoing edges)
            edges = graph_data.get('edges', [])
            nodes_with_outgoing = set(edge['from'] for edge in edges)
            
            leaf_nodes = [n for n in nodes if n['id'] not in nodes_with_outgoing and n.get('type') == 'researcher']
            leaf_count = len(leaf_nodes)
            
            # Dynamic expansions (nodes that spawned other nodes)
            expansion_count = len(nodes_with_outgoing)
            
            section += f"- **Total Nodes**: {total_nodes}\n"
            section += f"- **Leaf Research Nodes**: {leaf_count}\n"
            section += f"- **Dynamic Expansions**: {expansion_count}\n"
        else:
            section += "- **Total Nodes**: N/A\n"
            section += "- **Leaf Research Nodes**: N/A\n"
            section += "- **Dynamic Expansions**: N/A\n"
        
        section += f"- **Rejected Claims**: {len(rejected_results)}\n"
        section += "\n"
        
        # Node hierarchy overview
        section += "### Node Hierarchy Overview\n\n"
        
        if graph_data and 'nodes' in graph_data:
            nodes = graph_data['nodes']
            
            # Root node
            root_nodes = [n for n in nodes if n.get('type') == 'root']
            if root_nodes:
                section += f"- **Root Node**: `{root_nodes[0]['id']}`\n\n"
            
            section += "**Subgraph Summaries**:\n\n"
            
            # List all nodes with their details
            for node in nodes:
                node_id = node.get('id', 'unknown')
                node_type = node.get('type', 'unknown')
                node_status = node.get('status', 'UNKNOWN')
                
                # Map type to role
                role_map = {
                    'root': 'Principal',
                    'researcher': 'Researcher',
                    'critic': 'Critic',
                    'synthesizer': 'Synthesizer'
                }
                role = role_map.get(node_type, node_type.capitalize())
                
                section += f"- **Node ID**: `{node_id}`, **Role**: {role}, **Status**: {node_status}\n"
            
            section += "\n"
        else:
            section += "*No DAG data available.*\n\n"
        
        return section
    
    def _format_bibliography(self, verified_claims: List[AtomicClaim]) -> str:
        """Format Section 5: Bibliography."""
        section = "## 5. Bibliography\n\n"
        
        # Collect unique sources with metadata
        source_map = {}
        for claim in verified_claims:
            if claim.source_url:
                if claim.source_url not in source_map:
                    source_map[claim.source_url] = {
                        'title': claim.source_title or "Untitled Source",
                        'rank': claim.source_rank,
                        'claim_count': 0
                    }
                source_map[claim.source_url]['claim_count'] += 1
        
        if not source_map:
            section += "*No sources available.*\n\n"
            return section
        
        # Sort by rank (if available), then alphabetically
        sorted_sources = sorted(
            source_map.items(),
            key=lambda x: (x[1]['rank'] if x[1]['rank'] else 999, x[0])
        )
        
        # Format bibliography entries
        for idx, (url, metadata) in enumerate(sorted_sources, 1):
            title = metadata['title']
            rank = metadata['rank']
            claim_count = metadata['claim_count']
            
            section += f"**[{idx}]** {title}\n\n"
            section += f"   {url}\n\n"
            
            if rank:
                section += f"   *Search rank: {rank}, Claims sourced: {claim_count}*\n\n"
            else:
                section += f"   *Claims sourced: {claim_count}*\n\n"
        
        return section
