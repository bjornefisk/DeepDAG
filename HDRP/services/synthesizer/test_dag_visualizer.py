"""
Unit tests for HDRP DAGVisualizer module.

Tests ID sanitization for Mermaid, node shape mapping, graph-to-Mermaid conversion,
claims-based diagram generation, simple pipeline diagrams, metadata visualization,
and execution timeline generation.
"""

import unittest
from datetime import datetime, timezone

from HDRP.services.synthesizer.dag_visualizer import DAGVisualizer
from HDRP.services.shared.claims import AtomicClaim


class TestDAGVisualizerInit(unittest.TestCase):
    """Tests for DAGVisualizer initialization."""

    def test_init_sets_node_counter(self):
        """Verify node counter starts at 0."""
        visualizer = DAGVisualizer()
        self.assertEqual(visualizer.node_counter, 0)

    def test_init_creates_empty_node_id_map(self):
        """Verify node ID map is empty on init."""
        visualizer = DAGVisualizer()
        self.assertIsInstance(visualizer.node_id_map, dict)
        self.assertEqual(len(visualizer.node_id_map), 0)

    def test_node_shapes_defined(self):
        """Verify node shapes are defined."""
        self.assertIn('researcher', DAGVisualizer.NODE_SHAPES)
        self.assertIn('critic', DAGVisualizer.NODE_SHAPES)
        self.assertIn('synthesizer', DAGVisualizer.NODE_SHAPES)
        self.assertIn('root', DAGVisualizer.NODE_SHAPES)

    def test_status_styles_defined(self):
        """Verify status styles are defined."""
        self.assertIn('SUCCEEDED', DAGVisualizer.STATUS_STYLES)
        self.assertIn('RUNNING', DAGVisualizer.STATUS_STYLES)
        self.assertIn('FAILED', DAGVisualizer.STATUS_STYLES)
        self.assertIn('PENDING', DAGVisualizer.STATUS_STYLES)


class TestSanitizeId(unittest.TestCase):
    """Tests for _sanitize_id method."""

    def setUp(self):
        self.visualizer = DAGVisualizer()

    def test_replaces_hyphens(self):
        """Verify hyphens are replaced with underscores."""
        result = self.visualizer._sanitize_id("node-with-hyphens")
        self.assertNotIn("-", result)
        self.assertIn("_", result)

    def test_replaces_spaces(self):
        """Verify spaces are replaced with underscores."""
        result = self.visualizer._sanitize_id("node with spaces")
        self.assertNotIn(" ", result)
        self.assertIn("_", result)

    def test_replaces_colons(self):
        """Verify colons are replaced with underscores."""
        result = self.visualizer._sanitize_id("node:with:colons")
        self.assertNotIn(":", result)

    def test_removes_special_characters(self):
        """Verify special characters are removed."""
        result = self.visualizer._sanitize_id("node@#$%special")
        self.assertTrue(result.replace("_", "").isalnum())

    def test_prepends_n_to_numeric_start(self):
        """Verify 'n' is prepended when ID starts with number."""
        result = self.visualizer._sanitize_id("123node")
        self.assertTrue(result.startswith("n"))

    def test_handles_reserved_keywords(self):
        """Verify reserved keywords get suffix."""
        for keyword in ['end', 'graph', 'subgraph', 'style', 'class']:
            result = self.visualizer._sanitize_id(keyword)
            self.assertTrue(result.endswith("_node"))

    def test_caches_sanitized_ids(self):
        """Verify sanitized IDs are cached."""
        original_id = "test-node-id"
        result1 = self.visualizer._sanitize_id(original_id)
        result2 = self.visualizer._sanitize_id(original_id)
        
        self.assertEqual(result1, result2)
        self.assertIn(original_id, self.visualizer.node_id_map)

    def test_handles_empty_string(self):
        """Verify empty string is handled."""
        result = self.visualizer._sanitize_id("")
        self.assertEqual(result, "")


