import abc
from typing import List

from .schema import SearchResponse


class SearchProvider(abc.ABC):
    """Abstract Base Class for Search Providers.
    
    Enforces a consistent interface regardless of the underlying API (Google, Bing, Serper, Tavily, etc.).
    
    Providers are expected to respect:
    - HARD_LIMIT_SOURCES: global hard cap on returned sources to avoid context flooding / excessive cost.
    - DEFAULT_MAX_RESULTS: conventional per-query default used by callers such as the ReActAgent.
    """
    
    # Safety cap to prevent context window flooding or excessive API costs.
    HARD_LIMIT_SOURCES = 10
    # Conventional default when callers do not specify max_results explicitly.
    DEFAULT_MAX_RESULTS = 5

    @abc.abstractmethod
    def search(self, query: str, max_results: int = DEFAULT_MAX_RESULTS) -> SearchResponse:
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
