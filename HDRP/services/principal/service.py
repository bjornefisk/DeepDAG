"""Principal Service for LLM-based query decomposition.

Decomposes complex research queries into DAG structures with:
- Dependencies between subtasks
- Independent parallel work streams
- Entity relationships for graph expansion
"""

import json
import logging
import os
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from HDRP.api.gen.python.HDRP.api.proto import hdrp_services_pb2
from HDRP.services.principal.prompts import build_decomposition_prompt
from HDRP.services.shared.logger import ResearchLogger

logger = logging.getLogger(__name__)

# Maximum depth for the DAG (0-indexed: 0, 1, 2 = 3 levels)
MAX_DEPTH = 3


def _make_edge(from_node: str, to_node: str) -> hdrp_services_pb2.Edge:
    """Create an Edge proto, handling 'from' as a reserved Python keyword."""
    edge = hdrp_services_pb2.Edge(to=to_node)
    setattr(edge, 'from', from_node)
    return edge


@dataclass
class Subtask:
    """Represents a decomposed subtask from LLM response."""
    id: str
    query: str
    dependencies: List[str]
    entities: List[str]


class PrincipalService:
    """Service for decomposing research queries into DAGs using LLM."""
    
    def __init__(self, run_id: Optional[str] = None):
        self.logger = ResearchLogger("principal_service", run_id=run_id)
        self._client = None
    
    @property
    def client(self):
        """Lazy-load OpenAI client to avoid import errors when API key unavailable."""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI()
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI client: {e}")
                raise
        return self._client
    
    def decompose_query(
        self, 
        query: str, 
        run_id: str,
        model: str = "gpt-4o-mini"
    ) -> hdrp_services_pb2.DecompositionResponse:
        """Decompose a query into a DAG of research subtasks.
        
        Args:
            query: The research query to decompose.
            run_id: Unique identifier for this research run.
            model: LLM model to use for decomposition.
            
        Returns:
            DecompositionResponse with graph and subtask list.
        """
        self.logger.log("decompose_start", {"query": query, "run_id": run_id})
        
        try:
            subtasks = self._call_llm(query, model)
            graph = self._build_graph(subtasks, query, run_id)
            subtask_queries = [s.query for s in subtasks]
            
            self.logger.log("decompose_success", {
                "query": query,
                "subtask_count": len(subtasks),
                "node_count": len(graph.nodes),
                "edge_count": len(graph.edges)
            })
            
            return hdrp_services_pb2.DecompositionResponse(
                graph=graph,
                subtasks=subtask_queries
            )
            
        except Exception as e:
            self.logger.log("decompose_fallback", {
                "query": query,
                "error": str(e),
                "error_type": type(e).__name__
            })
            return self._fallback_linear_dag(query, run_id)
    
    def _call_llm(self, query: str, model: str) -> List[Subtask]:
        """Call LLM to decompose the query.
        
        Args:
            query: The research query.
            model: Model identifier.
            
        Returns:
            List of parsed Subtask objects.
            
        Raises:
            Exception: If LLM call fails or response is invalid.
        """
        messages = build_decomposition_prompt(query)
        
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=1024
        )
        
        content = response.choices[0].message.content
        return self._parse_llm_response(content)
    
    def _parse_llm_response(self, content: str) -> List[Subtask]:
        """Parse and validate LLM JSON response.
        
        Args:
            content: Raw JSON string from LLM.
            
        Returns:
            List of Subtask objects.
            
        Raises:
            ValueError: If response format is invalid.
        """
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON response: {e}")
        
        if "subtasks" not in data:
            raise ValueError("Missing 'subtasks' key in response")
        
        subtasks = []
        seen_ids = set()
        
        for item in data["subtasks"]:
            if not isinstance(item, dict):
                continue
                
            subtask_id = item.get("id", "")
            if not subtask_id or subtask_id in seen_ids:
                continue
            seen_ids.add(subtask_id)
            
            subtasks.append(Subtask(
                id=subtask_id,
                query=item.get("query", ""),
                dependencies=item.get("dependencies", []),
                entities=item.get("entities", [])
            ))
        
        if not subtasks:
            raise ValueError("No valid subtasks in response")
        
        return subtasks
    
    def _build_graph(
        self, 
        subtasks: List[Subtask], 
        original_query: str,
        run_id: str
    ) -> hdrp_services_pb2.Graph:
        """Build a proto Graph from decomposed subtasks.
        
        Creates researcher nodes for each subtask, then adds
        critic and synthesizer nodes at the end.
        
        Args:
            subtasks: List of decomposed subtasks.
            original_query: The original research query.
            run_id: Unique run identifier.
            
        Returns:
            Fully constructed Graph proto.
        """
        nodes = []
        edges = []
        
        # Calculate depth for each subtask based on dependencies
        depth_map = self._calculate_depths(subtasks)
        
        # Create researcher nodes for each subtask
        valid_ids = set()
        for subtask in subtasks:
            depth = depth_map.get(subtask.id, 0)
            
            # Enforce max depth constraint
            if depth >= MAX_DEPTH:
                self.logger.log("depth_exceeded", {
                    "subtask_id": subtask.id,
                    "depth": depth,
                    "max_depth": MAX_DEPTH
                })
                continue
            
            node_id = f"researcher_{subtask.id}"
            valid_ids.add(subtask.id)
            
            nodes.append(hdrp_services_pb2.Node(
                id=node_id,
                type="researcher",
                config={"query": subtask.query},
                status="CREATED",
                relevance_score=1.0,
                depth=depth
            ))
        
        # Create edges based on dependencies
        for subtask in subtasks:
            if subtask.id not in valid_ids:
                continue
                
            for dep_id in subtask.dependencies:
                if dep_id in valid_ids:
                    edges.append(_make_edge(
                        f"researcher_{dep_id}",
                        f"researcher_{subtask.id}"
                    ))
        
        # Find leaf nodes (no outgoing edges)
        has_outgoing = {getattr(e, 'from') for e in edges}
        leaves = [n.id for n in nodes if n.id not in has_outgoing]
        
        # Add critic node after all leaves
        max_researcher_depth = max((n.depth for n in nodes), default=0)
        critic_depth = min(max_researcher_depth + 1, MAX_DEPTH - 1)
        
        nodes.append(hdrp_services_pb2.Node(
            id="critic_1",
            type="critic",
            config={"task": original_query},
            status="CREATED",
            relevance_score=1.0,
            depth=critic_depth
        ))
        
        for leaf_id in leaves:
            edges.append(_make_edge(leaf_id, "critic_1"))
        
        # Add synthesizer node after critic
        synth_depth = min(critic_depth + 1, MAX_DEPTH - 1)
        nodes.append(hdrp_services_pb2.Node(
            id="synthesizer_1",
            type="synthesizer",
            config={"query": original_query},
            status="CREATED",
            relevance_score=1.0,
            depth=synth_depth
        ))
        
        edges.append(_make_edge("critic_1", "synthesizer_1"))
        
        return hdrp_services_pb2.Graph(
            id=run_id,
            nodes=nodes,
            edges=edges,
            metadata={
                "goal": original_query,
                "run_id": run_id,
                "decomposition_method": "llm"
            }
        )
    
    def _calculate_depths(self, subtasks: List[Subtask]) -> Dict[str, int]:
        """Calculate depth for each subtask based on dependency chain.
        
        Uses topological sort to assign depths.
        
        Args:
            subtasks: List of subtasks with dependencies.
            
        Returns:
            Dict mapping subtask ID to depth.
        """
        id_to_subtask = {s.id: s for s in subtasks}
        depths: Dict[str, int] = {}
        
        def get_depth(subtask_id: str) -> int:
            if subtask_id in depths:
                return depths[subtask_id]
            
            subtask = id_to_subtask.get(subtask_id)
            if not subtask or not subtask.dependencies:
                depths[subtask_id] = 0
                return 0
            
            max_dep_depth = 0
            for dep_id in subtask.dependencies:
                if dep_id in id_to_subtask:
                    max_dep_depth = max(max_dep_depth, get_depth(dep_id) + 1)
            
            depths[subtask_id] = max_dep_depth
            return max_dep_depth
        
        for subtask in subtasks:
            get_depth(subtask.id)
        
        return depths
    
    def _fallback_linear_dag(
        self, 
        query: str, 
        run_id: str
    ) -> hdrp_services_pb2.DecompositionResponse:
        """Create a simple linear DAG when LLM is unavailable.
        
        Falls back to: researcher -> critic -> synthesizer
        
        Args:
            query: The original research query.
            run_id: Unique run identifier.
            
        Returns:
            DecompositionResponse with linear DAG.
        """
        nodes = [
            hdrp_services_pb2.Node(
                id="researcher_1",
                type="researcher",
                config={"query": query},
                status="CREATED",
                relevance_score=1.0,
                depth=0
            ),
            hdrp_services_pb2.Node(
                id="critic_1",
                type="critic",
                config={"task": query},
                status="CREATED",
                relevance_score=1.0,
                depth=1
            ),
            hdrp_services_pb2.Node(
                id="synthesizer_1",
                type="synthesizer",
                config={"query": query},
                status="CREATED",
                relevance_score=1.0,
                depth=2
            )
        ]
        
        edges = [
            _make_edge("researcher_1", "critic_1"),
            _make_edge("critic_1", "synthesizer_1")
        ]
        
        graph = hdrp_services_pb2.Graph(
            id=run_id,
            nodes=nodes,
            edges=edges,
            metadata={
                "goal": query,
                "run_id": run_id,
                "decomposition_method": "fallback_linear"
            }
        )
        
        return hdrp_services_pb2.DecompositionResponse(
            graph=graph,
            subtasks=[query]
        )
