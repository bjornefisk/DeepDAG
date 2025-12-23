from typing import Optional
from .base import SearchProvider
from .simulated import SimulatedSearchProvider

class SearchFactory:
    """Factory to instantiate the appropriate search provider based on configuration."""
    
    @staticmethod
    def get_provider(provider_type: str = "simulated", api_key: Optional[str] = None) -> SearchProvider:
        if provider_type == "simulated":
            return SimulatedSearchProvider()
        elif provider_type == "google":
            # In a real app, this would return GoogleSearchProvider(api_key)
            raise NotImplementedError("Google provider not yet configured")
        elif provider_type == "tavily":
             # In a real app, this would return TavilyProvider(api_key)
             raise NotImplementedError("Tavily provider not yet configured")
        else:
            raise ValueError(f"Unknown provider type: {provider_type}")
