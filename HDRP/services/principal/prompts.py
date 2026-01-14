"""Prompt templates for LLM-based query decomposition.

Contains few-shot examples for research planning that help the LLM identify:
- Dependencies between subtasks
- Independent parallel work streams
- Entity relationships for graph expansion
"""

SYSTEM_PROMPT = """You are a research planning assistant. Your job is to decompose complex research queries into a structured Directed Acyclic Graph (DAG) of subtasks.

Rules:
1. Each subtask should be atomic and independently researchable
2. Identify dependencies between subtasks (what must complete before another can start)
3. Group independent tasks at the same depth level for parallel execution
4. Maximum depth is 3 levels (0, 1, 2)
5. Each subtask needs a "researcher" node, optionally followed by "critic" and "synthesizer" nodes

Output JSON format:
{
  "subtasks": [
    {
      "id": "unique_id",
      "query": "specific research question",
      "dependencies": ["id_of_dependency", ...],
      "entities": ["key entities mentioned"]
    }
  ],
  "reasoning": "brief explanation of decomposition strategy"
}"""

FEW_SHOT_EXAMPLES = [
    {
        "query": "Compare quantum vs classical computing",
        "response": """{
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
  "reasoning": "Quantum and classical computing are independent research streams that can be explored in parallel. The comparison requires both to complete first."
}"""
    },
    {
        "query": "Analyze the economic impact of renewable energy adoption",
        "response": """{
  "subtasks": [
    {
      "id": "solar_economics",
      "query": "What is the economic impact of solar energy adoption on local economies?",
      "dependencies": [],
      "entities": ["solar energy", "solar panel costs", "solar jobs"]
    },
    {
      "id": "wind_economics",
      "query": "What is the economic impact of wind energy adoption?",
      "dependencies": [],
      "entities": ["wind energy", "wind turbines", "offshore wind"]
    },
    {
      "id": "fossil_displacement",
      "query": "How does renewable energy adoption affect fossil fuel industry employment?",
      "dependencies": [],
      "entities": ["fossil fuels", "coal", "natural gas", "job displacement"]
    },
    {
      "id": "policy_analysis",
      "query": "What government policies have been most effective in promoting renewable energy adoption?",
      "dependencies": ["solar_economics", "wind_economics"],
      "entities": ["renewable energy policy", "subsidies", "tax incentives"]
    }
  ],
  "reasoning": "Solar, wind, and fossil fuel displacement can be researched independently. Policy analysis depends on understanding the economics of renewables first."
}"""
    },
    {
        "query": "What is the history of machine learning?",
        "response": """{
  "subtasks": [
    {
      "id": "ml_history",
      "query": "What is the history and evolution of machine learning from its origins to present day?",
      "dependencies": [],
      "entities": ["machine learning", "neural networks", "deep learning", "AI winter"]
    }
  ],
  "reasoning": "This is a single, focused research question that doesn't benefit from decomposition into parallel streams."
}"""
    }
]


def build_decomposition_prompt(query: str) -> list:
    """Build the messages list for the decomposition prompt.
    
    Args:
        query: The research query to decompose.
        
    Returns:
        List of message dicts for the chat completion API.
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # Add few-shot examples
    for example in FEW_SHOT_EXAMPLES:
        messages.append({"role": "user", "content": example["query"]})
        messages.append({"role": "assistant", "content": example["response"]})
    
    # Add the actual query
    messages.append({"role": "user", "content": query})
    
    return messages
