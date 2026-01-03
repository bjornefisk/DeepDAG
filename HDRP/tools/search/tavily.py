import json
import os
import time
from typing import Any, Dict, List, Optional
from urllib import error, request

from .base import SearchProvider, SearchError
from .schema import SearchResponse, SearchResult


# Default Tavily HTTP endpoint; can be overridden for testing.
TAVILY_SEARCH_URL = os.getenv("TAVILY_API_URL", "https://api.tavily.com/search")


class TavilySearchProvider(SearchProvider):
    """Search provider backed by the Tavily web search API.

    Notes on configuration:
    - API key:
        * Preferred: pass explicitly via the constructor.
        * Fallback: read from the TAVILY_API_KEY environment variable.
    - Latency / timeouts:
        * `timeout_seconds` is a hard client-side timeout for the HTTP request.
    - Query scope:
        * `search_depth` controls how aggressively Tavily explores the web
          (typically \"basic\" or \"advanced\").
        * `topic` can be used to bias results towards \"general\" web search,
          \"news\", etc., depending on Tavily's configuration.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        search_depth: str = "basic",
        topic: str = "general",
        timeout_seconds: float = 8.0,
        default_max_results: Optional[int] = None,
    ) -> None:
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        self.search_depth = search_depth
        self.topic = topic
        self.timeout_seconds = timeout_seconds
        # Allow callers to override the conventional default.
        self.default_max_results = (
            default_max_results
            if default_max_results is not None
            else self.DEFAULT_MAX_RESULTS
        )

    def health_check(self) -> bool:
        """Return True if the provider appears to be correctly configured.

        For now we only validate local configuration (e.g., API key presence)
        to avoid introducing external dependencies into health checks.
        """
        return bool(self.api_key)

    def search(self, query: str, max_results: int = None) -> SearchResponse:
        if max_results is None:
            max_results = self.default_max_results

        safe_limit = self._validate_limit(max_results)

        if not self.api_key:
            raise SearchError(
                "TavilySearchProvider is misconfigured: missing API key. "
                "Set TAVILY_API_KEY or pass api_key explicitly."
            )

        payload: Dict[str, Any] = {
            # API key is passed in the JSON body per Tavily's public HTTP interface.
            "api_key": self.api_key,
            "query": query,
            "search_depth": self.search_depth,
            "topic": self.topic,
            "max_results": safe_limit,
            # We only need raw sources; the agent synthesizes answers separately.
            "include_answer": False,
        }

        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}

        req = request.Request(
            TAVILY_SEARCH_URL,
            data=data,
            headers=headers,
            method="POST",
        )

        start_time = time.time()

        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                status = resp.getcode()
                raw_body = resp.read().decode("utf-8")
        except error.HTTPError as e:
            raise SearchError(f"Tavily HTTP error: {e.code}") from e
        except error.URLError as e:
            raise SearchError(f"Tavily connection error: {e.reason}") from e
        except Exception as e:
            raise SearchError(f"Tavily unexpected error: {e}") from e

        try:
            body: Dict[str, Any] = json.loads(raw_body) if raw_body else {}
        except json.JSONDecodeError as e:
            raise SearchError("Tavily returned invalid JSON.") from e

        if not (200 <= status < 300):
            message = ""
            if isinstance(body, dict):
                # Many APIs surface an error string or object; best-effort here.
                message = str(body.get("error") or body.get("message") or "")
            raise SearchError(f"Tavily API returned status {status}: {message}")

        raw_results = body.get("results") or []
        results: List[SearchResult] = []

        for item in raw_results:
            if not isinstance(item, dict):
                # Skip malformed entries rather than failing the entire search.
                continue

            title = item.get("title") or "Untitled result"
            url = item.get("url") or ""
            snippet = item.get("content") or item.get("snippet") or ""
            published_date = item.get("published_date")

            # Preserve provider-specific metadata for debugging/eval.
            metadata: Dict[str, Any] = {
                k: v
                for k, v in item.items()
                if k
                not in (
                    "title",
                    "url",
                    "content",
                    "snippet",
                    "published_date",
                )
            }

            results.append(
                SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    source="tavily",
                    published_date=published_date,
                    metadata=metadata,
                )
            )

        latency_ms = (time.time() - start_time) * 1000.0

        # `total_found` reflects the total number of items Tavily returned before
        # our own post-processing / clamping.
        total_found = len(raw_results)

        return SearchResponse(
            query=query,
            results=results[:safe_limit],
            total_found=total_found,
            latency_ms=round(latency_ms, 2),
        )


