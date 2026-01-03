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
        """Verify claims with balanced precision/recall."""
        results = []
        
        STOP_WORDS = {
            "the", "is", "at", "of", "on", "and", "a", "to", "in", "for", 
            "with", "by", "from", "up", "about", "into", "over", "after",
            "research", "find", "identify", "list", "describe", "explain"
        }

        task_tokens = set(word.lower() for word in task.split() if word.lower() not in STOP_WORDS)

        for claim in claims:
            rejection_reason = None
            
            # Traceability: timestamp, source_url, support_text
            if not claim.extracted_at:
                rejection_reason = "REJECTED: Missing extraction timestamp"
                self.logger.log("traceability_missing", {"claim_id": claim.claim_id})
            elif not self._is_valid_timestamp(claim.extracted_at):
                rejection_reason = "REJECTED: Invalid timestamp format"
                self.logger.log("traceability_invalid", {"claim_id": claim.claim_id})
            
            if not rejection_reason and not claim.source_url:
                rejection_reason = "REJECTED: Missing source URL"
            elif not rejection_reason and not claim.support_text:
                rejection_reason = "REJECTED: Missing support text"

            lower_statement = claim.statement.lower()
            lower_support = claim.support_text.lower()
            
            # Context-aware qualifiers: accept if supported by source
            if not rejection_reason:
                vague_indicators = {
                    "maybe": 0.8, "might": 0.7, "possibly": 0.6,
                    "probably": 0.5, "could be": 0.6, "appears": 0.7, "seems": 0.75,
                }
                
                vague_severity = 0.0
                for indicator, severity in vague_indicators.items():
                    if indicator in lower_statement:
                        vague_severity = max(vague_severity, severity)
                        break
                
                if vague_severity > 0 and vague_severity <= 0.5:
                    supporting_qualifiers = any(
                        q in lower_support for q in ["may", "might", "could", "possible", "suggest"]
                    )
                    if not supporting_qualifiers:
                        rejection_reason = "REJECTED: Unsupported vague statement"
            
            # Adaptive word count: accept 3+ words with connectors
            if not rejection_reason:
                word_count = len(claim.statement.split())
                has_connector = any(w in lower_statement for w in 
                    ["because", "when", "if", "in", "for", "to", "is", "was", "are"])
                
                if word_count < 3 and not has_connector:
                    rejection_reason = "REJECTED: Statement too short"
            
            # Logical leap detection: flag unsupported causality
            if not rejection_reason:
                strong_inferences = [
                    "therefore", "thus", "consequently", "as a result", "which means",
                    "implies", "suggests", "indicates", "hence", "leads to"
                ]
                has_inference = any(w in lower_statement for w in strong_inferences)
                
                if has_inference:
                    support_inference = [
                        "because", "due to", "caused by", "results in", "leads to",
                        "cause", "result", "effect", "therefore", "thus", "consequently"
                    ]
                    support_has = any(w in lower_support for w in support_inference)
                    
                    if not support_has:
                        rejection_reason = "REJECTED: Unsupported causal inference"

            # Grounding check: 60% lexical overlap (allows paraphrases)
            if not rejection_reason:
                statement_tokens = self._tokenize(lower_statement)
                support_tokens = set(self._tokenize(lower_support))
                
                filtered_tokens = [w for w in statement_tokens if w not in STOP_WORDS]
                if not filtered_tokens:
                    filtered_tokens = statement_tokens

                overlap = sum(1 for w in filtered_tokens if w in support_tokens)
                
                if len(filtered_tokens) > 0 and (overlap / len(filtered_tokens)) < 0.6:
                    rejection_reason = "REJECTED: Low grounding in source"

            # Paraphrase tolerance: 70% key term overlap (skips verbatim check)
            if not rejection_reason:
                if claim.statement not in claim.support_text:
                    key_words = self._extract_key_terms(lower_statement, STOP_WORDS)
                    support_key_words = set(self._extract_key_terms(lower_support, STOP_WORDS))
                    
                    if key_words:
                        overlap = key_words.intersection(support_key_words)
                        if len(overlap) / len(key_words) < 0.7:
                            rejection_reason = "REJECTED: Key terms missing from source"

            # Relevance check: multi-level (direct match → semantic → rank-based trust)
            if not rejection_reason:
                claim_tokens = set(w for w in filtered_tokens if w not in STOP_WORDS)
                relevance_overlap = task_tokens.intersection(claim_tokens)
                
                if not relevance_overlap:
                    # Check semantic connection between support and task
                    support_key = self._extract_key_terms(lower_support, STOP_WORDS)
                    task_key = self._extract_key_terms(task.lower(), STOP_WORDS)
                    
                    if not support_key.intersection(task_key):
                        # Trust top-2 ranked results (search engines filter by relevance)
                        if claim.source_rank and claim.source_rank > 2:
                            rejection_reason = "REJECTED: Not relevant (low rank, no keyword overlap)"

            if rejection_reason:
                self.logger.log("claim_rejected", {
                    "claim_id": claim.claim_id, "reason": rejection_reason,
                    "statement": claim.statement[:50] + "..."
                })
                claim.confidence = 0.0
                results.append(CritiqueResult(claim=claim, is_valid=False, reason=rejection_reason))
            else:
                if claim.confidence < 0.9:
                    claim.confidence = min(claim.confidence + 0.1, 1.0)
                results.append(CritiqueResult(claim=claim, is_valid=True, reason="Verified"))
            
        return results
    
    def _is_valid_timestamp(self, timestamp_str: str) -> bool:
        """Validate ISO 8601 timestamp (with/without 'Z')."""
        try:
            if timestamp_str.endswith('Z'):
                datetime.fromisoformat(timestamp_str[:-1])
            else:
                datetime.fromisoformat(timestamp_str)
            return True
        except (ValueError, AttributeError):
            return False

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize: strip punctuation and split."""
        import re
        clean_text = re.sub(r'[^\w\s]', ' ', text)
        return clean_text.split()
    
    def _extract_key_terms(self, text: str, stop_words: set) -> set:
        """Extract meaningful terms (≥3 chars, non-stop words)."""
        key_terms = set()
        for token in self._tokenize(text):
            if len(token) >= 3 and token.lower() not in stop_words:
                key_terms.add(token.lower())
        return key_terms
