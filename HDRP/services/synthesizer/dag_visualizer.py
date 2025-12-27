"""
DAG visualization module for generating Mermaid diagrams.

This module converts DAG structures into Mermaid flowchart syntax
for embedding in markdown documents.
"""

from typing import Dict, List, Optional, Set
from HDRP.services.shared.claims import AtomicClaim


class DAGVisualizer:
    """Generates Mermaid diagram representations of research DAGs."""
    
    # Node type to shape mapping
    NODE_SHAPES = {
        'researcher': '[]',      # Rectangle
        'critic': '{{}',         # Hexagon
        'synthesizer': '([{}])', # Stadium/pill
        'principal': '[()]',     # Rounded rectangle
        'root': '(())',          # Circle
        'default': '[]'          # Rectangle
    }
    
    # Status to style mapping
    STATUS_STYLES = {
        'SUCCEEDED': 'fill:#d4edda',
        'RUNNING': 'fill:#fff3cd',
        'FAILED': 'fill:#f8d7da',
        'PENDING': 'fill:#e7e7e7',
        'CREATED': 'fill:#f0f0f0',
        'BLOCKED': 'fill:#ffc107',
        'CANCELLED': 'fill:#6c757d'
    }
    
    def __init__(self):
        self.node_counter = 0
        self.node_id_map = {}  # Original ID -> Sanitized ID
    
    def _sanitize_id(self, node_id: str) -> str:
        """Convert node IDs to Mermaid-safe identifiers.
        
        Mermaid doesn't allow spaces, special chars in node IDs.
        """
        if node_id in self.node_id_map:
            return self.node_id_map[node_id]
        
        # Replace invalid characters
        safe_id = node_id.replace('-', '_').replace(' ', '_').replace(':', '_')
        safe_id = ''.join(c for c in safe_id if c.isalnum() or c == '_')
        
        # Ensure it doesn't start with number
        if safe_id and safe_id[0].isdigit():
            safe_id = 'n' + safe_id
        
        # Avoid reserved keywords
        if safe_id.lower() in ['end', 'graph', 'subgraph', 'style', 'class']:
            safe_id = safe_id + '_node'
        
        self.node_id_map[node_id] = safe_id
        return safe_id
    
    def _get_node_shape(self, node_type: str) -> tuple:
        """Get opening and closing brackets for node shape.
        
        Returns:
            (opening, closing) bracket pair
        """
        shape = self.NODE_SHAPES.get(node_type.lower(), self.NODE_SHAPES['default'])
        
        if shape == '[]':
            return '[', ']'
        elif shape == '{{}}':
            return '{{', '}}'
        elif shape == '([{}])':
            return '([', '])'
        elif shape == '[()]':
            return '[(', ')]'
        elif shape == '(())':
            return '((', '))'
        else:
            return '[', ']'
    
    def generate_from_graph_dict(self, graph_data: Dict) -> str:
        """Generate Mermaid diagram from graph dictionary.
        
        Args:
            graph_data: Dictionary with 'nodes' and 'edges' keys
                       nodes: List of dicts with 'id', 'type', 'status', etc.
                       edges: List of dicts with 'from' and 'to' keys
        
        Returns:
            Mermaid diagram as string
        """
        if not graph_data:
            return ""
        
        nodes = graph_data.get('nodes', [])
        edges = graph_data.get('edges', [])
        
        if not nodes:
            return ""
        
        mermaid = "```mermaid\nflowchart TD\n"
        
        # Add nodes
        for node in nodes:
            node_id = node.get('id', f'node_{self.node_counter}')
            self.node_counter += 1
            
            safe_id = self._sanitize_id(node_id)
            node_type = node.get('type', 'default')
            status = node.get('status', 'CREATED')
            
            # Get shape brackets
            open_br, close_br = self._get_node_shape(node_type)
            
            # Create display label
            label = f"{node_type.title()}"
            if status and status != 'CREATED':
                label += f"<br/>{status}"
            
            # Add relevance score if available
            relevance = node.get('relevance_score')
            if relevance is not None:
                label += f"<br/>Score: {relevance:.2f}"
            
            # Escape special characters in label
            label = label.replace('"', '&quot;')
            
            mermaid += f"    {safe_id}{open_br}\"{label}\"{close_br}\n"
        
        # Add edges
        for edge in edges:
            from_id = edge.get('from', '')
            to_id = edge.get('to', '')
            
            if from_id and to_id:
                safe_from = self._sanitize_id(from_id)
                safe_to = self._sanitize_id(to_id)
                mermaid += f"    {safe_from} --> {safe_to}\n"
        
        mermaid += "```\n"
        return mermaid
    
    def generate_from_claims(self, claims: List[AtomicClaim]) -> str:
        """Reconstruct and visualize DAG from claims' source_node_id fields.
        
        This is a fallback when full graph data isn't available.
        Creates a simplified view showing the research flow.
        
        Args:
            claims: List of claims with source_node_id populated
            
        Returns:
            Mermaid diagram as string
        """
        if not claims:
            return ""
        
        # Extract unique nodes from claims
        nodes = set()
        node_info = {}  # node_id -> {type, claim_count}
        
        for claim in claims:
            if claim.source_node_id:
                nodes.add(claim.source_node_id)
                if claim.source_node_id not in node_info:
                    node_info[claim.source_node_id] = {
                        'type': 'researcher',  # Default assumption
                        'claim_count': 0,
                        'status': 'SUCCEEDED'  # If we have claims, it succeeded
                    }
                node_info[claim.source_node_id]['claim_count'] += 1
        
        if not nodes:
            # No node IDs found, create simple diagram
            return self._generate_simple_pipeline_diagram(len(claims))
        
        # Build graph structure
        mermaid = "```mermaid\nflowchart TD\n"
        
        # Add root node
        mermaid += '    root(("Research Query"))\n'
        
        # Add researcher nodes
        sorted_nodes = sorted(nodes)
        for node_id in sorted_nodes:
            safe_id = self._sanitize_id(node_id)
            info = node_info[node_id]
            claim_count = info['claim_count']
            
            label = f"Research Node<br/>{claim_count} claims"
            mermaid += f'    {safe_id}["{label}"]\n'
            mermaid += f'    root --> {safe_id}\n'
        
        # Add verification stage
        mermaid += '    critic{{"Critic<br/>Verification"}}\n'
        for node_id in sorted_nodes:
            safe_id = self._sanitize_id(node_id)
            mermaid += f'    {safe_id} --> critic\n'
        
        # Add synthesis stage
        mermaid += '    synth(["Synthesizer<br/>Final Report"])\n'
        mermaid += '    critic --> synth\n'
        
        mermaid += "```\n"
        return mermaid
    
    def _generate_simple_pipeline_diagram(self, claim_count: int) -> str:
        """Generate a simple pipeline diagram when no node info available.
        
        Args:
            claim_count: Total number of claims
            
        Returns:
            Mermaid diagram showing basic pipeline
        """
        mermaid = "```mermaid\nflowchart LR\n"
        mermaid += '    query(("Research Query"))\n'
        mermaid += f'    research["Researcher<br/>{claim_count} claims"]\n'
        mermaid += '    critic{{"Critic<br/>Verification"}}\n'
        mermaid += '    synth(["Synthesizer<br/>Report"])\n'
        mermaid += '    query --> research\n'
        mermaid += '    research --> critic\n'
        mermaid += '    critic --> synth\n'
        mermaid += "```\n"
        return mermaid
    
    def generate_with_metadata(
        self,
        graph_data: Optional[Dict],
        claims: List[AtomicClaim],
        metadata: Dict
    ) -> str:
        """Generate comprehensive DAG visualization with metadata context.
        
        Args:
            graph_data: Optional full graph structure
            claims: List of verified claims
            metadata: Additional metadata (timing, stats, etc.)
            
        Returns:
            Mermaid diagram with explanatory text
        """
        result = "## Research Execution Graph\n\n"
        
        # Add explanatory text
        if claims:
            result += (
                "The following diagram illustrates the research execution flow, "
                f"showing how {len(claims)} verified claims were discovered and validated "
                "through the hierarchical pipeline.\n\n"
            )
        
        # Generate the diagram
        if graph_data and graph_data.get('nodes'):
            result += self.generate_from_graph_dict(graph_data)
        elif claims:
            result += self.generate_from_claims(claims)
        else:
            result += "*No execution graph data available.*\n"
        
        # Add legend
        result += "\n### Diagram Legend\n\n"
        result += "- **Circles**: Query/Goal nodes\n"
        result += "- **Rectangles**: Researcher nodes (claim extraction)\n"
        result += "- **Hexagons**: Critic nodes (verification)\n"
        result += "- **Rounded**: Synthesizer nodes (report generation)\n"
        result += "\n"
        
        return result
    
    def generate_execution_timeline(
        self,
        claims: List[AtomicClaim],
        metadata: Dict
    ) -> str:
        """Generate a timeline view of the research execution.
        
        Args:
            claims: List of verified claims with timestamps
            metadata: Execution metadata
            
        Returns:
            Timeline visualization as text
        """
        if not claims:
            return ""
        
        # Extract timestamps
        timestamped_claims = [c for c in claims if c.extracted_at]
        if not timestamped_claims:
            return ""
        
        result = "### Execution Timeline\n\n"
        result += "```\n"
        
        # Sort by timestamp
        sorted_claims = sorted(timestamped_claims, key=lambda c: c.extracted_at)
        
        start_time = sorted_claims[0].extracted_at
        result += f"Start: {start_time}\n"
        result += "│\n"
        
        # Group by source node
        node_groups = {}
        for claim in sorted_claims:
            node_id = claim.source_node_id or "Unknown"
            if node_id not in node_groups:
                node_groups[node_id] = []
            node_groups[node_id].append(claim)
        
        # Show progression
        for node_id, node_claims in node_groups.items():
            result += f"├─ {node_id}: {len(node_claims)} claims extracted\n"
        
        result += "│\n"
        end_time = sorted_claims[-1].extracted_at
        result += f"End: {end_time}\n"
        result += "```\n\n"
        
        return result

