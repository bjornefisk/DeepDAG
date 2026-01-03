from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

from HDRP.tools.search.base import SearchProvider, SearchError
from HDRP.services.shared.claims import AtomicClaim, ClaimExtractor
from HDRP.services.shared.logger import ResearchLogger


@dataclass
class ReActStep:
    """Single step in a ReAct-style trajectory."""

    thought: str
    action: Optional[str] = None
    observation: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReActRunResult:
    """Container for a single ReAct agent run."""

    question: str
    final_answer: str
    claims: List[AtomicClaim]
    steps: List[ReActStep]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "final_answer": self.final_answer,
            "claims": [c.model_dump() for c in self.claims],
            "steps": [s.to_dict() for s in self.steps],
        }


class ReActAgent:
    """Baseline ReAct-style agent for benchmarking.

    This is intentionally minimal and rule-based. It follows a classic
    pattern:

        THINK → SEARCH → OBSERVE → ANSWER

    The goal is not to be state of the art, but to provide a strong,
    reproducible baseline to compare HDRP against.
    """

    def __init__(
        self,
        search_provider: SearchProvider,
        max_results: int = 5,
        run_id: Optional[str] = None,
    ) -> None:
        self.search_provider = search_provider
        self.max_results = max_results
        self.extractor = ClaimExtractor()
        self.logger = ResearchLogger("react_agent", run_id=run_id)

    def run(self, question: str) -> ReActRunResult:
        """Execute a single ReAct episode for the given question."""
        steps: List[ReActStep] = []

        # Step 1: decide to search
        thought_1 = (
            "I should search for authoritative sources that directly address this question."
        )
        step_1 = ReActStep(
            thought=thought_1,
            action=f"Search[{question}]",
        )
        self.logger.log(
            "react_thought",
            {"stage": 1, "thought": thought_1, "question": question},
        )

        # Step 2: call the search tool
        provider_name = type(self.search_provider).__name__
        try:
            search_response = self.search_provider.search(
                question, max_results=self.max_results
            )
        except SearchError as e:
            step_1.observation = f"Search failed: {e}"
            steps.append(step_1)
            self.logger.log(
                "react_search_error",
                {
                    "error": str(e),
                    "question": question,
                    "provider": provider_name,
                    "max_results_requested": self.max_results,
                },
            )
            # In failure mode, return an empty result with the error surfaced.
            return ReActRunResult(
                question=question,
                final_answer="I was unable to retrieve any sources for this question.",
                claims=[],
                steps=steps,
            )

        if not search_response.results:
            step_1.observation = "Search returned no results."
            steps.append(step_1)
            self.logger.log(
                "react_search_empty",
                {
                    "question": question,
                    "provider": provider_name,
                    "max_results_requested": self.max_results,
                    "latency_ms": search_response.latency_ms,
                    "total_found": search_response.total_found,
                },
            )
            return ReActRunResult(
                question=question,
                final_answer="I could not find any relevant information to answer this question.",
                claims=[],
                steps=steps,
            )

        # Aggregate a short textual observation from the top results.
        observation_snippets = []
        for idx, result in enumerate(search_response.results, 1):
            snippet = result.snippet or ""
            observation_snippets.append(f"[{idx}] {snippet}")
        combined_observation = "\n".join(observation_snippets)
        step_1.observation = combined_observation
        steps.append(step_1)

        self.logger.log(
            "react_search_observation",
            {
                "question": question,
                "provider": provider_name,
                "max_results_requested": self.max_results,
                "latency_ms": search_response.latency_ms,
                "results_count": len(search_response.results),
                "total_found": search_response.total_found,
                "results": [
                    {
                        "index": idx + 1,
                        "title": r.title,
                        "url": r.url,
                        "snippet": r.snippet,
                    }
                    for idx, r in enumerate(search_response.results)
                ],
            },
        )

        # Step 3: simple deterministic "reasoning" over the observation.
        thought_2 = (
            "Using these snippets, I will extract concrete factual statements and cite "
            "their originating URLs."
        )
        step_2 = ReActStep(
            thought=thought_2,
            action="ExtractClaims[search_results]",
            observation="Extracted atomic claims from search snippets.",
        )
        steps.append(step_2)

        # Extract atomic claims per search result, preserving traceability metadata.
        claims: List[AtomicClaim] = []
        for idx, result in enumerate(search_response.results, 1):
            extraction = self.extractor.extract(
                result.snippet,
                source_url=result.url,
                source_node_id="react_agent",
                source_title=result.title,
                source_rank=idx,
            )
            claims.extend(extraction.claims)

        self.logger.log(
            "react_claims_extracted",
            {
                "question": question,
                "claims_count": len(claims),
            },
        )

        # Step 4: synthesize a minimal final answer referencing the extracted claims.
        if claims:
            thought_3 = (
                "I will answer the question by summarizing the verified-looking claims "
                "and referencing their sources."
            )
        else:
            thought_3 = (
                "No strong factual claims were extracted; I should acknowledge the "
                "lack of evidence."
            )

        summary_lines: List[str] = []
        summary_lines.append(f"Question: {question}")
        summary_lines.append("")

        if claims:
            summary_lines.append("Answer (ReAct Baseline):")
            for i, claim in enumerate(claims, 1):
                citation = claim.source_url or "unknown source"
                summary_lines.append(f"{i}. {claim.statement} (source: {citation})")
        else:
            summary_lines.append(
                "I was unable to extract concrete factual statements from the retrieved sources."
            )

        final_answer = "\n".join(summary_lines)

        step_3 = ReActStep(
            thought=thought_3,
            action="FinalAnswer",
            observation="Generated final answer summarizing extracted claims.",
        )
        steps.append(step_3)

        self.logger.log(
            "react_final_answer",
            {
                "question": question,
                "claims_count": len(claims),
            },
        )

        return ReActRunResult(
            question=question,
            final_answer=final_answer,
            claims=claims,
            steps=steps,
        )


