from typing import List, Tuple
from HDRP.services.shared.claims import AtomicClaim

class CriticService:
    """Service responsible for verifying claims found by the Researcher.
    
    It ensures that every claim has a valid source URL and supporting text, 
    and (in production) would use an LLM to verify the semantic alignment 
    between the statement and the support text.
    """
    
    def verify(self, claims: List[AtomicClaim], task: str) -> List[Tuple[AtomicClaim, bool, str]]:
        """Verifies a list of claims.
        
        Args:
            claims: List of claims to verify.
            task: The original task/query that generated these claims.

        Returns:
            list of tuples: (claim, is_valid, reason)
        """
        results = []
        
        # Simple stop words list for MVP relevance checking
        STOP_WORDS = {
            "the", "is", "at", "of", "on", "and", "a", "to", "in", "for", 
            "with", "by", "from", "up", "about", "into", "over", "after",
            "research", "find", "identify", "list", "describe", "explain" # task-specific stops
        }

        task_tokens = set(word.lower() for word in task.split() if word.lower() not in STOP_WORDS)

        for claim in claims:
            # 1. Basic Presence Checks
            if not claim.source_url:
                results.append((claim, False, "REJECTED: Missing source URL"))
                continue
            if not claim.support_text:
                results.append((claim, False, "REJECTED: Missing support text"))
                continue

            # 2. Vague Statement Detection
            # Checks for weak modal verbs, ambiguous pronouns, or lack of concreteness.
            vague_indicators = ["maybe", "might", "possibly", "probably", "could be", "seems to", "appears to"]
            lower_statement = claim.statement.lower()
            
            if any(word in lower_statement for word in vague_indicators):
                results.append((claim, False, "REJECTED: Statement is too vague/speculative"))
                continue

            if len(claim.statement.split()) < 5:
                results.append((claim, False, "REJECTED: Statement too short to be substantive"))
                continue

            # 3. Inferred/Logical Leap Detection
            # Detects if the agent is trying to 'reason' instead of 'extracting'.
            inference_indicators = [
                "therefore", "thus", "consequently", "as a result", "which means", "implying", 
                "implies", "suggests", "indicates", "because", "due to", "hence", "leads to"
            ]
            if any(word in lower_statement for word in inference_indicators):
                # If these words are in the statement but NOT in the support text, it's a hallucinated inference.
                lower_support = claim.support_text.lower()
                if not any(word in lower_support for word in inference_indicators):
                    results.append((claim, False, "REJECTED: Detected inferred logical leap not present in source"))
                    continue

            # 4. Grounding Check
            # Ensure the core claim isn't a complete hallucination relative to the snippet.
            # In an MVP, we check for high keyword overlap.
            statement_words = set(lower_statement.split())
            support_words = set(claim.support_text.lower().split())
            overlap = statement_words.intersection(support_words)
            
            if len(overlap) / len(statement_words) < 0.4:
                results.append((claim, False, "REJECTED: Low grounding - statement deviates significantly from support text"))
                continue

            # 5. Verbatim Check
            # Final strict check: the statement MUST exist verbatim in the support text.
            if claim.statement not in claim.support_text:
                results.append((claim, False, "REJECTED: Claim statement not found verbatim in source text"))
                continue

            # 6. Relevance Check
            # Ensure the claim is actually relevant to the requested task.
            # We require at least one significant token overlap between task and claim.
            claim_tokens = set(word for word in statement_words if word not in STOP_WORDS)
            relevance_overlap = task_tokens.intersection(claim_tokens)
            
            if not relevance_overlap:
                results.append((claim, False, f"REJECTED: Claim not relevant to task '{task}' (no keyword overlap)"))
                continue

            results.append((claim, True, "Verified: Grounded and concrete"))
            
        return results
