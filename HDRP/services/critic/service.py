from typing import List, Optional
from HDRP.services.shared.claims import AtomicClaim, CritiqueResult
from HDRP.services.shared.logger import ResearchLogger
from datetime import datetime

class CriticService:
    """Service responsible for verifying claims found by the Researcher.
    
    It ensures that every claim has a valid source URL and supporting text, 
    and (in production) would use an LLM to verify the semantic alignment 
    between the statement and the support text.
    """
    def __init__(self, run_id: Optional[str] = None):
        self.logger = ResearchLogger("critic", run_id=run_id)
    
    def verify(self, claims: List[AtomicClaim], task: str) -> List[CritiqueResult]:
        """Verifies a list of claims.
        
        Args:
            claims: List of claims to verify.
            task: The original task/query that generated these claims.

        Returns:
            list of CritiqueResult objects.
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
            rejection_reason = None
            
            # 0. Traceability Checks - Ensure MVP standard compliance
            if not claim.extracted_at:
                rejection_reason = "REJECTED: Missing extraction timestamp (traceability failure)"
                self.logger.log("traceability_missing", {
                    "claim_id": claim.claim_id,
                    "missing_field": "extracted_at"
                })
            elif not self._is_valid_timestamp(claim.extracted_at):
                rejection_reason = "REJECTED: Invalid extraction timestamp format"
                self.logger.log("traceability_invalid", {
                    "claim_id": claim.claim_id,
                    "extracted_at": claim.extracted_at
                })
            
            # 1. Basic Presence Checks
            if not rejection_reason and not claim.source_url:
                rejection_reason = "REJECTED: Missing source URL"
            elif not rejection_reason and not claim.support_text:
                rejection_reason = "REJECTED: Missing support text"

            # 2. Vague Statement Detection
            if not rejection_reason:
                vague_indicators = ["maybe", "might", "possibly", "probably", "could be", "seems to", "appears to"]
                lower_statement = claim.statement.lower()
                
                if any(word in lower_statement for word in vague_indicators):
                    rejection_reason = "REJECTED: Statement is too vague/speculative"
                elif len(claim.statement.split()) < 5:
                    rejection_reason = "REJECTED: Statement too short to be substantive"

            # 3. Inferred/Logical Leap Detection
            if not rejection_reason:
                inference_indicators = [
                    "therefore", "thus", "consequently", "as a result", "which means", "implying", 
                    "implies", "suggests", "indicates", "because", "due to", "hence", "leads to"
                ]
                if any(word in lower_statement for word in inference_indicators):
                    lower_support = claim.support_text.lower()
                    if not any(word in lower_support for word in inference_indicators):
                        rejection_reason = "REJECTED: Detected inferred logical leap not present in source"

            # 4. Grounding Check
            if not rejection_reason:
                statement_tokens = self._tokenize(lower_statement)
                support_tokens = set(self._tokenize(claim.support_text.lower()))
                
                filtered_statement_tokens = [w for w in statement_tokens if w not in STOP_WORDS]
                if not filtered_statement_tokens:
                     filtered_statement_tokens = statement_tokens

                overlap_count = sum(1 for w in filtered_statement_tokens if w in support_tokens)
                
                if len(filtered_statement_tokens) > 0 and (overlap_count / len(filtered_statement_tokens)) < 0.7:
                    rejection_reason = "REJECTED: Low grounding - statement deviates significantly from support text"

            # 5. Verbatim Check
            if not rejection_reason:
                if claim.statement not in claim.support_text:
                    rejection_reason = "REJECTED: Claim statement not found verbatim in source text"

            # 6. Relevance Check
            if not rejection_reason:
                claim_tokens = set(word for word in filtered_statement_tokens if word not in STOP_WORDS)
                relevance_overlap = task_tokens.intersection(claim_tokens)
                
                if not relevance_overlap:
                    rejection_reason = f"REJECTED: Claim not relevant to task '{task}' (no keyword overlap)"

            if rejection_reason:
                self.logger.log("claim_rejected", {
                    "claim_id": claim.claim_id,
                    "reason": rejection_reason,
                    "statement": claim.statement[:50] + "..." if len(claim.statement) > 50 else claim.statement,
                    "source_url": claim.source_url,
                    "source_title": claim.source_title
                })
                # For rejected claims, lower confidence to 0.0
                claim.confidence = 0.0
                results.append(CritiqueResult(claim=claim, is_valid=False, reason=rejection_reason))
            else:
                # For verified claims, maintain or slightly increase confidence
                # This shows the critic's approval adds value
                if claim.confidence < 0.9:
                    claim.confidence = min(claim.confidence + 0.1, 1.0)
                results.append(CritiqueResult(claim=claim, is_valid=True, reason="Verified: Grounded and concrete"))
            
        return results
    
    def _is_valid_timestamp(self, timestamp_str: str) -> bool:
        """Validates that a timestamp string is properly formatted ISO 8601."""
        try:
            # Accept both with and without 'Z' suffix
            if timestamp_str.endswith('Z'):
                datetime.fromisoformat(timestamp_str[:-1])
            else:
                datetime.fromisoformat(timestamp_str)
            return True
        except (ValueError, AttributeError):
            return False

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenizer that strips punctuation."""
        import re
        # Replace non-alphanumeric characters with space and split
        clean_text = re.sub(r'[^\w\s]', ' ', text)
        return clean_text.split()
