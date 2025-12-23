import abc
import time
from typing import List, Optional

from .schema import SearchResponse, SearchResult

class SearchProvider(abc.ABC):
    """Abstract Base Class for Search Providers.
    
    Enforces a consistent interface regardless of the underlying API (Google, Bing, Serper, etc.).
    """

    @abc.abstractmethod
    def search(self, query: str, max_results: int = 5) -> SearchResponse:
        """Execute a search query and return normalized results.
        
        Args:
            query: The search string.
            max_results: Maximum number of results to return.
            
        Returns:
            SearchResponse: Structured response containing list of SearchResult.
            
        Raises:
            SearchError: If the downstream API fails or rate limit is exceeded.
        """
        pass

    @abc.abstractmethod
    def health_check(self) -> bool:
        """Verify provider connectivity."""
        pass

class SearchError(Exception):
    """Base exception for search tool failures."""
    pass
