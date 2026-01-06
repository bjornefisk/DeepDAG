"""
Tests for the artifact bundle generation functionality.

Validates that the synthesizer can produce complete artifact bundles
with human-like reports, DAG visualizations, and structured metadata.
"""

import unittest
import json
import os
import shutil
from pathlib import Path
from datetime import datetime, timezone

from HDRP.services.synthesizer.service import SynthesizerService
from HDRP.services.synthesizer.humanizer import ReportHumanizer
from HDRP.services.synthesizer.dag_visualizer import DAGVisualizer
from HDRP.services.shared.claims import AtomicClaim, CritiqueResult


class TestArtifactBundle(unittest.TestCase):
    """Test artifact bundle creation and validation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.synthesizer = SynthesizerService()
        self.test_output_dir = "HDRP/artifacts/test_runs"
        
        # Create test claims
        self.test_claims = [
            AtomicClaim(
                claim_id="claim_1",
                statement="Quantum computers use qubits for computation",
                support_text="Quantum computers leverage quantum bits or qubits for computation",
                source_url="https://nature.com/quantum",
                source_title="Nature: Quantum Computing Basics",
                source_rank=1,
                source_node_id="node_quantum_intro",
                extracted_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                confidence=0.9
            ),
            AtomicClaim(
                claim_id="claim_2",
                statement="Quantum supremacy was demonstrated in 2019",
                support_text="Google claimed quantum supremacy in October 2019",
                source_url="https://science.org/supremacy",
                source_title="Science: Quantum Supremacy Achieved",
                source_rank=2,
                source_node_id="node_quantum_milestones",
                extracted_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                confidence=0.85
            ),
            AtomicClaim(
                claim_id="claim_3",
                statement="Error correction remains a major challenge",
                support_text="Quantum error correction is one of the biggest challenges",
                source_url="https://nature.com/quantum",
                source_title="Nature: Quantum Computing Basics",
                source_rank=1,
                source_node_id="node_quantum_challenges",
                extracted_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                confidence=0.88
            )
        ]
        
        # Create verification results
        self.verification_results = [
            CritiqueResult(claim=claim, is_valid=True, reason="Verified")
            for claim in self.test_claims
        ]
        
        # Create test graph data
        self.test_graph_data = {
            'id': 'test_graph',
            'nodes': [
                {'id': 'root', 'type': 'root', 'status': 'SUCCEEDED', 'relevance_score': 1.0},
                {'id': 'node_quantum_intro', 'type': 'researcher', 'status': 'SUCCEEDED', 'relevance_score': 0.9},
                {'id': 'node_quantum_milestones', 'type': 'researcher', 'status': 'SUCCEEDED', 'relevance_score': 0.85},
                {'id': 'node_quantum_challenges', 'type': 'researcher', 'status': 'SUCCEEDED', 'relevance_score': 0.88},
                {'id': 'critic', 'type': 'critic', 'status': 'SUCCEEDED', 'relevance_score': 0.95},
                {'id': 'synthesizer', 'type': 'synthesizer', 'status': 'SUCCEEDED', 'relevance_score': 1.0}
            ],
            'edges': [
                {'from': 'root', 'to': 'node_quantum_intro'},
                {'from': 'root', 'to': 'node_quantum_milestones'},
                {'from': 'root', 'to': 'node_quantum_challenges'},
                {'from': 'node_quantum_intro', 'to': 'critic'},
                {'from': 'node_quantum_milestones', 'to': 'critic'},
                {'from': 'node_quantum_challenges', 'to': 'critic'},
                {'from': 'critic', 'to': 'synthesizer'}
            ]
        }
    
    def tearDown(self):
        """Clean up test artifacts."""
        if os.path.exists(self.test_output_dir):
            shutil.rmtree(self.test_output_dir)
    
    def test_bundle_directory_creation(self):
        """Test that bundle creates proper directory structure."""
        run_id = "test_bundle_dir"
        
        output_files = self.synthesizer.create_artifact_bundle(
            verification_results=self.verification_results,
            output_dir=self.test_output_dir,
            graph_data=self.test_graph_data,
            run_id=run_id,
            query="quantum computing research"
        )
        
        # Check that directory was created
        bundle_dir = Path(self.test_output_dir) / run_id
        self.assertTrue(bundle_dir.exists())
        self.assertTrue(bundle_dir.is_dir())
    
    def test_all_files_generated(self):
        """Test that all 4 expected files are created."""
        run_id = "test_all_files"
        
        output_files = self.synthesizer.create_artifact_bundle(
            verification_results=self.verification_results,
            output_dir=self.test_output_dir,
            graph_data=self.test_graph_data,
            run_id=run_id,
            query="quantum computing"
        )
        
        # Check all expected keys present
        self.assertIn('report', output_files)
        self.assertIn('dag', output_files)
        self.assertIn('metadata', output_files)
        self.assertIn('claims', output_files)
        
        # Check all files exist
        for file_path in output_files.values():
            self.assertTrue(os.path.exists(file_path), f"File not found: {file_path}")
    
    def test_report_contains_humanized_elements(self):
        """Test that report includes executive summary and natural language."""
        run_id = "test_humanized"
        context = {
            'report_title': 'Quantum Computing Research Report',
            'section_headers': {
                'node_quantum_intro': 'Introduction to Quantum Computing',
                'node_quantum_milestones': 'Recent Milestones',
                'node_quantum_challenges': 'Current Challenges'
            }
        }
        
        output_files = self.synthesizer.create_artifact_bundle(
            verification_results=self.verification_results,
            output_dir=self.test_output_dir,
            graph_data=self.test_graph_data,
            context=context,
            run_id=run_id,
            query="quantum computing developments"
        )
        
        # Read the report
        with open(output_files['report'], 'r', encoding='utf-8') as f:
            report_content = f.read()
        
        # Check for humanized elements
        self.assertIn("Executive Summary", report_content)
        self.assertIn("Conclusions", report_content)
        self.assertIn("Research Overview", report_content)
        
        # Should NOT contain raw technical metadata format
        self.assertNotIn("- **Total Verified Claims**:", report_content)
        
        # Should have natural language
        self.assertIn("research investigation", report_content.lower())
        
        # Check for bibliography
        self.assertIn("Bibliography", report_content)
    
    def test_mermaid_diagram_embedded(self):
        """Test that Mermaid diagram is embedded in the report."""
        run_id = "test_mermaid"
        
        output_files = self.synthesizer.create_artifact_bundle(
            verification_results=self.verification_results,
            output_dir=self.test_output_dir,
            graph_data=self.test_graph_data,
            run_id=run_id,
            query="quantum computing"
        )
        
        with open(output_files['report'], 'r', encoding='utf-8') as f:
            report_content = f.read()
        
        # Check for Mermaid diagram
        self.assertIn("```mermaid", report_content)
        self.assertIn("flowchart", report_content)
        self.assertIn("Research Execution Graph", report_content)
        
        # Should contain some node references
        self.assertTrue(
            "root" in report_content or "researcher" in report_content.lower(),
            "Mermaid diagram should reference DAG nodes"
        )
    
    def test_dag_json_structure(self):
        """Test that DAG JSON file has correct structure."""
        run_id = "test_dag_json"
        
        output_files = self.synthesizer.create_artifact_bundle(
            verification_results=self.verification_results,
            output_dir=self.test_output_dir,
            graph_data=self.test_graph_data,
            run_id=run_id,
            query="quantum computing"
        )
        
        with open(output_files['dag'], 'r', encoding='utf-8') as f:
            dag_data = json.load(f)
        
        # Check structure
        self.assertIn('nodes', dag_data)
        self.assertIn('edges', dag_data)
        self.assertIsInstance(dag_data['nodes'], list)
        self.assertIsInstance(dag_data['edges'], list)
        
        # Check nodes have required fields
        for node in dag_data['nodes']:
            self.assertIn('id', node)
            self.assertIn('type', node)
            self.assertIn('status', node)
    
    def test_metadata_completeness(self):
        """Test that metadata JSON contains all required sections."""
        run_id = "test_metadata"
        
        output_files = self.synthesizer.create_artifact_bundle(
            verification_results=self.verification_results,
            output_dir=self.test_output_dir,
            graph_data=self.test_graph_data,
            run_id=run_id,
            query="quantum computing research"
        )
        
        with open(output_files['metadata'], 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # Check top-level sections
        self.assertIn('bundle_info', metadata)
        self.assertIn('statistics', metadata)
        self.assertIn('sources', metadata)
        self.assertIn('dag_nodes', metadata)
        self.assertIn('provenance', metadata)
        
        # Check bundle_info
        self.assertEqual(metadata['bundle_info']['run_id'], run_id)
        self.assertEqual(metadata['bundle_info']['query'], "quantum computing research")
        
        # Check statistics
        stats = metadata['statistics']
        self.assertEqual(stats['total_claims'], 3)
        self.assertEqual(stats['verified_claims'], 3)
        self.assertEqual(stats['unique_sources'], 2)  # Two unique URLs
        self.assertGreater(stats['average_confidence'], 0)
        
        # Check sources array
        self.assertIsInstance(metadata['sources'], list)
        self.assertGreater(len(metadata['sources']), 0)
        
        # Check provenance
        self.assertEqual(metadata['provenance']['system'], 'HDRP')
        self.assertTrue(metadata['provenance']['verification_enabled'])
    
    def test_claims_json_structure(self):
        """Test that claims JSON contains properly structured claim data."""
        run_id = "test_claims_json"
        
        output_files = self.synthesizer.create_artifact_bundle(
            verification_results=self.verification_results,
            output_dir=self.test_output_dir,
            graph_data=self.test_graph_data,
            run_id=run_id,
            query="quantum computing"
        )
        
        with open(output_files['claims'], 'r', encoding='utf-8') as f:
            claims_data = json.load(f)
        
        # Check it's a list
        self.assertIsInstance(claims_data, list)
        self.assertEqual(len(claims_data), 3)
        
        # Check each claim has required fields
        for claim in claims_data:
            self.assertIn('claim_id', claim)
            self.assertIn('statement', claim)
            self.assertIn('source_url', claim)
            self.assertIn('confidence', claim)
            self.assertIn('extracted_at', claim)
    
    def test_bundle_without_graph_data(self):
        """Test that bundle generation works without graph_data (graceful degradation)."""
        run_id = "test_no_graph"
        
        output_files = self.synthesizer.create_artifact_bundle(
            verification_results=self.verification_results,
            output_dir=self.test_output_dir,
            graph_data=None,  # No graph data provided
            run_id=run_id,
            query="quantum computing"
        )
        
        # Should still create report, metadata, claims (no dag.json)
        self.assertIn('report', output_files)
        self.assertIn('metadata', output_files)
        self.assertIn('claims', output_files)
        self.assertNotIn('dag', output_files)  # No DAG file without graph_data
        
        # Report should still have Mermaid (reconstructed from claims)
        with open(output_files['report'], 'r', encoding='utf-8') as f:
            report_content = f.read()
        
        self.assertIn("```mermaid", report_content)
    
    def test_humanizer_adds_executive_summary(self):
        """Test that humanizer correctly adds executive summary."""
        humanizer = ReportHumanizer()
        
        summary = humanizer.add_executive_summary(
            claims=self.test_claims,
            topic="quantum computing developments",
            section_titles=["Introduction", "Milestones", "Challenges"]
        )
        
        self.assertIn("Executive Summary", summary)
        self.assertIn("quantum computing developments", summary)
        self.assertIn("3 verified findings", summary)
        self.assertIn("Key Findings", summary)
    
    def test_humanizer_softens_technical_language(self):
        """Test that technical metadata is converted to natural language."""
        humanizer = ReportHumanizer()
        
        technical_text = """- **Total Verified Claims**: 10
