"""Tests for LLM-based query decomposition in PrincipalService."""

import unittest
from unittest.mock import MagicMock
import json

from HDRP.services.principal.service import PrincipalService, Subtask, MAX_DEPTH


class TestPrincipalServiceDecomposition(unittest.TestCase):
    """Tests for PrincipalService query decomposition."""

    def setUp(self):
        self.service = PrincipalService(run_id="test-run")
        # Pre-set mock client to avoid lazy-load triggering OpenAI initialization
        self.mock_client = MagicMock()
        self.service._client = self.mock_client

    def _set_mock_response(self, response_dict):
        """Helper to set up mock LLM response."""
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = json.dumps(response_dict)
        self.mock_client.chat.completions.create.return_value = mock_completion

    def test_parallel_decomposition_quantum_vs_classical(self):
        """Compare quantum vs classical computing should generate 2+ independent researcher nodes."""
        mock_response = {
            "subtasks": [
                {
                    "id": "quantum_research",
                    "query": "What are the key capabilities of quantum computing?",
                    "dependencies": [],
                    "entities": ["quantum computing"]
                },
                {
                    "id": "classical_research", 
                    "query": "What are the key capabilities of classical computing?",
                    "dependencies": [],
                    "entities": ["classical computing"]
                },
                {
                    "id": "comparison",
                    "query": "Compare quantum and classical computing",
                    "dependencies": ["quantum_research", "classical_research"],
                    "entities": ["comparison"]
                }
            ],
            "reasoning": "Parallel research streams"
        }
        self._set_mock_response(mock_response)

        result = self.service.decompose_query(
            "Compare quantum vs classical computing",
            "test-run-123"
        )

        # Verify we have at least 2 independent researcher nodes (no incoming edges at depth 0)
        researcher_nodes = [n for n in result.graph.nodes if n.type == "researcher"]
        depth_0_researchers = [n for n in researcher_nodes if n.depth == 0]
        
        self.assertGreaterEqual(
            len(depth_0_researchers), 2,
            f"Expected at least 2 independent researchers, got {len(depth_0_researchers)}"
        )
        
        # Verify the graph has nodes and edges
        self.assertGreater(len(result.graph.nodes), 0)
        self.assertGreater(len(result.graph.edges), 0)
        
        # Verify critic and synthesizer are present
        node_types = {n.type for n in result.graph.nodes}
        self.assertIn("critic", node_types)
        self.assertIn("synthesizer", node_types)

    def test_max_depth_constraint_enforced(self):
        """Verify max depth=3 is enforced."""
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

        result = self.service.decompose_query("Deep query", "test-run")

        # All nodes should have depth < MAX_DEPTH
        for node in result.graph.nodes:
            self.assertLess(
                node.depth, MAX_DEPTH,
                f"Node {node.id} has depth {node.depth} >= MAX_DEPTH {MAX_DEPTH}"
            )

    def test_fallback_to_linear_dag_on_llm_failure(self):
        """Verify fallback to linear DAG when LLM is unavailable."""
        self.mock_client.chat.completions.create.side_effect = Exception("API Error")

        result = self.service.decompose_query("Test query", "test-run")

        # Should fall back to linear DAG
        self.assertEqual(result.graph.metadata.get("decomposition_method"), "fallback_linear")
        
        # Linear DAG has exactly 3 nodes
        self.assertEqual(len(result.graph.nodes), 3)
        
        # Verify node types
        node_types = [n.type for n in result.graph.nodes]
        self.assertEqual(sorted(node_types), ["critic", "researcher", "synthesizer"])
        
        # Verify linear edges
        self.assertEqual(len(result.graph.edges), 2)

    def test_parse_llm_response_single_subtask(self):
        """Simple query returns single subtask."""
        mock_response = {
            "subtasks": [
                {
                    "id": "single_task",
                    "query": "What is the history of machine learning?",
                    "dependencies": [],
                    "entities": ["machine learning"]
                }
            ]
        }
        self._set_mock_response(mock_response)

        result = self.service.decompose_query(
            "What is the history of machine learning?",
            "test-run"
        )

        # Single researcher + critic + synthesizer = 3 nodes
        self.assertEqual(len(result.graph.nodes), 3)

    def test_graph_has_correct_metadata(self):
        """Verify graph metadata includes decomposition method."""
        mock_response = {
            "subtasks": [
                {"id": "test", "query": "Test", "dependencies": [], "entities": []}
            ]
        }
        self._set_mock_response(mock_response)

        result = self.service.decompose_query("Test", "run-123")

        self.assertEqual(result.graph.metadata.get("decomposition_method"), "llm")
        self.assertEqual(result.graph.metadata.get("run_id"), "run-123")
        self.assertEqual(result.graph.metadata.get("goal"), "Test")


