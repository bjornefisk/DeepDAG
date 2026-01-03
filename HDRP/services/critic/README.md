# Critic Agent

Adversarial gatekeeper that verifies claims against source text.

**Input:** Claim, SourceURL, SupportingText  
**Output:** Verified (bool), Critique (string)

Validates:
1. Entailment — Does supporting text entail the claim?
2. Relevance — Does the claim serve the parent node's objective?
3. Grounding — Is the source URL valid and content-matched?