class TestGetNodeShape(unittest.TestCase):
    """Tests for _get_node_shape method."""

    def setUp(self):
        self.visualizer = DAGVisualizer()

    def test_researcher_returns_rectangle(self):
        """Verify researcher node gets rectangle brackets."""
        opening, closing = self.visualizer._get_node_shape("researcher")
        self.assertEqual(opening, "[")
        self.assertEqual(closing, "]")

    def test_critic_returns_hexagon(self):
        """Verify critic node gets hexagon brackets."""
        opening, closing = self.visualizer._get_node_shape("critic")
        self.assertEqual(opening, "{{")
        self.assertEqual(closing, "}}")

    def test_synthesizer_returns_stadium(self):
        """Verify synthesizer node gets stadium brackets."""
        opening, closing = self.visualizer._get_node_shape("synthesizer")
        self.assertEqual(opening, "([")
        self.assertEqual(closing, "])")

    def test_root_returns_circle(self):
        """Verify root node gets circle brackets."""
        opening, closing = self.visualizer._get_node_shape("root")
        self.assertEqual(opening, "((")
        self.assertEqual(closing, "))")

    def test_principal_returns_rounded(self):
        """Verify principal node gets rounded brackets."""
        opening, closing = self.visualizer._get_node_shape("principal")
        self.assertEqual(opening, "[(")
        self.assertEqual(closing, ")]")

    def test_unknown_type_returns_default(self):
        """Verify unknown type gets default rectangle."""
        opening, closing = self.visualizer._get_node_shape("unknown_type")
        self.assertEqual(opening, "[")
        self.assertEqual(closing, "]")

    def test_case_insensitive(self):
        """Verify node type lookup is case insensitive."""
        opening1, closing1 = self.visualizer._get_node_shape("RESEARCHER")
        opening2, closing2 = self.visualizer._get_node_shape("researcher")
        self.assertEqual(opening1, opening2)
        self.assertEqual(closing1, closing2)


class TestGenerateFromGraphDict(unittest.TestCase):
    """Tests for generate_from_graph_dict method."""

    def setUp(self):
        self.visualizer = DAGVisualizer()

    def test_empty_graph_returns_empty(self):
        """Verify empty graph returns empty string."""
        result = self.visualizer.generate_from_graph_dict({})
        self.assertEqual(result, "")

    def test_none_graph_returns_empty(self):
        """Verify None graph returns empty string."""
        result = self.visualizer.generate_from_graph_dict(None)
        self.assertEqual(result, "")

    def test_empty_nodes_returns_empty(self):
        """Verify graph with empty nodes returns empty string."""
        result = self.visualizer.generate_from_graph_dict({"nodes": [], "edges": []})
        self.assertEqual(result, "")

    def test_starts_with_mermaid_code_block(self):
        """Verify output starts with Mermaid code block."""
        graph = {
            "nodes": [{"id": "node1", "type": "researcher"}],
            "edges": []
        }
        result = self.visualizer.generate_from_graph_dict(graph)
        self.assertTrue(result.startswith("```mermaid"))

    def test_ends_with_code_block_close(self):
        """Verify output ends with code block close."""
        graph = {
            "nodes": [{"id": "node1", "type": "researcher"}],
            "edges": []
        }
        result = self.visualizer.generate_from_graph_dict(graph)
        self.assertTrue(result.strip().endswith("```"))

    def test_includes_flowchart_directive(self):
        """Verify flowchart TD directive is included."""
        graph = {
            "nodes": [{"id": "node1", "type": "researcher"}],
            "edges": []
        }
        result = self.visualizer.generate_from_graph_dict(graph)
        self.assertIn("flowchart TD", result)

    def test_includes_nodes(self):
        """Verify nodes are included in output."""
        graph = {
            "nodes": [
                {"id": "node1", "type": "researcher"},
                {"id": "node2", "type": "critic"},
            ],
            "edges": []
        }
        result = self.visualizer.generate_from_graph_dict(graph)
        self.assertIn("node1", result)
        self.assertIn("node2", result)

    def test_includes_edges(self):
        """Verify edges are included in output."""
        graph = {
            "nodes": [
                {"id": "node1", "type": "researcher"},
                {"id": "node2", "type": "critic"},
            ],
            "edges": [{"from": "node1", "to": "node2"}]
        }
        result = self.visualizer.generate_from_graph_dict(graph)
        self.assertIn("-->", result)

    def test_shows_status_in_label(self):
        """Verify status is shown in node label."""
        graph = {
            "nodes": [{"id": "node1", "type": "researcher", "status": "SUCCEEDED"}],
            "edges": []
        }
        result = self.visualizer.generate_from_graph_dict(graph)
        self.assertIn("SUCCEEDED", result)

    def test_shows_relevance_score(self):
        """Verify relevance score is shown when present."""
        graph = {
            "nodes": [{"id": "node1", "type": "researcher", "relevance_score": 0.85}],
            "edges": []
        }
        result = self.visualizer.generate_from_graph_dict(graph)
        self.assertIn("Score:", result)
        self.assertIn("0.85", result)

    def test_handles_missing_edge_ids(self):
        """Verify missing edge IDs are handled gracefully."""
        graph = {
            "nodes": [{"id": "node1", "type": "researcher"}],
            "edges": [{"from": "", "to": "node1"}]  # Empty 'from'
        }
        result = self.visualizer.generate_from_graph_dict(graph)
        # Should not contain edge with empty from
        self.assertNotIn(" --> node1", result)


