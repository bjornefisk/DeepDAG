"""
Example: Using MultiSearchProvider to aggregate results from multiple providers.

This example demonstrates how to combine results from Tavily, Google, and Bing
to get broader coverage and better quality results.
"""

from HDRP.tools.search import (
    MultiSearchProvider,
    TavilySearchProvider,
    GoogleSearchProvider,
    BingSearchProvider,
)

# Initialize individual providers
# Note: You'll need valid API keys for each provider
providers = []

# Add Tavily if API key is available
try:
    tavily = TavilySearchProvider(api_key="your-tavily-key")
    if tavily.health_check():
        providers.append(tavily)
        print("✓ Tavily provider added")
except Exception as e:
    print(f"✗ Tavily provider failed: {e}")

# Add Google if API key and CX are available
try:
    google = GoogleSearchProvider(
        api_key="your-google-key",
        cx="your-search-engine-id"
    )
    if google.health_check():
        providers.append(google)
        print("✓ Google provider added")
except Exception as e:
    print(f"✗ Google provider failed: {e}")

# Add Bing if API key is available
try:
    bing = BingSearchProvider(api_key="your-bing-key")
    if bing.health_check():
        providers.append(bing)
        print("✓ Bing provider added")
except Exception as e:
    print(f"✗ Bing provider failed: {e}")

# Create multi-provider aggregator
if providers:
    multi = MultiSearchProvider(
        providers=providers,
        dedup_by_url=True,           # Remove duplicate URLs
        dedup_by_domain_limit=3,     # Max 3 results per domain
        timeout_seconds=10.0,         # Wait up to 10s for all providers
    )

    # Perform search
    query = "latest developments in quantum computing"
    print(f"\nSearching for: '{query}'")
    print(f"Using {len(providers)} provider(s)\n")

    response = multi.search(query, max_results=10)

    # Display results
    print(f"Found {len(response.results)} results (from {response.total_found} total)")
    print(f"Latency: {response.latency_ms}ms\n")

    for i, result in enumerate(response.results, 1):
        print(f"{i}. {result.title}")
        print(f"   URL: {result.url}")
        print(f"   Source: {result.source}")
        print(f"   Snippet: {result.snippet[:100]}...")
        print()
else:
    print("No providers available. Please configure API keys.")