- **Research Period**: 2025-12-27T19:30:00Z to 2025-12-27T19:30:05Z
- **Unique Sources**: 5"""
        
        natural_text = humanizer.soften_technical_language(technical_text)
        
        self.assertIn("Research Overview", natural_text)
        # Check that it extracted the numbers
        self.assertTrue("10" in natural_text and "5" in natural_text or "verified findings" in natural_text)
        
        # Should NOT contain bullet points
        self.assertNotIn("- **", natural_text)
    
    def test_dag_visualizer_from_graph_dict(self):
        """Test DAG visualizer with full graph dictionary."""
        visualizer = DAGVisualizer()
        
        mermaid = visualizer.generate_from_graph_dict(self.test_graph_data)
        
        self.assertIn("```mermaid", mermaid)
        self.assertIn("flowchart", mermaid)
        self.assertIn("root", mermaid)
        self.assertIn("-->", mermaid)
    
    def test_dag_visualizer_from_claims(self):
        """Test DAG visualizer reconstruction from claims."""
        visualizer = DAGVisualizer()
        
        mermaid = visualizer.generate_from_claims(self.test_claims)
        
        self.assertIn("```mermaid", mermaid)
        self.assertIn("flowchart", mermaid)
        self.assertIn("Research", mermaid)
        self.assertIn("Critic", mermaid)
        self.assertIn("Synthesizer", mermaid)
    
    def test_verify_citations_preserved(self):
        """Test that citations from original report are preserved in humanized version."""
        run_id = "test_citations"
        
        output_files = self.synthesizer.create_artifact_bundle(
            verification_results=self.verification_results,
            output_dir=self.test_output_dir,
            graph_data=self.test_graph_data,
            run_id=run_id,
            query="quantum computing"
        )
        
        with open(output_files['report'], 'r', encoding='utf-8') as f:
            report_content = f.read()
        
        # Check for citation format [1], [2], etc.
        import re
        citations = re.findall(r'\[\d+\]', report_content)
        self.assertGreater(len(citations), 0, "Report should contain numbered citations")
        
        # Check bibliography section exists
        self.assertIn("Bibliography", report_content)
        
        # Check that source URLs appear
        for claim in self.test_claims:
            if claim.source_url:
                self.assertIn(claim.source_url, report_content)


class TestHumanizerModule(unittest.TestCase):
    """Dedicated tests for the humanizer module."""
    
    def setUp(self):
        self.humanizer = ReportHumanizer()
        self.test_claims = [
            AtomicClaim(
                claim_id="c1",
                statement="Test claim one",
                confidence=0.9,
                source_url="http://example.com",
                source_node_id="node_1"
            ),
            AtomicClaim(
                claim_id="c2",
                statement="Test claim two",
                confidence=0.8,
                source_url="http://example.com",
                source_node_id="node_2"
            )
        ]
    
    def test_sentence_variation(self):
        """Test that sentence structure varies across claims."""
        claims_text = ["Claim one statement", "Claim two statement", "Claim three statement"]
        varied = self.humanizer.vary_sentence_structure(claims_text)
        
        # Should return same number of claims
        self.assertEqual(len(varied), len(claims_text))
        
        # At least some should be different from originals
        differences = sum(1 for i, v in enumerate(varied) if v != claims_text[i])
        self.assertGreater(differences, 0)
    
    def test_conclusions_generation(self):
        """Test conclusions section generation."""
        conclusions = self.humanizer.add_conclusions(
            claims=self.test_claims,
            section_titles=["Introduction", "Methods"]
        )
        
        self.assertIn("Conclusions", conclusions)
        self.assertIn("Research Implications", conclusions)
        # Check for either "verified sources" or "discrete claims"
        self.assertTrue("verified sources" in conclusions.lower() or "discrete claims" in conclusions.lower())


class TestDAGVisualizerModule(unittest.TestCase):
    """Dedicated tests for the DAG visualizer module."""
    
    def setUp(self):
        self.visualizer = DAGVisualizer()
    
    def test_sanitize_node_ids(self):
        """Test that node IDs are properly sanitized for Mermaid."""
        # Test various problematic IDs
        test_cases = {
            "node-with-dashes": "node_with_dashes",
            "node with spaces": "node_with_spaces",
            "123-starts-with-number": "n123_starts_with_number",
            "end": "end_node",  # Reserved keyword
        }
        
        for input_id, expected_safe_id in test_cases.items():
            safe_id = self.visualizer._sanitize_id(input_id)
            self.assertNotIn(' ', safe_id)
            self.assertNotIn('-', safe_id)
            if expected_safe_id:
                self.assertEqual(safe_id, expected_safe_id)
    
    def test_empty_graph_handling(self):
        """Test visualizer handles empty graph gracefully."""
        empty_graph = {'nodes': [], 'edges': []}
        mermaid = self.visualizer.generate_from_graph_dict(empty_graph)
        
        self.assertEqual(mermaid, "")
    
    def test_legend_generation(self):
        """Test that legend is included in visualization."""
        claims = [AtomicClaim(claim_id="c1", statement="Test", confidence=0.9)]
        
        result = self.visualizer.generate_with_metadata(
            graph_data=None,
            claims=claims,
            metadata={}
        )
        
        self.assertIn("Diagram Legend", result)
        self.assertIn("Circles", result)
        self.assertIn("Rectangles", result)


if __name__ == "__main__":
    unittest.main()

