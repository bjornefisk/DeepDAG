# Critic Agent (Verifier)

## Responsibility
Acts as the adversarial gatekeeper for information entering the system.

## Interface
- **Input:** `Claim`, `SourceURL`, `SupportingText`
- **Output:** `Verified (bool)`, `Critique (string)`

## Verification Logic
1.  **Entailment:** Does the `SupportingText` actually support the `Claim`?
2.  **Relevance:** Is the `Claim` relevant to the parent Node's objective?
3.  **Grounding:** Does the URL exist and match the content (if checkable)?