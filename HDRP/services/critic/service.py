from typing import List, Optional, Dict, Tuple
from concurrent.futures import ThreadPoolExecutor
from HDRP.services.shared.claims import AtomicClaim, CritiqueResult
from HDRP.services.shared.logger import ResearchLogger
from HDRP.services.shared.errors import CriticError, report_error
from HDRP.services.shared.profiling_utils import profile_block, enable_profiling_env
from HDRP.services.shared.settings import get_settings
from HDRP.services.critic.nli_verifier import NLIVerifier
from HDRP.services.critic.nli_http_client import NLIHttpClient
from datetime import datetime

class CriticService:
    """Service responsible for verifying claims found by the Researcher.
    
    It ensures that every claim has a valid source URL and supporting text, 
    and (in production) would use an LLM to verify the semantic alignment 
    between the statement and the support text.
    
    Optimized with batch verification and tokenization caching.
    """
    def __init__(
        self,
        run_id: Optional[str] = None,
        use_nli: bool = True,
        nli_threshold: Optional[float] = None,
        nli_contradiction_threshold: Optional[float] = None,
        nli_client: Optional[NLIHttpClient] = None,
        nli_variant: Optional[str] = None,
    ):
        """Initialize CriticService.
        
        Args:
            run_id: Optional run ID for logging
            use_nli: Whether to use NLI-based verification (True) or heuristic fallback (False)
            nli_threshold: NLI entailment score threshold for accepting claims
                          Default 0.60 determined via grid search optimization (see artifacts/threshold_optimization.json)
                          Previous hardcoded value of 0.65 was too strict, causing false negatives
        """
        self.logger = ResearchLogger("critic", run_id=run_id)
        self.enable_profiling = enable_profiling_env()
        self._tokenization_cache: Dict[str, List[str]] = {}
        self._executor = ThreadPoolExecutor(max_workers=4)
        
        # NLI-based verification
        settings = get_settings()
        nli_settings = settings.nli

        self.use_nli = use_nli
        self.nli_threshold = (
            nli_threshold
            if nli_threshold is not None
            else getattr(nli_settings, "entailment_threshold", 0.60)
        )
        self.nli_contradiction_threshold = (
            nli_contradiction_threshold
            if nli_contradiction_threshold is not None
            else getattr(nli_settings, "contradiction_threshold", 0.20)
        )
        self._nli_verifier: Optional[NLIVerifier] = None
        self.nli_variant = nli_variant
        if self.use_nli:
            self._nli_verifier = nli_client or NLIVerifier()
    
    def verify(self, claims: List[AtomicClaim], task: str) -> List[CritiqueResult]:
        """Verify claims with balanced precision/recall using query decomposition logic.
        
        Implements a two-pass verification:
        1. Direct Relevance: Validates claims directly against the task.
        2. Bridging (Subtopic) Relevance: Accepts claims that match entities discovered 
           in the high-confidence claims from pass 1. This solves the "partial relevance"
           problem for complex queries (e.g. "RSA" details are relevant to "Cryptography"
           if "RSA" was established as a subtopic).
        """
        results = []
        
        try:
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
                try:
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

                    # Grounding check: NLI-based or heuristic overlap
                    filtered_tokens = []
                    nli_score = None
                    if not rejection_reason:
                        if self.use_nli and self._nli_verifier:
                            # NLI-based verification
                            if isinstance(self._nli_verifier, NLIHttpClient):
                                relation = self._nli_verifier.compute_relation(
                                    premise=claim.support_text,
                                    hypothesis=claim.statement,
                                    variant=self.nli_variant,
                                )
                            else:
                                relation = self._nli_verifier.compute_relation(
                                    premise=claim.support_text,
                                    hypothesis=claim.statement
                                )
                            nli_score = relation["entailment"]
                            contradiction_score = relation["contradiction"]

                            if contradiction_score > self.nli_contradiction_threshold:
                                rejection_reason = (
                                    "REJECTED: Source contradicts statement "
                                    f"(NLI entailment: {nli_score:.2f}, contradiction: {contradiction_score:.2f})"
                                )
                            elif nli_score < self.nli_threshold:
                                rejection_reason = (
                                    "REJECTED: Low grounding "
                                    f"(NLI entailment: {nli_score:.2f}, contradiction: {contradiction_score:.2f})"
                                )
                        else:
                            # Fallback to heuristic word overlap
                            statement_tokens = self._tokenize(lower_statement)
                            support_tokens = set(self._tokenize(lower_support))
                            
                            filtered_tokens = [w for w in statement_tokens if w not in STOP_WORDS]
                            if not filtered_tokens:
                                filtered_tokens = statement_tokens

                            overlap = sum(1 for w in filtered_tokens if w in support_tokens)
                            
                            # Adaptive threshold: speculative claims need less strict overlap
                            claim_type = self._detect_claim_type(claim.statement)
                            threshold = 0.5 if claim_type == "speculative" else 0.6
                            
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
                
                except Exception as e:
                    # Error verifying individual claim - mark as rejected but continue
                    self.logger.log("claim_verification_error", {
                        "claim_id": claim.claim_id,
                        "error": str(e),
                        "type": type(e).__name__
                    })
                    candidates.append({
                        "claim": claim,
                        "reason": f"REJECTED: Verification error - {str(e)}",
                        "score": 0.0,
                        "entities": []
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
                    log_data = {
                        "claim_id": claim.claim_id, 
                        "reason": reason,
                        "statement": claim.statement if len(claim.statement) <= 50 else claim.statement[:50] + "...",
                        "source_url": claim.source_url,
                        "source_title": getattr(claim, 'source_title', None)
                    }
                    # Add NLI scores if available
                    if self.use_nli and "NLI" in reason:
                        import re

                        entailment_match = re.search(r'NLI entailment: (\d+\.\d+)', reason)
                        contradiction_match = re.search(r'contradiction: (\d+\.\d+)', reason)
                        legacy_match = re.search(r'NLI score: (\d+\.\d+)', reason)

                        if entailment_match:
                            log_data["nli_entailment"] = float(entailment_match.group(1))
                        if contradiction_match:
                            log_data["nli_contradiction"] = float(contradiction_match.group(1))
                        if legacy_match:
                            log_data["nli_score"] = float(legacy_match.group(1))
                    
                    self.logger.log("claim_rejected", log_data)
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
                    
                    # Log NLI verification if used
                    if self.use_nli:
                        self.logger.log("claim_verified", {
                            "claim_id": claim.claim_id,
                            "nli_threshold": self.nli_threshold,
                            "verification_method": "nli"
                        })
                    
                    results.append(CritiqueResult(
                        claim=claim, 
                        is_valid=True, 
                        reason="Verified",
                        entailment_score=score
                    ))
            
            return results
        
        except Exception as e:
            # Catastrophic error in verification - wrap and report
            error = CriticError(
                message=f"Verification failed: {str(e)}",
                run_id=self.logger.run_id,
                metadata={
                    "task": task,
                    "claims_count": len(claims),
                    "original_error": type(e).__name__
                }
            )
            report_error(error, run_id=self.logger.run_id, service="critic")
            
            # Return all claims as rejected rather than crashing
            self.logger.log("verification_failed", {
                "task": task,
                "claims_count": len(claims),
                "error": str(e)
            })
            
            return [
                CritiqueResult(
                    claim=claim,
                    is_valid=False,
                    reason=f"REJECTED: Verification service error",
                    entailment_score=0.0
                )
                for claim in claims
            ]
    
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
        """Tokenize: strip punctuation and split (with caching)."""
        # Check cache first
        if text in self._tokenization_cache:
            return self._tokenization_cache[text]
        
        import re
        clean_text = re.sub(r'[^\w\s]', ' ', text)
        tokens = clean_text.split()
        
        # Cache result (limit cache size)
        if len(self._tokenization_cache) < 1000:
            self._tokenization_cache[text] = tokens
        
        return tokens
    
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
        
        if speculative_count > factual_count:
            return "speculative"
        elif factual_count > speculative_count:
            return "factual"
        else:
            return "mixed"
    
    def verify_batch(self, claim_batches: List[Tuple[List[AtomicClaim], str]]) -> List[List[CritiqueResult]]:
        """Verify multiple batches of claims concurrently.
        
        Args:
            claim_batches: List of (claims, task) tuples
            
        Returns:
            List of verification results for each batch
        """
        def verify_single_batch(batch):
            claims, task = batch
            return self.verify(claims, task)
        
        # Process batches concurrently
        futures = [self._executor.submit(verify_single_batch, batch) for batch in claim_batches]
        results = []
        
        for future in futures:
            try:
                result = future.result(timeout=30)
                results.append(result)
            except Exception as e:
                self.logger.log("batch_verification_error", {
                    "error": str(e),
                    "type": type(e).__name__
                })
                results.append([])
        
        return results
    
    def __del__(self):
        """Cleanup thread pool on deletion."""
        if hasattr(self, '_executor'):
            self._executor.shutdown(wait=False)
