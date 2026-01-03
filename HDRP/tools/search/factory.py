import os
from typing import Any, Optional

from .base import SearchProvider
from .simulated import SimulatedSearchProvider


class SearchFactory:
    """Factory to instantiate the appropriate search provider based on configuration."""
    
    @staticmethod
    def get_provider(
        provider_type: str = "simulated",
        api_key: Optional[str] = None,
        **provider_kwargs: Any,
    ) -> SearchProvider:
        """Instantiate a concrete SearchProvider.

        Args:
            provider_type: Identifier for the provider implementation
                (e.g. \"simulated\", \"tavily\").
            api_key: Optional API key for providers that require it.
            provider_kwargs: Provider-specific configuration (e.g. timeouts).
        """
        if provider_type == "simulated":
            return SimulatedSearchProvider()
        elif provider_type == "google":
            # In a real app, this would return GoogleSearchProvider(api_key)
            raise NotImplementedError("Google provider not yet configured")
        elif provider_type == "tavily":
            # Import lazily to avoid unnecessary dependencies when Tavily is unused.
            from .tavily import TavilySearchProvider

            return TavilySearchProvider(api_key=api_key, **provider_kwargs)
        else:
            raise ValueError(f"Unknown provider type: {provider_type}")

    @staticmethod
    def from_env(default_provider: str = "simulated") -> SearchProvider:
        """Create a provider based on environment variables.

        Environment variables:
            HDRP_SEARCH_PROVIDER: which provider to use (\"simulated\", \"tavily\").
            TAVILY_API_KEY: API key for Tavily (required when provider is \"tavily\").
            TAVILY_SEARCH_DEPTH: optional search depth (\"basic\" / \"advanced\").
            TAVILY_TOPIC: optional topic bias (\"general\", \"news\", ...).
            TAVILY_MAX_RESULTS: default max results per query (int).
            TAVILY_TIMEOUT_SECONDS: HTTP timeout for Tavily requests (float seconds).
        """
        provider_type = os.getenv("HDRP_SEARCH_PROVIDER", default_provider).lower()

        if provider_type == "tavily":
            api_key = os.getenv("TAVILY_API_KEY")
            search_depth = os.getenv("TAVILY_SEARCH_DEPTH", "basic")
            topic = os.getenv("TAVILY_TOPIC", "general")

            timeout_env = os.getenv("TAVILY_TIMEOUT_SECONDS", "")
            max_results_env = os.getenv("TAVILY_MAX_RESULTS", "")

            timeout_seconds: Optional[float]
            default_max_results: Optional[int]

            try:
                timeout_seconds = float(timeout_env) if timeout_env else 8.0
            except ValueError:
                timeout_seconds = 8.0

            try:
                default_max_results = int(max_results_env) if max_results_env else None
            except ValueError:
                default_max_results = None

            provider = SearchFactory.get_provider(
                "tavily",
                api_key=api_key,
                search_depth=search_depth,
                topic=topic,
                timeout_seconds=timeout_seconds,
                default_max_results=default_max_results,
            )

            # If Tavily is misconfigured (e.g., missing key) or fails a
            # lightweight health check, fall back to the deterministic
            # simulated provider to keep evaluation flows robust.
            try:
                if not provider.health_check():
                    print(
                        "[search.factory] Tavily is misconfigured; "
                        "falling back to simulated provider."
                    )
                    return SearchFactory.get_provider("simulated")
            except Exception:
                print(
                    "[search.factory] Tavily health check failed; "
                    "falling back to simulated provider."
                )
                return SearchFactory.get_provider("simulated")

            return provider

        # Default: purely local, deterministic provider.
        return SearchFactory.get_provider("simulated")
