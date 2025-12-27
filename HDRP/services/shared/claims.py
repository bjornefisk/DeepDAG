from typing import List, Optional
from pydantic import BaseModel, Field
import uuid

class AtomicClaim(BaseModel):
    """Represents a single, non-decomposable factual statement."""
    claim_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    statement: str = Field(..., description="The factual claim in plain text")
    support_text: Optional[str] = Field(None, description="The specific snippet from the source that supports the claim")
    source_url: Optional[str] = Field(None, description="The URL of the source where the claim was found")
    source_node_id: Optional[str] = Field(None, description="The ID of the DAG node that generated this claim")
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    discovered_entities: List[str] = Field(default_factory=list, description="Entities identified in the claim that may be new topics")

class CritiqueResult(BaseModel):
    """Result of verifying a single atomic claim."""
    claim: AtomicClaim
    is_valid: bool
    reason: str

class ExtractionResponse(BaseModel):
    """Container for claims extracted from a specific source text."""
    source_text: str
    claims: List[AtomicClaim]
    metadata: dict = Field(default_factory=dict)

class ClaimExtractor:
    """Service to decompose complex text into atomic factual statements.
    
    This follows the 'Atomic Research' pattern where large documents are broken 
    into individual units of verification.
    """

    def extract(self, text: str, source_url: Optional[str] = None, source_node_id: Optional[str] = None) -> ExtractionResponse:
        """Parses text and extracts a list of atomic claims.
        
        For the MVP, this uses a combination of sentence splitting and 
        heuristic filtering. In production, this would be backed by a 
        specialized LLM prompt.
        """
        if not text or len(text.strip()) == 0:
            return ExtractionResponse(source_text=text, claims=[])

        # MVP Heuristic: Split by sentences and filter for 'fact-like' statements.
        sentences = self._split_sentences(text)
        extracted_claims = []

        for sentence in sentences:
            sentence = sentence.strip()
            if self._is_likely_factual(sentence):
                # For the MVP, the support text is the sentence itself found in the source.
                # In more advanced versions, this might include surrounding sentences for context.
                claim = AtomicClaim(
                    statement=sentence,
                    support_text=sentence, 
                    source_url=source_url,
                    source_node_id=source_node_id,
                    confidence=0.7, # Base confidence for heuristic extraction
                    discovered_entities=self._extract_entities(sentence)
                )
                extracted_claims.append(claim)

        return ExtractionResponse(
            source_text=text,
            claims=extracted_claims,
            metadata={"strategy": "heuristic_sentence_split", "input_len": len(text)}
        )

    def _split_sentences(self, text: str) -> List[str]:
        """Simple sentence splitter using punctuation boundaries."""
        import re
        # Split on . ! ? followed by space or newline
        return re.split(r'(?<=[.!?])\s+', text)

    def _is_likely_factual(self, sentence: str) -> bool:
        """Heuristic check to filter out non-factual content (queries, greetings, very short text)."""
        if len(sentence) < 20: # Too short to be a meaningful claim
            return False
        
        if sentence.endswith('?'): # It's a question
            return False

        subjective_indicators = ["i think", "i believe", "in my opinion", "hello", "hi there"]
        lower_s = sentence.lower()
        if any(indicator in lower_s for indicator in subjective_indicators):
            return False

        return True

    def _extract_entities(self, sentence: str) -> List[str]:
        """Heuristic: Extract capitalized words (potential named entities) not at start."""
        import re
        words = sentence.split()
        entities = []
        if not words:
            return []
        
        # Skip the first word to avoid sentence-start capitalization false positives
        for word in words[1:]:
            # Clean punctuation
            clean = re.sub(r'[^\w]', '', word)
            if clean and clean[0].isupper():
                entities.append(clean)
        
        return list(set(entities))
