import os
from typing import Any, Optional

from .base import SearchProvider, SearchError
from .simulated import SimulatedSearchProvider
from .api_key_validator import APIKeyError


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
                (e.g. \"simulated\", \"tavily\", \"google\", \"bing\").
            api_key: Optional API key for providers that require it.
            provider_kwargs: Provider-specific configuration (e.g. timeouts).
        """
        if provider_type == "simulated":
            return SimulatedSearchProvider()
        elif provider_type == "google":
            # Import lazily to avoid unnecessary dependencies when Google is unused.
            from .google import GoogleSearchProvider

            return GoogleSearchProvider(api_key=api_key, **provider_kwargs)
        elif provider_type == "bing":
            # Import lazily to avoid unnecessary dependencies when Bing is unused.
            from .bing import BingSearchProvider

            return BingSearchProvider(api_key=api_key, **provider_kwargs)
        elif provider_type == "tavily":
            # Import lazily to avoid unnecessary dependencies when Tavily is unused.
            from .tavily import TavilySearchProvider

            return TavilySearchProvider(api_key=api_key, **provider_kwargs)
        else:
            raise ValueError(f"Unknown provider type: {provider_type}")

    @staticmethod
    def from_env(
        default_provider: str = "simulated",
        strict_mode: bool = False,
    ) -> SearchProvider:
        """Create a provider based on environment variables.

        Environment variables:
            HDRP_SEARCH_PROVIDER: which provider to use (\"simulated\", \"tavily\", \"google\", \"bing\").
            
            Tavily:
                TAVILY_API_KEY: API key for Tavily (required when provider is \"tavily\").
                TAVILY_SEARCH_DEPTH: optional search depth (\"basic\" / \"advanced\").
                TAVILY_TOPIC: optional topic bias (\"general\", \"news\", ...).
                TAVILY_MAX_RESULTS: default max results per query (int).
                TAVILY_TIMEOUT_SECONDS: HTTP timeout for Tavily requests (float seconds).
            
            Google:
                GOOGLE_API_KEY: API key for Google Custom Search (required).
                GOOGLE_CX: Custom Search Engine ID (required).
                GOOGLE_TIMEOUT_SECONDS: HTTP timeout (float seconds).
                GOOGLE_MAX_RESULTS: default max results per query (int).
            
            Bing:
                BING_API_KEY: API key for Bing Web Search (required).
                BING_MARKET: market code (default \"en-US\").
                BING_TIMEOUT_SECONDS: HTTP timeout (float seconds).
                BING_MAX_RESULTS: default max results per query (int).
        
        Args:
            default_provider: Provider to use if HDRP_SEARCH_PROVIDER is not set.
            strict_mode: If True, raise errors on misconfiguration instead of
                        falling back to simulated provider.
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

            try:
                provider = SearchFactory.get_provider(
                    "tavily",
                    api_key=api_key,
                    search_depth=search_depth,
                    topic=topic,
                    timeout_seconds=timeout_seconds,
                    default_max_results=default_max_results,
                )
                
                # Verify health check passes
                if not provider.health_check():
                    if strict_mode:
                        raise SearchError(
                            "Tavily provider failed health check. "
                            "Please verify your API key configuration."
                        )
                    print(
                        "[search.factory] Tavily is misconfigured; "
                        "falling back to simulated provider."
                    )
                    return SearchFactory.get_provider("simulated")
                    
                return provider
                
            except (SearchError, APIKeyError) as e:
                if strict_mode:
                    raise SearchError(
                        f"Failed to initialize Tavily provider: {e}"
                    ) from e
                print(
                    f"[search.factory] Tavily initialization failed: {e}\n"
                    "[search.factory] Falling back to simulated provider."
                )
                return SearchFactory.get_provider("simulated")
            except Exception as e:
                if strict_mode:
                    raise SearchError(
                        f"Unexpected error initializing Tavily provider: {e}"
                    ) from e
                print(
                    "[search.factory] Tavily health check failed; "
                    "falling back to simulated provider."
                )
                return SearchFactory.get_provider("simulated")

        elif provider_type == "google":
            api_key = os.getenv("GOOGLE_API_KEY")
            cx = os.getenv("GOOGLE_CX")
            timeout_env = os.getenv("GOOGLE_TIMEOUT_SECONDS", "")
            max_results_env = os.getenv("GOOGLE_MAX_RESULTS", "")

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

            try:
                provider = SearchFactory.get_provider(
                    "google",
                    api_key=api_key,
                    cx=cx,
                    timeout_seconds=timeout_seconds,
                    default_max_results=default_max_results,
                )
                
                # Verify health check passes
                if not provider.health_check():
                    if strict_mode:
                        raise SearchError(
                            "Google provider failed health check. "
                            "Please verify your API key and CX configuration."
                        )
                    print(
                        "[search.factory] Google is misconfigured; "
                        "falling back to simulated provider."
                    )
                    return SearchFactory.get_provider("simulated")
                    
                return provider
                
            except (SearchError, APIKeyError) as e:
                if strict_mode:
                    raise SearchError(
                        f"Failed to initialize Google provider: {e}"
                    ) from e
                print(
                    f"[search.factory] Google initialization failed: {e}\n"
                    "[search.factory] Falling back to simulated provider."
                )
                return SearchFactory.get_provider("simulated")
            except Exception as e:
                if strict_mode:
                    raise SearchError(
                        f"Unexpected error initializing Google provider: {e}"
                    ) from e
                print(
                    "[search.factory] Google health check failed; "
                    "falling back to simulated provider."
                )
                return SearchFactory.get_provider("simulated")

        elif provider_type == "bing":
            api_key = os.getenv("BING_API_KEY")
            market = os.getenv("BING_MARKET", "en-US")
            timeout_env = os.getenv("BING_TIMEOUT_SECONDS", "")
            max_results_env = os.getenv("BING_MAX_RESULTS", "")

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

            try:
                provider = SearchFactory.get_provider(
                    "bing",
                    api_key=api_key,
                    market=market,
                    timeout_seconds=timeout_seconds,
                    default_max_results=default_max_results,
                )
                
                # Verify health check passes
                if not provider.health_check():
                    if strict_mode:
                        raise SearchError(
                            "Bing provider failed health check. "
                            "Please verify your API key configuration."
                        )
                    print(
                        "[search.factory] Bing is misconfigured; "
                        "falling back to simulated provider."
                    )
                    return SearchFactory.get_provider("simulated")
                    
                return provider
                
            except (SearchError, APIKeyError) as e:
                if strict_mode:
                    raise SearchError(
                        f"Failed to initialize Bing provider: {e}"
                    ) from e
                print(
                    f"[search.factory] Bing initialization failed: {e}\n"
                    "[search.factory] Falling back to simulated provider."
                )
                return SearchFactory.get_provider("simulated")
            except Exception as e:
                if strict_mode:
                    raise SearchError(
                        f"Unexpected error initializing Bing provider: {e}"
                    ) from e
                print(
                    "[search.factory] Bing health check failed; "
                    "falling back to simulated provider."
                )
                return SearchFactory.get_provider("simulated")

        # Default: purely local, deterministic provider.
        return SearchFactory.get_provider("simulated")