class TestGenerateFromClaims(unittest.TestCase):
    """Tests for generate_from_claims method."""

    def setUp(self):
        self.visualizer = DAGVisualizer()
        self.timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _create_claim(self, source_node_id=None):
        return AtomicClaim(
            statement="Test claim",
            support_text="Test claim",
            source_url="https://example.com",
            confidence=0.8,
            source_node_id=source_node_id,
            extracted_at=self.timestamp,
        )

    def test_empty_claims_returns_empty(self):
        """Verify empty claims return empty string."""
        result = self.visualizer.generate_from_claims([])
        self.assertEqual(result, "")

    def test_claims_without_node_ids_uses_simple_diagram(self):
        """Verify claims without node IDs use simple pipeline diagram."""
        claims = [self._create_claim(source_node_id=None)]
        result = self.visualizer.generate_from_claims(claims)
        # Simple diagram uses LR direction
        self.assertIn("flowchart LR", result)

    def test_claims_with_node_ids_creates_graph(self):
        """Verify claims with node IDs create full graph."""
        claims = [
            self._create_claim(source_node_id="research_node_1"),
            self._create_claim(source_node_id="research_node_2"),
        ]
        result = self.visualizer.generate_from_claims(claims)
        # Full diagram uses TD direction
        self.assertIn("flowchart TD", result)

    def test_includes_root_node(self):
        """Verify root node is included."""
        claims = [self._create_claim(source_node_id="node1")]
        result = self.visualizer.generate_from_claims(claims)
        self.assertIn("Research Query", result)

    def test_includes_critic_node(self):
        """Verify critic node is included."""
        claims = [self._create_claim(source_node_id="node1")]
        result = self.visualizer.generate_from_claims(claims)
        self.assertIn("Critic", result)

    def test_includes_synthesizer_node(self):
        """Verify synthesizer node is included."""
        claims = [self._create_claim(source_node_id="node1")]
        result = self.visualizer.generate_from_claims(claims)
        self.assertIn("Synthesizer", result)

    def test_shows_claim_count_per_node(self):
        """Verify claim count is shown per node."""
        claims = [
            self._create_claim(source_node_id="node1"),
            self._create_claim(source_node_id="node1"),
            self._create_claim(source_node_id="node2"),
        ]
        result = self.visualizer.generate_from_claims(claims)
        self.assertIn("2 claims", result)  # node1 has 2 claims
        self.assertIn("1 claims", result)  # node2 has 1 claim


class TestGenerateSimplePipelineDiagram(unittest.TestCase):
    """Tests for _generate_simple_pipeline_diagram method."""

    def setUp(self):
        self.visualizer = DAGVisualizer()

    def test_uses_flowchart_lr(self):
        """Verify simple diagram uses LR (left-to-right) direction."""
        result = self.visualizer._generate_simple_pipeline_diagram(5)
        self.assertIn("flowchart LR", result)

    def test_includes_query_node(self):
        """Verify query node is included."""
        result = self.visualizer._generate_simple_pipeline_diagram(5)
        self.assertIn("Research Query", result)

    def test_includes_claim_count(self):
        """Verify claim count is shown."""
        result = self.visualizer._generate_simple_pipeline_diagram(10)
        self.assertIn("10 claims", result)

    def test_includes_all_pipeline_stages(self):
        """Verify all pipeline stages are included."""
        result = self.visualizer._generate_simple_pipeline_diagram(5)
        self.assertIn("Researcher", result)
        self.assertIn("Critic", result)
        self.assertIn("Synthesizer", result)

    def test_includes_edges(self):
        """Verify edges connect all stages."""
        result = self.visualizer._generate_simple_pipeline_diagram(5)
        # Should have 3 edges: query->research, research->critic, critic->synth
        self.assertEqual(result.count("-->"), 3)


