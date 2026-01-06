import json
import os
import time
from typing import Any, Dict, List, Optional
from urllib import error, request

from .base import SearchProvider, SearchError
from .schema import SearchResponse, SearchResult
from .api_key_validator import validate_bing_api_key, APIKeyError


# Bing Web Search API v7 endpoint
BING_SEARCH_URL = os.getenv(
    "BING_API_URL", "https://api.bing.microsoft.com/v7.0/search"
)


class BingSearchProvider(SearchProvider):
    """Search provider backed by Bing Web Search API v7.

    Notes on configuration:
    - API key:
        * Obtain from Azure Portal (Cognitive Services - Bing Search)
        * Can be passed explicitly or via BING_API_KEY environment variable
        * Passed via 'Ocp-Apim-Subscription-Key' header (Azure standard)
    - Latency / timeouts:
        * `timeout_seconds` is a hard client-side timeout for the HTTP request
    - Query scope:
        * `market` controls the market/language (e.g., "en-US", "en-GB", "fr-FR")
        * Results are from Bing's global web index
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        market: str = "en-US",
        timeout_seconds: float = 8.0,
        default_max_results: Optional[int] = None,
        validate_key: bool = True,
    ) -> None:
        self.api_key = api_key or os.getenv("BING_API_KEY")
        self.market = market
        self.timeout_seconds = timeout_seconds
        self.validate_key = validate_key
        # Allow callers to override the conventional default
        self.default_max_results = (
            default_max_results
            if default_max_results is not None
            else self.DEFAULT_MAX_RESULTS
        )

        # Validate API key early if requested (default behavior)
        # This can be disabled for testing or when using health_check() separately
        if validate_key:
            try:
                validate_bing_api_key(self.api_key, raise_on_invalid=True)
            except APIKeyError as e:
                raise SearchError(str(e)) from e

    def health_check(self) -> bool:
        """Return True if the provider appears to be correctly configured.

        Validates API key presence and format.
        """
        is_valid, _ = validate_bing_api_key(
            self.api_key, raise_on_invalid=False
        )
        return is_valid

    def search(self, query: str, max_results: int = None) -> SearchResponse:
        if max_results is None:
            max_results = self.default_max_results

        safe_limit = self._validate_limit(max_results)

        # Double-check API key validity (only if validation is enabled)
        if self.validate_key:
            try:
                validate_bing_api_key(self.api_key, raise_on_invalid=True)
            except APIKeyError as e:
                raise SearchError(str(e)) from e

        # Build query parameters for Bing Web Search API
        params = {
            "q": query,
            "count": safe_limit,  # Number of results to return
            "mkt": self.market,  # Market code
            "textDecorations": "false",  # Disable HTML formatting in snippets
            "textFormat": "Raw",  # Return plain text
        }

        # Construct URL with query parameters
        url = f"{BING_SEARCH_URL}?{'&'.join(f'{k}={request.quote(str(v))}' for k, v in params.items())}"

        # Bing requires API key in header
        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key,
        }

        req = request.Request(url, headers=headers, method="GET")

        start_time = time.time()

        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                status = resp.getcode()
                raw_body = resp.read().decode("utf-8")
        except error.HTTPError as e:
            raise SearchError(f"Bing API HTTP error: {e.code}") from e
        except error.URLError as e:
            raise SearchError(f"Bing API connection error: {e.reason}") from e
        except Exception as e:
            raise SearchError(f"Bing API unexpected error: {e}") from e

        try:
            body: Dict[str, Any] = json.loads(raw_body) if raw_body else {}
        except json.JSONDecodeError as e:
            raise SearchError("Bing API returned invalid JSON.") from e

        if not (200 <= status < 300):
            message = ""
            if isinstance(body, dict):
                # Bing API surfaces errors in an 'error' object
                error_obj = body.get("error", {})
                if isinstance(error_obj, dict):
                    message = error_obj.get("message", "")
                else:
                    message = str(error_obj)
            raise SearchError(f"Bing API returned status {status}: {message}")

        # Bing returns results in 'webPages.value' array
        web_pages = body.get("webPages", {})
        raw_results = web_pages.get("value") if isinstance(web_pages, dict) else []
        if raw_results is None:
            raw_results = []

        results: List[SearchResult] = []

        for item in raw_results:
            if not isinstance(item, dict):
                # Skip malformed entries rather than failing the entire search
                continue

            title = item.get("name") or "Untitled result"
            url = item.get("url") or ""
            snippet = item.get("snippet") or ""
            published_date = item.get("datePublished")

            # Preserve provider-specific metadata for debugging/eval
            metadata: Dict[str, Any] = {
                k: v
                for k, v in item.items()
                if k not in ("name", "url", "snippet", "datePublished")
            }

            results.append(
                SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    source="bing",
                    published_date=published_date,
                    metadata=metadata,
                )
            )

        latency_ms = (time.time() - start_time) * 1000.0

        # `total_found` reflects the total number of items Bing returned
        total_found = len(raw_results)

        return SearchResponse(
            query=query,
            results=results[:safe_limit],
            total_found=total_found,
            latency_ms=round(latency_ms, 2),
        )
