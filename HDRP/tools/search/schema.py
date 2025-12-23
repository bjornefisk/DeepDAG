from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime

class SearchResult(BaseModel):
    """Normalized data model for a single search result."""
    title: str = Field(..., description="The title of the web page")
    url: str = Field(..., description="The direct link to the result")
    snippet: str = Field(..., description="A short summary or snippet from the page")
    source: str = Field(..., description="The provider source (e.g., google, ddg)")
    published_date: Optional[str] = Field(None, description="Publication date if available")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Raw provider metadata")

class SearchResponse(BaseModel):
    """Container for the full search operation response."""
    query: str
    results: List[SearchResult]
    total_found: int = 0
    latency_ms: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