class TestSubtaskParsing(unittest.TestCase):
    """Tests for LLM response parsing."""

    def setUp(self):
        self.service = PrincipalService()

    def test_parse_valid_response(self):
        """Parse valid JSON response."""
        content = json.dumps({
            "subtasks": [
                {"id": "a", "query": "Query A", "dependencies": [], "entities": ["X"]},
                {"id": "b", "query": "Query B", "dependencies": ["a"], "entities": []}
            ]
        })

        subtasks = self.service._parse_llm_response(content)

        self.assertEqual(len(subtasks), 2)
        self.assertEqual(subtasks[0].id, "a")
        self.assertEqual(subtasks[1].dependencies, ["a"])

    def test_parse_invalid_json_raises(self):
        """Invalid JSON raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            self.service._parse_llm_response("not json")
        
        self.assertIn("Invalid JSON", str(ctx.exception))

    def test_parse_missing_subtasks_key_raises(self):
        """Missing subtasks key raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            self.service._parse_llm_response('{"tasks": []}')
        
        self.assertIn("Missing 'subtasks'", str(ctx.exception))

    def test_parse_empty_subtasks_raises(self):
        """Empty subtasks list raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            self.service._parse_llm_response('{"subtasks": []}')
        
        self.assertIn("No valid subtasks", str(ctx.exception))

    def test_parse_deduplicates_ids(self):
        """Duplicate IDs are filtered out."""
        content = json.dumps({
            "subtasks": [
                {"id": "dup", "query": "First", "dependencies": [], "entities": []},
                {"id": "dup", "query": "Second", "dependencies": [], "entities": []}
            ]
        })

        subtasks = self.service._parse_llm_response(content)

        self.assertEqual(len(subtasks), 1)
        self.assertEqual(subtasks[0].query, "First")


class TestDepthCalculation(unittest.TestCase):
    """Tests for dependency-based depth calculation."""

    def setUp(self):
        self.service = PrincipalService()

    def test_independent_tasks_depth_zero(self):
        """Tasks with no dependencies have depth 0."""
        subtasks = [
            Subtask("a", "A", [], []),
            Subtask("b", "B", [], [])
        ]

        depths = self.service._calculate_depths(subtasks)

        self.assertEqual(depths["a"], 0)
        self.assertEqual(depths["b"], 0)

    def test_dependent_task_depth_increments(self):
        """Task depending on another has depth = parent + 1."""
        subtasks = [
            Subtask("a", "A", [], []),
            Subtask("b", "B", ["a"], [])
        ]

        depths = self.service._calculate_depths(subtasks)

        self.assertEqual(depths["a"], 0)
        self.assertEqual(depths["b"], 1)

    def test_diamond_dependency_max_depth(self):
        """
        Diamond pattern: A -> B, A -> C, B+C -> D
        D should have depth 2 (max of B and C, both at 1, plus 1).
        """
        subtasks = [
            Subtask("a", "A", [], []),
            Subtask("b", "B", ["a"], []),
            Subtask("c", "C", ["a"], []),
            Subtask("d", "D", ["b", "c"], [])
        ]

        depths = self.service._calculate_depths(subtasks)

        self.assertEqual(depths["a"], 0)
        self.assertEqual(depths["b"], 1)
        self.assertEqual(depths["c"], 1)
        self.assertEqual(depths["d"], 2)


if __name__ == "__main__":
    unittest.main()
