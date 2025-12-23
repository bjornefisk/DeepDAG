import abc
import time
from typing import List, Optional

from .schema import SearchResponse, SearchResult

class SearchProvider(abc.ABC):
    """Abstract Base Class for Search Providers.
    
    Enforces a consistent interface regardless of the underlying API (Google, Bing, Serper, etc.).
    """
    
    # Safety cap to prevent context window flooding or excessive API costs
    HARD_LIMIT_SOURCES = 10

    @abc.abstractmethod
    def search(self, query: str, max_results: int = 5) -> SearchResponse:
        """Execute a search query and return normalized results.
        
        Args:
            query: The search string.
            max_results: Maximum number of results to return. Clamped to HARD_LIMIT_SOURCES (10).
            
        Returns:
            SearchResponse: Structured response containing list of SearchResult.
            
        Raises:
            SearchError: If the downstream API fails or rate limit is exceeded.
        """
        pass
    
    def _validate_limit(self, requested: int) -> int:
        """Clamps the requested limit to the global hard cap."""
        if requested < 1:
            return 1
        return min(requested, self.HARD_LIMIT_SOURCES)

    @abc.abstractmethod
    def health_check(self) -> bool:
        """Verify provider connectivity."""
        pass

class SearchError(Exception):
    """Base exception for search tool failures."""
    pass
