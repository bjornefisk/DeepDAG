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
        """Verify claims with balanced precision/recall using query decomposition logic.
        
        Implements a two-pass verification:
        1. Direct Relevance: Validates claims directly against the task.
        2. Bridging (Subtopic) Relevance: Accepts claims that match entities discovered 
           in the high-confidence claims from pass 1. This solves the "partial relevance"
           problem for complex queries (e.g. "RSA" details are relevant to "Cryptography"
           if "RSA" was established as a subtopic).
        """
        # #region agent log
        import json;open('/mnt/d/Desktop/deepdag/.cursor/debug.log','a').write(json.dumps({"location":"service.py:16","message":"verify() entry","data":{"task":task,"num_claims":len(claims)},"timestamp":__import__('datetime').datetime.now().timestamp()*1000,"sessionId":"debug-session","hypothesisId":"H1"})+'\n')
        # #endregion
        results = []
        
        STOP_WORDS = {
            "the", "is", "at", "of", "on", "and", "a", "to", "in", "for", 
            "with", "by", "from", "up", "about", "into", "over", "after",
            "research", "find", "identify", "list", "describe", "explain"
        }

        task_tokens = set(word.lower() for word in task.split() if word.lower() not in STOP_WORDS)
        
        # Intermediate storage for two-pass logic
        # format: {'claim': claim, 'reason': str|None, 'score': float, 'entities': List[str]}
        candidates = []

        # PASS 1: Structural & Direct Semantic Checks
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
            
            # Context-aware qualifiers: only reject if explicit contradiction exists
            if not rejection_reason:
                # Only penalize if source explicitly contradicts the qualifier
                definite_contradictions = {
                    "contradicts": 0.9, "refutes": 0.9, "disproves": 0.9,
                    "false": 0.95, "incorrect": 0.85, "wrong": 0.85,
                }
                
                contradiction_severity = 0.0
                for indicator, severity in definite_contradictions.items():
                    if indicator in lower_support:
                        contradiction_severity = max(contradiction_severity, severity)
                        break
                
                if contradiction_severity > 0.8:
                    rejection_reason = "REJECTED: Source contradicts statement"
            
            # Adaptive word count: accept 4+ words, or fewer with strong semantics
            if not rejection_reason:
                word_count = len(claim.statement.split())
                # Check for semantic richness even in short claims
                has_semantically_rich_connector = any(w in lower_statement for w in 
                    ["because", "therefore", "causes", "results", "enables", "defines", "is"])
                has_entity = any(len(w) > 3 for w in claim.statement.split())
                
                # Accept if: 4+ words OR (< 4 words BUT has rich semantics AND has entities)
                if word_count < 4 and not (has_semantically_rich_connector and has_entity):
                    rejection_reason = "REJECTED: Statement lacks sufficient information"
            
            # Logical leap detection: only flag unjustified causal claims
            # Decomposed queries (e.g., "How does X relate to Y?") can have implicit causality
            if not rejection_reason:
                explicit_causal_claims = [
                    "causes", "directly causes", "is the cause", "resulted in", "led to",
                    "produced", "generated", "created"
                ]
                has_strong_causal = any(w in lower_statement for w in explicit_causal_claims)
                
                if has_strong_causal:
                    # Only reject if source has NO causal language at all
                    support_causal = [
                        "because", "due to", "caused by", "results in", "leads to",
                        "cause", "result", "effect", "therefore", "thus", "consequently",
                        "origin", "source", "root", "foundation"
                    ]
                    support_has = any(w in lower_support for w in support_causal)
                    
                    if not support_has:
                        rejection_reason = "REJECTED: Causal claim lacks supporting evidence"

            # Grounding check: adaptive overlap based on claim type
            filtered_tokens = []
            if not rejection_reason:
                statement_tokens = self._tokenize(lower_statement)
                support_tokens = set(self._tokenize(lower_support))
                
                filtered_tokens = [w for w in statement_tokens if w not in STOP_WORDS]
                if not filtered_tokens:
                    filtered_tokens = statement_tokens

                overlap = sum(1 for w in filtered_tokens if w in support_tokens)
                
                # Adaptive threshold: speculative claims need less strict overlap
                claim_type = self._detect_claim_type(claim.statement)
                threshold = 0.5 if claim_type == "speculative" else 0.6
                
                # #region agent log
                import json;open('/mnt/d/Desktop/deepdag/.cursor/debug.log','a').write(json.dumps({"location":"service.py:126","message":"grounding check","data":{"overlap":overlap,"filtered_tokens_len":len(filtered_tokens),"threshold":threshold,"claim_type":claim_type,"overlap_ratio":overlap/len(filtered_tokens) if len(filtered_tokens) > 0 else 0},"timestamp":__import__('datetime').datetime.now().timestamp()*1000,"sessionId":"debug-session","hypothesisId":"H5"})+'\n')
                # #endregion
                
                if len(filtered_tokens) > 0 and (overlap / len(filtered_tokens)) < threshold:
                    rejection_reason = f"REJECTED: Low grounding"

            # Inference indicator check: reject if statement has inference words not in support
            if not rejection_reason:
                inference_indicators = [
                    "because", "therefore", "thus", "hence", "consequently", 
                    "as a result", "leads to", "causes", "due to", "results in"
                ]
                for indicator in inference_indicators:
                    if indicator in lower_statement and indicator not in lower_support:
                        rejection_reason = f"REJECTED: Inference indicator '{indicator}' not supported by source"
                        break
            
            # Embellishment check: detect quantifiers/qualifiers added to claims
            if not rejection_reason:
                embellishments = [
                    ("for all", "for"), ("all its", "its"), ("every", ""),
                    ("always", ""), ("never", ""), ("completely", ""),
                    ("entirely", ""), ("absolutely", "")
                ]
                for embellished, base in embellishments:
                    if embellished in lower_statement and embellished not in lower_support:
                        # Check if even the base form conveys same meaning
                        rejection_reason = f"REJECTED: Embellishment '{embellished}' not in source"
                        break
            
            # Paraphrase tolerance: 70% key term overlap (skips verbatim check)
            if not rejection_reason:
                if claim.statement not in claim.support_text:
                    key_words = self._extract_key_terms(lower_statement, STOP_WORDS)
                    support_key_words = set(self._extract_key_terms(lower_support, STOP_WORDS))
                    
                    if key_words:
                        overlap_keys = key_words.intersection(support_key_words)
                        if len(overlap_keys) / len(key_words) < 0.7:
                            rejection_reason = "REJECTED: Key terms missing from source"

            # Initial Relevance Calculation
            entailment_score = 0.0
            if not rejection_reason:
                claim_tokens = set(w for w in filtered_tokens if w not in STOP_WORDS)
                if not claim_tokens:
                     claim_tokens = set(self._tokenize(lower_statement))

                relevance_overlap = task_tokens.intersection(claim_tokens)
                
                if claim_tokens:
                    entailment_score = len(relevance_overlap) / len(claim_tokens)
                
                # #region agent log
                import json;open('/mnt/d/Desktop/deepdag/.cursor/debug.log','a').write(json.dumps({"location":"service.py:150","message":"relevance score","data":{"entailment_score":entailment_score,"claim_tokens":list(claim_tokens),"task_tokens":list(task_tokens),"relevance_overlap":list(relevance_overlap)},"timestamp":__import__('datetime').datetime.now().timestamp()*1000,"sessionId":"debug-session","hypothesisId":"H1"})+'\n')
                # #endregion
                
                # Semantic boost check
                if not relevance_overlap:
                    support_key = self._extract_key_terms(lower_support, STOP_WORDS)
                    task_key = self._extract_key_terms(task.lower(), STOP_WORDS)
                    if support_key.intersection(task_key):
                        entailment_score = max(entailment_score, 0.5)

            candidates.append({
                "claim": claim,
                "reason": rejection_reason,
                "score": entailment_score,
                "entities": [e.lower() for e in claim.discovered_entities]
            })

        # PASS 2: Bridging & Final Verdict
        
        # 2a. Identify Valid Subtopics (Bridging Entities)
        # Collect entities from claims that are verified AND have high direct relevance
        verified_subtopics = set()
        for c in candidates:
            if not c["reason"] and c["score"] >= 0.4:
                # This claim is relevant to the main task. Its entities are now valid subtopics.
                for ent in c["entities"]:
                    verified_subtopics.add(ent)
        
        # 2b. Re-evaluate Low Relevance Claims
        results = []
        for c in candidates:
            claim = c["claim"]
            reason = c["reason"]
            score = c["score"]
            
            # #region agent log
            import json;open('/mnt/d/Desktop/deepdag/.cursor/debug.log','a').write(json.dumps({"location":"service.py:179","message":"pass2 evaluation","data":{"claim_id":claim.claim_id,"score":score,"has_reason":bool(reason),"threshold_check":score < 0.1},"timestamp":__import__('datetime').datetime.now().timestamp()*1000,"sessionId":"debug-session","hypothesisId":"H1"})+'\n')
            # #endregion
            
            if not reason:
                # If relevance is low, try to rescue via subtopics
                if score < 0.1: # Threshold for "low/no relevance" - catches truly irrelevant claims
                    # Check if claim mentions any verified subtopic
                    claim_text = (claim.statement + " " + claim.support_text).lower()
                    
                    # We accept partial matches for entities (e.g. "RSA" in "RSA Algorithm")
                    has_subtopic = any(sub in claim_text for sub in verified_subtopics if len(sub) > 2)
                    
                    if has_subtopic:
                        score = 0.5 # Boost to acceptable relevance
                        # Log the rescue for debugging
                        self.logger.log("claim_rescued_by_subtopic", {
                            "claim_id": claim.claim_id,
                            "subtopic_match": "true"
                        })
                    else:
                        # Reject low-relevance claims that can't be bridged via subtopics
                        reason = "REJECTED: Not relevant to task"
            
            if reason:
                # #region agent log
                import json;open('/mnt/d/Desktop/deepdag/.cursor/debug.log','a').write(json.dumps({"location":"service.py:206","message":"logging rejection","data":{"claim_id":claim.claim_id,"reason":reason,"has_source_url":hasattr(claim,'source_url'),"source_url_val":getattr(claim,'source_url',None)},"timestamp":__import__('datetime').datetime.now().timestamp()*1000,"sessionId":"debug-session","hypothesisId":"H6"})+'\n')
                # #endregion
                self.logger.log("claim_rejected", {
                    "claim_id": claim.claim_id, 
                    "reason": reason,
                    "statement": claim.statement if len(claim.statement) <= 50 else claim.statement[:50] + "...",
                    "source_url": claim.source_url,
                    "source_title": getattr(claim, 'source_title', None)
                })
                claim.confidence = 0.0
                results.append(CritiqueResult(
                    claim=claim, 
                    is_valid=False, 
                    reason=reason,
                    entailment_score=score
                ))
            else:
                if claim.confidence < 0.9:
                    claim.confidence = min(claim.confidence + 0.1, 1.0)
                results.append(CritiqueResult(
                    claim=claim, 
                    is_valid=True, 
                    reason="Verified",
                    entailment_score=score
                ))
            
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
    
    def _detect_claim_type(self, statement: str) -> str:
        """Detect claim type: 'factual', 'speculative', or 'mixed'.
        
        Factual: Present tense, definitive language, past events
        Speculative: Modal verbs, uncertainty indicators, conditional
        """
        lower_stmt = statement.lower()
        
        # Speculative indicators
        speculative_markers = [
            "might", "may", "could", "possibly", "perhaps", "likely", "probably",
            "appears to", "seems to", "suggests", "indicates", "implies", "would",
            "if", "whether", "could be", "may be", "might be", "could have",
            "could happen", "remains to be", "awaits", "unclear"
        ]
        
        # Factual indicators - expanded to catch more verbs
        factual_markers = [
            "is", "was", "are", "were", "has been", "have been", "does", "did",
            "evidence shows", "research confirms", "studies indicate", "proven",
            "established", "documented", "identified", "discovered", "found",
            "orbits", "contains", "comprises", "includes", "consists", "measures"
        ]
        
        speculative_count = sum(1 for m in speculative_markers if m in lower_stmt)
        factual_count = sum(1 for m in factual_markers if m in lower_stmt)
        
        # If no markers at all, assume factual (default for simple statements)
        if speculative_count == 0 and factual_count == 0:
            return "factual"
        
        # #region agent log
        import json;open('/mnt/d/Desktop/deepdag/.cursor/debug.log','a').write(json.dumps({"location":"service.py:280","message":"claim type detection","data":{"statement":statement,"speculative_count":speculative_count,"factual_count":factual_count},"timestamp":__import__('datetime').datetime.now().timestamp()*1000,"sessionId":"debug-session","hypothesisId":"H4"})+'\n')
        # #endregion
        
        if speculative_count > factual_count:
            return "speculative"
        elif factual_count > speculative_count:
            return "factual"
        else:
            return "mixed"
