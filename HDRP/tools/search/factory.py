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
                (e.g. \"simulated\", \"google\").
            api_key: Optional API key for providers that require it.
            provider_kwargs: Provider-specific configuration (e.g. timeouts).
        """
        if provider_type == "simulated":
            return SimulatedSearchProvider()
        elif provider_type == "google":
            # Import lazily to avoid unnecessary dependencies when Google is unused.
            from .google import GoogleSearchProvider

            return GoogleSearchProvider(api_key=api_key, **provider_kwargs)
        else:
            raise ValueError(f"Unknown provider type: {provider_type}")

    @staticmethod
    def from_env(
        default_provider: str = "simulated",
        strict_mode: bool = False,
    ) -> SearchProvider:
        """Create a provider based on centralized settings.

        Uses HDRP settings loaded from:
        1. Environment variables (highest precedence)
        2. Environment-specific YAML (config.{env}.yaml)
        3. Base YAML (config.yaml)
        
        Args:
            default_provider: Provider to use if not configured.
            strict_mode: If True, raise errors on misconfiguration instead of
                        falling back to simulated provider.
        """
        from HDRP.services.shared.settings import get_settings
        
        settings = get_settings()
        provider_type = settings.search.provider or default_provider

        if provider_type == "google":
            # Get Google-specific settings
            google_config = settings.search.google
            
            # Extract API key (SecretStr)
            api_key = None
            if google_config.api_key:
                api_key = google_config.api_key.get_secret_value()
            
            cx = google_config.cx
            timeout_seconds = google_config.timeout_seconds
            default_max_results = google_config.max_results

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

        # Default: purely local, deterministic provider.
        return SearchFactory.get_provider("simulated")

