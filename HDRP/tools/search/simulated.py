import time
import random
from typing import List

from .base import SearchProvider, SearchError
from .schema import SearchResponse, SearchResult

class SimulatedSearchProvider(SearchProvider):
    """A deterministic search provider for development, testing, and offline environments.
    
    It returns plausible-looking results based on keywords in the query, allowing 
    agents to be tested without incurring API costs or requiring internet access.
    """

    def __init__(self, latency_mean: float = 0.1):
        self.latency_mean = latency_mean

    def health_check(self) -> bool:
        return True

    def search(self, query: str, max_results: int = 5) -> SearchResponse:
        start_time = time.time()
        
        # Simulate network latency
        time.sleep(max(0.0, random.gauss(self.latency_mean, 0.05)))
        
        results = self._generate_mock_results(query, max_results)
        
        latency = (time.time() - start_time) * 1000
        return SearchResponse(
            query=query,
            results=results,
            total_found=len(results) * 100, # Simulate generic large count
            latency_ms=round(latency, 2)
        )

    def _generate_mock_results(self, query: str, limit: int) -> List[SearchResult]:
        q_lower = query.lower()
        results = []
        
        # Dynamic response generation based on intent keywords
        if "quantum" in q_lower:
            results.append(SearchResult(
                title="Quantum Computing Impact on Cryptography - Nature",
                url="https://www.nature.com/articles/s41586-023-0001",
                snippet="Shor's algorithm poses a significant threat to RSA encryption...",
                source="simulated"
            ))
            results.append(SearchResult(
                title="NIST Post-Quantum Cryptography Standardization",
                url="https://csrc.nist.gov/projects/post-quantum-cryptography",
                snippet="NIST has announced the first four quantum-resistant cryptographic algorithms...",
                source="simulated"
            ))
        elif "weather" in q_lower:
             results.append(SearchResult(
                title="Current Weather Forecast",
                url="https://weather.com/forecast",
                snippet="Today's forecast: Sunny with a high of 75F...",
                source="simulated"
            ))
        else:
            # Fallback generic results
            for i in range(limit):
                results.append(SearchResult(
                    title=f"Result {i+1} for '{query}'",
                    url=f"https://example.com/search?q={query}&id={i}",
                    snippet=f"This is a simulated search result description for the query '{query}'. It contains relevant keywords...",
                    source="simulated"
                ))

        return results[:limit]
