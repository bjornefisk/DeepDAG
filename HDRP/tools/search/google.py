import json
import os
import time
from typing import Any, Dict, List, Optional
from urllib import error, request

from .base import SearchProvider, SearchError
from .schema import SearchResponse, SearchResult
from .api_key_validator import validate_google_api_key, APIKeyError


# Google Custom Search JSON API endpoint
GOOGLE_SEARCH_URL = os.getenv(
    "GOOGLE_API_URL", "https://www.googleapis.com/customsearch/v1"
)


class GoogleSearchProvider(SearchProvider):
    """Search provider backed by Google Custom Search JSON API.

    Notes on configuration:
    - API credentials:
        * API key: Obtain from Google Cloud Console (Custom Search API)
        * CX (Custom Search Engine ID): Create at https://cse.google.com
        * Both can be passed explicitly or via environment variables
    - Latency / timeouts:
        * `timeout_seconds` is a hard client-side timeout for the HTTP request
    - Query scope:
        * Results are filtered by the Custom Search Engine configuration
        * CSE can be configured for specific sites or the entire web
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        cx: Optional[str] = None,
        timeout_seconds: float = 8.0,
        default_max_results: Optional[int] = None,
        validate_key: bool = True,
    ) -> None:
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.cx = cx or os.getenv("GOOGLE_CX")
        self.timeout_seconds = timeout_seconds
        self.validate_key = validate_key
        # Allow callers to override the conventional default
        self.default_max_results = (
            default_max_results
            if default_max_results is not None
            else self.DEFAULT_MAX_RESULTS
        )

        # Validate API credentials early if requested (default behavior)
        # This can be disabled for testing or when using health_check() separately
        if validate_key:
            try:
                validate_google_api_key(
                    self.api_key, self.cx, raise_on_invalid=True
                )
            except APIKeyError as e:
                raise SearchError(str(e)) from e

    def health_check(self) -> bool:
        """Return True if the provider appears to be correctly configured.

        Validates both API key and CX parameter presence and format.
        """
        is_valid, _ = validate_google_api_key(
            self.api_key, self.cx, raise_on_invalid=False
        )
        return is_valid

    def search(self, query: str, max_results: int = None) -> SearchResponse:
        if max_results is None:
            max_results = self.default_max_results

        safe_limit = self._validate_limit(max_results)

        # Double-check API credentials validity (only if validation is enabled)
        if self.validate_key:
            try:
                validate_google_api_key(self.api_key, self.cx, raise_on_invalid=True)
            except APIKeyError as e:
                raise SearchError(str(e)) from e

        # Build query parameters for Google Custom Search API
        params = {
            "key": self.api_key,
            "cx": self.cx,
            "q": query,
            "num": safe_limit,  # Number of results to return (max 10 per request)
        }

        # Construct URL with query parameters
        url = f"{GOOGLE_SEARCH_URL}?{'&'.join(f'{k}={request.quote(str(v))}' for k, v in params.items())}"

        req = request.Request(url, method="GET")

        start_time = time.time()

        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                status = resp.getcode()
                raw_body = resp.read().decode("utf-8")
        except error.HTTPError as e:
            raise SearchError(f"Google API HTTP error: {e.code}") from e
        except error.URLError as e:
            raise SearchError(f"Google API connection error: {e.reason}") from e
        except Exception as e:
            raise SearchError(f"Google API unexpected error: {e}") from e

        try:
            body: Dict[str, Any] = json.loads(raw_body) if raw_body else {}
        except json.JSONDecodeError as e:
            raise SearchError("Google API returned invalid JSON.") from e

        if not (200 <= status < 300):
            message = ""
            if isinstance(body, dict):
                # Google API surfaces errors in an 'error' object
                error_obj = body.get("error", {})
                if isinstance(error_obj, dict):
                    message = error_obj.get("message", "")
                else:
                    message = str(error_obj)
            raise SearchError(f"Google API returned status {status}: {message}")

        raw_results = body.get("items") or []
        results: List[SearchResult] = []

        for item in raw_results:
            if not isinstance(item, dict):
                # Skip malformed entries rather than failing the entire search
                continue

            title = item.get("title") or "Untitled result"
            url = item.get("link") or ""
            snippet = item.get("snippet") or ""

            # Extract published date from pagemap metadata if available
            published_date = None
            pagemap = item.get("pagemap", {})
            if isinstance(pagemap, dict):
                metatags = pagemap.get("metatags", [])
                if metatags and isinstance(metatags, list) and len(metatags) > 0:
                    first_meta = metatags[0]
                    if isinstance(first_meta, dict):
                        # Try common date fields
                        published_date = (
                            first_meta.get("article:published_time")
                            or first_meta.get("date")
                            or first_meta.get("pubdate")
                        )

            # Preserve provider-specific metadata for debugging/eval
            metadata: Dict[str, Any] = {
                k: v
                for k, v in item.items()
                if k not in ("title", "link", "snippet", "pagemap")
            }

            results.append(
                SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    source="google",
                    published_date=published_date,
                    metadata=metadata,
                )
            )

        latency_ms = (time.time() - start_time) * 1000.0

        # `total_found` reflects the total number of items Google returned
        total_found = len(raw_results)

        return SearchResponse(
            query=query,
            results=results[:safe_limit],
            total_found=total_found,
            latency_ms=round(latency_ms, 2),
        )