class TestGenerateWithMetadata(unittest.TestCase):
    """Tests for generate_with_metadata method."""

    def setUp(self):
        self.visualizer = DAGVisualizer()
        self.timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _create_claim(self, source_node_id="node1"):
        return AtomicClaim(
            statement="Test claim",
            support_text="Test claim",
            source_url="https://example.com",
            confidence=0.8,
            source_node_id=source_node_id,
            extracted_at=self.timestamp,
        )

    def test_includes_header(self):
        """Verify header is included."""
        claims = [self._create_claim()]
        result = self.visualizer.generate_with_metadata(None, claims, {})
        self.assertIn("## Research Execution Graph", result)

    def test_includes_claim_count_in_description(self):
        """Verify claim count is in description."""
        claims = [self._create_claim() for _ in range(7)]
        result = self.visualizer.generate_with_metadata(None, claims, {})
        self.assertIn("7 verified claims", result)

    def test_includes_legend(self):
        """Verify legend section is included."""
        claims = [self._create_claim()]
        result = self.visualizer.generate_with_metadata(None, claims, {})
        self.assertIn("### Diagram Legend", result)

    def test_legend_explains_shapes(self):
        """Verify legend explains different shapes."""
        claims = [self._create_claim()]
        result = self.visualizer.generate_with_metadata(None, claims, {})
        self.assertIn("Circles", result)
        self.assertIn("Rectangles", result)
        self.assertIn("Hexagons", result)

    def test_uses_graph_data_when_available(self):
        """Verify graph data is used when provided."""
        graph_data = {
            "nodes": [{"id": "custom_node", "type": "researcher"}],
            "edges": []
        }
        result = self.visualizer.generate_with_metadata(graph_data, [], {})
        self.assertIn("custom_node", result)

    def test_uses_claims_when_no_graph_data(self):
        """Verify claims are used when no graph data."""
        claims = [self._create_claim(source_node_id="claim_node")]
        result = self.visualizer.generate_with_metadata(None, claims, {})
        self.assertIn("claim_node", result)

    def test_shows_message_when_no_data(self):
        """Verify message shown when no data available."""
        result = self.visualizer.generate_with_metadata(None, [], {})
        self.assertIn("No execution graph data available", result)


class TestGenerateExecutionTimeline(unittest.TestCase):
    """Tests for generate_execution_timeline method."""

    def setUp(self):
        self.visualizer = DAGVisualizer()

    def _create_claim_with_timestamp(self, timestamp, source_node_id="node1"):
        return AtomicClaim(
            statement="Test claim",
            support_text="Test claim",
            source_url="https://example.com",
            confidence=0.8,
            source_node_id=source_node_id,
            extracted_at=timestamp,
        )

    def test_empty_claims_returns_empty(self):
        """Verify empty claims return empty string."""
        result = self.visualizer.generate_execution_timeline([], {})
        self.assertEqual(result, "")

    def test_claims_without_timestamps_returns_empty(self):
        """Verify claims without timestamps return empty string."""
        claim = AtomicClaim(
            statement="Test",
            support_text="Test",
            source_url="https://example.com",
            confidence=0.8,
            extracted_at=None,  # No timestamp
        )
        result = self.visualizer.generate_execution_timeline([claim], {})
        self.assertEqual(result, "")

    def test_includes_timeline_header(self):
        """Verify timeline header is included."""
        timestamp = "2024-01-15T10:00:00.000Z"
        claims = [self._create_claim_with_timestamp(timestamp)]
        result = self.visualizer.generate_execution_timeline(claims, {})
        self.assertIn("### Execution Timeline", result)

    def test_shows_start_time(self):
        """Verify start time is shown."""
        timestamp = "2024-01-15T10:00:00.000Z"
        claims = [self._create_claim_with_timestamp(timestamp)]
        result = self.visualizer.generate_execution_timeline(claims, {})
        self.assertIn("Start:", result)
        self.assertIn(timestamp, result)

    def test_shows_end_time(self):
        """Verify end time is shown."""
        t1 = "2024-01-15T10:00:00.000Z"
        t2 = "2024-01-15T10:05:00.000Z"
        claims = [
            self._create_claim_with_timestamp(t1),
            self._create_claim_with_timestamp(t2),
        ]
        result = self.visualizer.generate_execution_timeline(claims, {})
        self.assertIn("End:", result)
        self.assertIn(t2, result)

    def test_groups_by_source_node(self):
        """Verify claims are grouped by source node."""
        timestamp = "2024-01-15T10:00:00.000Z"
        claims = [
            self._create_claim_with_timestamp(timestamp, source_node_id="node_a"),
            self._create_claim_with_timestamp(timestamp, source_node_id="node_a"),
            self._create_claim_with_timestamp(timestamp, source_node_id="node_b"),
        ]
        result = self.visualizer.generate_execution_timeline(claims, {})
        self.assertIn("node_a", result)
        self.assertIn("node_b", result)
        self.assertIn("2 claims", result)  # node_a has 2 claims

    def test_handles_unknown_node_id(self):
        """Verify claims without node ID use 'Unknown'."""
        timestamp = "2024-01-15T10:00:00.000Z"
        claim = AtomicClaim(
            statement="Test",
            support_text="Test",
            source_url="https://example.com",
            confidence=0.8,
            source_node_id=None,
            extracted_at=timestamp,
        )
        result = self.visualizer.generate_execution_timeline([claim], {})
        self.assertIn("Unknown", result)


if __name__ == "__main__":
    unittest.main()

