"""
Integration example: Using MultiSearchProvider with HDRP CLI

This shows how to modify the CLI to use multiple search providers simultaneously.
"""

# Add this to HDRP/cli.py to enable multi-provider mode

def _build_multi_search_provider(api_keys: dict) -> SearchProvider:
    """
    Build a MultiSearchProvider from available API keys.
    
    Args:
        api_keys: Dictionary with keys like 'tavily', 'google_key', 'google_cx', 'bing'
    
    Returns:
        MultiSearchProvider configured with all available providers
    """
    from HDRP.tools.search import (
        MultiSearchProvider,
        TavilySearchProvider,
        GoogleSearchProvider,
        BingSearchProvider,
    )
    
    providers = []
    
    # Add Tavily if available
    if api_keys.get('tavily'):
        try:
            tavily = TavilySearchProvider(api_key=api_keys['tavily'])
            if tavily.health_check():
                providers.append(tavily)
                print("[multi-search] ✓ Tavily provider added")
        except Exception as e:
            print(f"[multi-search] ✗ Tavily failed: {e}")
    
    # Add Google if available
    if api_keys.get('google_key') and api_keys.get('google_cx'):
        try:
            google = GoogleSearchProvider(
                api_key=api_keys['google_key'],
                cx=api_keys['google_cx']
            )
            if google.health_check():
                providers.append(google)
                print("[multi-search] ✓ Google provider added")
        except Exception as e:
            print(f"[multi-search] ✗ Google failed: {e}")
    
    # Add Bing if available
    if api_keys.get('bing'):
        try:
            bing = BingSearchProvider(api_key=api_keys['bing'])
            if bing.health_check():
                providers.append(bing)
                print("[multi-search] ✓ Bing provider added")
        except Exception as e:
            print(f"[multi-search] ✗ Bing failed: {e}")
    
    if not providers:
        raise ValueError("No search providers available. Please configure API keys.")
    
    print(f"[multi-search] Using {len(providers)} provider(s)")
    
    return MultiSearchProvider(
        providers=providers,
        dedup_by_url=True,
        dedup_by_domain_limit=3,
        timeout_seconds=10.0,
    )


# Example usage in CLI:
# 
# To enable multi-provider mode, set environment variable:
# export HDRP_SEARCH_PROVIDER=multi
# 
# Then configure all the providers you want to use:
# export TAVILY_API_KEY="your-tavily-key"
# export GOOGLE_API_KEY="your-google-key"
# export GOOGLE_CX="your-cx"
# export BING_API_KEY="your-bing-key"
# 
# Run the CLI:
# python -m HDRP.cli run --query "quantum computing"
# 
# The system will automatically use all configured providers!
