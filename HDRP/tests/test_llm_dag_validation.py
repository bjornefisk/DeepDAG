"""Integration test for LLM-based DAG decomposition and validation.

Verifies:
1. Query "Compare quantum vs classical computing" generates 2+ independent researcher nodes
2. Max depth=3 constraint is enforced
3. Generated DAG structure is valid (no cycles, proper edges)
"""

import unittest
from unittest.mock import MagicMock
import json

from HDRP.services.principal.service import PrincipalService


class TestLLMDAGValidation(unittest.TestCase):
    """Integration tests for LLM DAG decomposition validation."""

    def setUp(self):
        self.service = PrincipalService(run_id="integration-test")
        # Mock the OpenAI client
        self.mock_client = MagicMock()
        self.service._client = self.mock_client

    def _set_mock_response(self, response_dict):
        """Helper to set up mock LLM response."""
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = json.dumps(response_dict)
        self.mock_client.chat.completions.create.return_value = mock_completion

    def test_quantum_vs_classical_parallel_nodes(self):
        """Test: 'Compare quantum vs classical computing' generates 2+ independent researcher nodes."""
        # This is the exact example from the few-shot prompts
        mock_response = {
            "subtasks": [
                {
                    "id": "quantum_research",
                    "query": "What are the key capabilities and limitations of quantum computing?",
                    "dependencies": [],
                    "entities": ["quantum computing", "qubits", "quantum supremacy"]
                },
                {
                    "id": "classical_research",
                    "query": "What are the key capabilities and limitations of classical computing?",
                    "dependencies": [],
                    "entities": ["classical computing", "transistors", "Moore's law"]
                },
                {
                    "id": "comparison_synthesis",
                    "query": "How do quantum and classical computing compare in terms of performance, cost, and use cases?",
                    "dependencies": ["quantum_research", "classical_research"],
                    "entities": ["performance comparison", "use cases"]
                }
            ],
            "reasoning": "Quantum and classical computing are independent research streams that can be explored in parallel."
        }
        self._set_mock_response(mock_response)

        result = self.service.decompose_query(
            "Compare quantum vs classical computing",
            "test-run-quantum-vs-classical"
        )

        # Verification 1: At least 2+ independent researcher nodes at depth 0
        researcher_nodes = [n for n in result.graph.nodes if n.type == "researcher"]
        depth_0_researchers = [n for n in researcher_nodes if n.depth == 0]

        print(f"\n✓ Test 1: Parallel decomposition")
        print(f"  - Total researcher nodes: {len(researcher_nodes)}")
        print(f"  - Independent (depth 0) researchers: {len(depth_0_researchers)}")
        print(f"  - Independent researcher IDs: {[n.id for n in depth_0_researchers]}")

        self.assertGreaterEqual(
            len(depth_0_researchers), 2,
            f"Expected at least 2 independent researchers at depth 0, got {len(depth_0_researchers)}"
        )

        # Verify the graph structure
        self.assertEqual(len(researcher_nodes), 3, "Should have 3 researcher nodes total")
        
        # Verify edges show dependencies
        edges = result.graph.edges
        edge_map = {}
        for edge in edges:
            from_node = getattr(edge, 'from')
            to_node = edge.to
            if from_node not in edge_map:
                edge_map[from_node] = []
            edge_map[from_node].append(to_node)

        print(f"  - Edge count: {len(edges)}")
        print(f"  - Dependency structure:")
        for from_node, to_nodes in edge_map.items():
            print(f"    {from_node} -> {to_nodes}")

        # Verify the comparison node depends on both research nodes
        comparison_node_id = "researcher_comparison_synthesis"
        self.assertIn(comparison_node_id, [n.id for n in researcher_nodes])
        
    def test_max_depth_constraint(self):
        """Test: Max depth=3 is enforced."""
        # Create a deep dependency chain that would exceed max depth
        mock_response = {
            "subtasks": [
                {"id": "level0", "query": "Level 0", "dependencies": [], "entities": []},
                {"id": "level1", "query": "Level 1", "dependencies": ["level0"], "entities": []},
                {"id": "level2", "query": "Level 2", "dependencies": ["level1"], "entities": []},
                {"id": "level3", "query": "Level 3", "dependencies": ["level2"], "entities": []},
                {"id": "level4", "query": "Level 4", "dependencies": ["level3"], "entities": []},
            ]
        }
        self._set_mock_response(mock_response)

        result = self.service.decompose_query("Deep query chain", "test-run-depth")

        print(f"\n✓ Test 2: Max depth constraint")
        print(f"  - Total nodes: {len(result.graph.nodes)}")
        
        max_depth_found = max(n.depth for n in result.graph.nodes)
        print(f"  - Max depth in graph: {max_depth_found}")
        print(f"  - Max allowed depth: 2 (0-indexed, so 3 levels)")

        # All nodes should have depth < 3 (MAX_DEPTH)
        for node in result.graph.nodes:
            print(f"    {node.id}: depth={node.depth}, type={node.type}")
            self.assertLess(
                node.depth, 3,
                f"Node {node.id} has depth {node.depth} >= MAX_DEPTH (3)"
            )

        # Verify nodes beyond depth limit were dropped
        researcher_nodes = [n for n in result.graph.nodes if n.type == "researcher"]
        # Only level0, level1, level2 should be present (depths 0, 1, 2)
        # level3 and level4 should be dropped
        self.assertLessEqual(
            len(researcher_nodes), 3,
            "Deep nodes should be filtered out"
        )

    def test_dag_structure_validity(self):
        """Test: Generated DAG has valid structure (no orphans, proper connections)."""
        mock_response = {
            "subtasks": [
                {
                    "id": "foundations",
                    "query": "What are the foundations of AI?",
                    "dependencies": [],
                    "entities": ["AI", "machine learning"]
                },
                {
                    "id": "applications",
                    "query": "What are modern AI applications?",
                    "dependencies": ["foundations"],
                    "entities": ["AI applications", "NLP", "computer vision"]
                }
            ]
        }
        self._set_mock_response(mock_response)

        result = self.service.decompose_query("Research AI", "test-run-structure")

        print(f"\n✓ Test 3: DAG structure validation")
        
        # Verify graph has correct node types
        node_types = {n.type for n in result.graph.nodes}
        print(f"  - Node types present: {node_types}")
        
        self.assertIn("researcher", node_types, "Must have researcher nodes")
        self.assertIn("critic", node_types, "Must have critic node")
        self.assertIn("synthesizer", node_types, "Must have synthesizer node")

        # Verify all nodes have IDs
        node_ids = [n.id for n in result.graph.nodes]
        print(f"  - Node IDs: {node_ids}")
        self.assertEqual(len(node_ids), len(set(node_ids)), "All node IDs must be unique")

        # Verify edges connect valid nodes
        edges = result.graph.edges
        for edge in edges:
            from_node = getattr(edge, 'from')
            to_node = edge.to
            self.assertIn(from_node, node_ids, f"Edge source {from_node} must exist")
            self.assertIn(to_node, node_ids, f"Edge target {to_node} must exist")

        print(f"  - Total edges: {len(edges)}")
        print(f"  - All edges connect valid nodes ✓")

        # Verify no cycles (simple check: synthesizer should be a sink)
        synthesizer_node = next(n for n in result.graph.nodes if n.type == "synthesizer")
        outgoing_from_synth = [e for e in edges if getattr(e, 'from') == synthesizer_node.id]
        self.assertEqual(
            len(outgoing_from_synth), 0,
            "Synthesizer should have no outgoing edges (should be a sink)"
        )

        print(f"  - DAG structure is valid (no cycles from sink) ✓")

    def test_metadata_tracking(self):
        """Test: Graph metadata includes proper decomposition info."""
        mock_response = {
            "subtasks": [
                {"id": "test", "query": "Test query", "dependencies": [], "entities": []}
            ]
        }
        self._set_mock_response(mock_response)

        result = self.service.decompose_query("Test", "run-metadata-123")

        print(f"\n✓ Test 4: Metadata tracking")
        print(f"  - Graph metadata: {dict(result.graph.metadata)}")

        self.assertEqual(
            result.graph.metadata.get("decomposition_method"), "llm",
            "Should indicate LLM-based decomposition"
        )
        self.assertEqual(
            result.graph.metadata.get("run_id"), "run-metadata-123",
            "Should track run ID"
        )
        self.assertEqual(
            result.graph.metadata.get("goal"), "Test",
            "Should track original query"
        )

        print(f"  - All metadata fields present and correct ✓")


if __name__ == "__main__":
    # Run with verbose output
    unittest.main(verbosity=2)
