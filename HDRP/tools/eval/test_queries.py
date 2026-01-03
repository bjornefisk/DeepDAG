"""
Test Query Suite for HDRP vs ReAct Comparison

This module defines a structured set of research queries across three
complexity levels to evaluate and compare the HDRP hierarchical approach
against the flat ReAct baseline.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List


class QueryComplexity(Enum):
    """Classification of query difficulty levels."""
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


@dataclass
class TestQuery:
    """A single test query with metadata."""
    
    id: str
    question: str
    complexity: QueryComplexity
    description: str
    expected_subtopics: List[str]
    
    def __str__(self) -> str:
        return f"[{self.complexity.value.upper()}] {self.question}"


# Simple queries: Single-topic factual questions
SIMPLE_QUERIES = [
    TestQuery(
        id="simple_01",
        question="What is quantum computing?",
        complexity=QueryComplexity.SIMPLE,
        description="Single-concept definition query",
        expected_subtopics=["quantum computing", "qubits", "superposition"],
    ),
    TestQuery(
        id="simple_02",
        question="Who invented the transistor?",
        complexity=QueryComplexity.SIMPLE,
        description="Historical fact with clear answer",
        expected_subtopics=["transistor", "inventors", "Bell Labs"],
    ),
    TestQuery(
        id="simple_03",
        question="What is machine learning?",
        complexity=QueryComplexity.SIMPLE,
        description="Single-concept technical definition",
        expected_subtopics=["machine learning", "AI", "algorithms"],
    ),
]

# Medium queries: Multi-faceted research requiring 2-3 subtopics
MEDIUM_QUERIES = [
    TestQuery(
        id="medium_01",
        question="Compare quantum computing to classical computing",
        complexity=QueryComplexity.MEDIUM,
        description="Comparison requiring analysis of two concepts",
        expected_subtopics=["quantum computing", "classical computing", "differences", "advantages"],
    ),
    TestQuery(
        id="medium_02",
        question="What is the impact of AI on healthcare?",
        complexity=QueryComplexity.MEDIUM,
        description="Application domain analysis requiring multiple perspectives",
        expected_subtopics=["AI", "healthcare", "medical diagnosis", "applications"],
    ),
    TestQuery(
        id="medium_03",
        question="How does blockchain technology ensure security?",
        complexity=QueryComplexity.MEDIUM,
        description="Technical mechanism explanation with multiple components",
        expected_subtopics=["blockchain", "security", "cryptography", "consensus"],
    ),
    TestQuery(
        id="medium_04",
        question="What are the main challenges in developing autonomous vehicles?",
        complexity=QueryComplexity.MEDIUM,
        description="Multi-dimensional problem analysis",
        expected_subtopics=["autonomous vehicles", "challenges", "sensors", "safety", "regulations"],
    ),
]

# Complex queries: Multi-part research testing hierarchical decomposition
COMPLEX_QUERIES = [
    TestQuery(
        id="complex_01",
        question="Trace the evolution of cryptography from classical methods to quantum-resistant approaches",
        complexity=QueryComplexity.COMPLEX,
        description="Historical progression requiring multiple eras and technical transitions",
        expected_subtopics=[
            "classical cryptography",
            "public-key cryptography",
            "RSA",
            "quantum computing threats",
            "post-quantum cryptography",
            "lattice-based cryptography"
        ],
    ),
    TestQuery(
        id="complex_02",
        question="Compare renewable energy adoption and policies across North America, Europe, and Asia",
        complexity=QueryComplexity.COMPLEX,
        description="Multi-region comparative analysis with policy and technical dimensions",
        expected_subtopics=[
            "renewable energy",
            "North America",
            "Europe",
            "Asia",
            "policies",
            "adoption rates",
            "solar",
            "wind"
        ],
    ),
    TestQuery(
        id="complex_03",
        question="Analyze the technical and ethical implications of large language models in content generation",
        complexity=QueryComplexity.COMPLEX,
        description="Multi-dimensional analysis requiring technical, ethical, and societal perspectives",
        expected_subtopics=[
            "large language models",
            "GPT",
            "content generation",
            "technical capabilities",
            "ethical concerns",
            "bias",
            "misinformation",
            "copyright"
        ],
    ),
]


# Combined query set
ALL_QUERIES = SIMPLE_QUERIES + MEDIUM_QUERIES + COMPLEX_QUERIES


def get_queries_by_complexity(complexity: QueryComplexity) -> List[TestQuery]:
    """Filter queries by complexity level."""
    return [q for q in ALL_QUERIES if q.complexity == complexity]


def get_query_by_id(query_id: str) -> TestQuery:
    """Retrieve a specific query by ID."""
    for query in ALL_QUERIES:
        if query.id == query_id:
            return query
    raise ValueError(f"Query ID '{query_id}' not found")


def print_query_summary() -> None:
    """Print a summary of all test queries."""
    print("=" * 80)
    print("TEST QUERY SUITE SUMMARY")
    print("=" * 80)
    print(f"\nTotal Queries: {len(ALL_QUERIES)}")
    print(f"  - Simple:  {len(SIMPLE_QUERIES)}")
    print(f"  - Medium:  {len(MEDIUM_QUERIES)}")
    print(f"  - Complex: {len(COMPLEX_QUERIES)}")
    print("\n" + "-" * 80)
    
    for complexity_level in [QueryComplexity.SIMPLE, QueryComplexity.MEDIUM, QueryComplexity.COMPLEX]:
        queries = get_queries_by_complexity(complexity_level)
        print(f"\n{complexity_level.value.upper()} QUERIES:")
        for query in queries:
            print(f"  [{query.id}] {query.question}")
            print(f"           {query.description}")
    print("\n" + "=" * 80)


if __name__ == "__main__":
    # When run directly, print the query summary
    print_query_summary()

