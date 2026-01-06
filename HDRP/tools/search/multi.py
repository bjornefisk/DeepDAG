import time
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from .base import SearchProvider, SearchError
from .schema import SearchResponse, SearchResult


class MultiSearchProvider(SearchProvider):
    """Search provider that aggregates results from multiple providers.
    
    Queries multiple search providers in parallel and combines their results,
    removing duplicates and optionally ranking by provider priority.
    
    Example:
        providers = [
            TavilySearchProvider(api_key="..."),
            GoogleSearchProvider(api_key="...", cx="..."),
            BingSearchProvider(api_key="..."),
        ]
        multi = MultiSearchProvider(providers=providers)
        response = multi.search("quantum computing", max_results=10)
    """

    def __init__(
        self,
        providers: List[SearchProvider],
        dedup_by_url: bool = True,
        dedup_by_domain_limit: int = 3,
        timeout_seconds: float = 10.0,
    ) -> None:
        """Initialize multi-provider search.
        
        Args:
            providers: List of SearchProvider instances to query.
            dedup_by_url: If True, remove duplicate URLs from results.
            dedup_by_domain_limit: Maximum results per domain (0 = no limit).
            timeout_seconds: Maximum time to wait for all providers.
        """
        if not providers:
            raise ValueError("MultiSearchProvider requires at least one provider")
        
        self.providers = providers
        self.dedup_by_url = dedup_by_url
        self.dedup_by_domain_limit = dedup_by_domain_limit
        self.timeout_seconds = timeout_seconds

    def health_check(self) -> bool:
        """Return True if at least one provider is healthy."""
        return any(provider.health_check() for provider in self.providers)

    def search(self, query: str, max_results: int = None) -> SearchResponse:
        if max_results is None:
            max_results = self.DEFAULT_MAX_RESULTS

        safe_limit = self._validate_limit(max_results)
        start_time = time.time()

        # Query all providers in parallel
        all_results: List[SearchResult] = []
        provider_errors: Dict[str, str] = {}

        with ThreadPoolExecutor(max_workers=len(self.providers)) as executor:
            # Submit all search tasks
            future_to_provider = {
                executor.submit(self._safe_search, provider, query, safe_limit): provider
                for provider in self.providers
            }

            # Collect results as they complete
            for future in as_completed(future_to_provider, timeout=self.timeout_seconds):
                provider = future_to_provider[future]
                provider_name = provider.__class__.__name__
                
                try:
                    results = future.result()
                    all_results.extend(results)
                except Exception as e:
                    # Log error but continue with other providers
                    provider_errors[provider_name] = str(e)

        # If all providers failed, raise an error
        if not all_results:
            if provider_errors:
                error_summary = "; ".join(f"{name}: {err}" for name, err in provider_errors.items())
                raise SearchError(f"All providers failed: {error_summary}")
            else:
                # No results but no errors either - all providers returned empty
                pass  # Will return empty results below

        # Deduplicate and filter results
        filtered_results = self._deduplicate_results(all_results)
        
        # Limit to requested number
        final_results = filtered_results[:safe_limit]

        latency_ms = (time.time() - start_time) * 1000.0

        return SearchResponse(
            query=query,
            results=final_results,
            total_found=len(all_results),
            latency_ms=round(latency_ms, 2),
        )

    def _safe_search(
        self, 
        provider: SearchProvider, 
        query: str, 
        max_results: int
    ) -> List[SearchResult]:
        """Search a provider and return results."""
        response = provider.search(query, max_results=max_results)
        return response.results

    def _deduplicate_results(self, results: List[SearchResult]) -> List[SearchResult]:
        """Remove duplicate results based on URL and domain limits."""
        if not results:
            return []

        seen_urls = set()
        domain_counts: Dict[str, int] = {}
        deduplicated: List[SearchResult] = []

        for result in results:
            # Skip if we've seen this exact URL
            if self.dedup_by_url and result.url in seen_urls:
                continue

            # Extract domain for domain-based limiting
            domain = self._extract_domain(result.url)
            
            # Check domain limit
            if self.dedup_by_domain_limit > 0:
                domain_count = domain_counts.get(domain, 0)
                if domain_count >= self.dedup_by_domain_limit:
                    continue
                domain_counts[domain] = domain_count + 1

            # Add to results
            deduplicated.append(result)
            seen_urls.add(result.url)

        return deduplicated

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL for deduplication."""
        try:
            # Simple domain extraction
            parts = url.split("//")
            if len(parts) > 1:
                domain = parts[1].split("/")[0]
                return domain
            return "unknown"
        except Exception:
            return "unknown"
