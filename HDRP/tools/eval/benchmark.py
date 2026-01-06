import argparse
import os
import sys
from typing import Optional

from HDRP.tools.eval.react_agent import ReActAgent
from HDRP.tools.search import SearchFactory, SearchProvider
from HDRP.tools.search.base import SearchError
from HDRP.tools.search.api_key_validator import APIKeyError


def _build_search_provider(explicit_provider: Optional[str]) -> SearchProvider:
    """Select and configure a SearchProvider based on CLI flags and env.

    Precedence:
        1. CLI flag --search-provider
        2. HDRP_SEARCH_PROVIDER environment variable
        3. Hard-coded default of \"simulated\"
    """
    if explicit_provider is not None:
        provider_type = explicit_provider.lower()
    else:
        provider_type = os.getenv("HDRP_SEARCH_PROVIDER", "simulated").lower()

    if provider_type == "tavily":
        api_key = os.getenv("TAVILY_API_KEY")
        search_depth = os.getenv("TAVILY_SEARCH_DEPTH", "basic")
        topic = os.getenv("TAVILY_TOPIC", "general")

        timeout_env = os.getenv("TAVILY_TIMEOUT_SECONDS", "")
        max_results_env = os.getenv("TAVILY_MAX_RESULTS", "")

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

        # If Tavily is misconfigured, fall back to the simulated provider while
        # emitting a human-readable warning.
        try:
            if not provider.health_check():
                print(
                    "[benchmark] Tavily is misconfigured (missing or invalid API key); "
                    "falling back to simulated provider."
                )
                return SearchFactory.get_provider("simulated")
        except Exception:
            print(
                "[benchmark] Tavily health check failed; falling back to simulated "
                "provider."
            )
            return SearchFactory.get_provider("simulated")

        return provider

    # Default: deterministic local provider.
    return SearchFactory.get_provider("simulated")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run a single ReActAgent episode against a chosen search provider. "
            "This is a lightweight benchmarking / manual sanity-check tool."
        )
    )
    parser.add_argument(
        "--search-provider",
        choices=["simulated", "tavily"],
        default=None,
        help=(
            "Which search provider to use. If omitted, falls back to the "
            "HDRP_SEARCH_PROVIDER environment variable or 'simulated'."
        ),
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=None,
        help=(
            "Maximum number of search results to request. If omitted, uses "
            "SearchProvider.DEFAULT_MAX_RESULTS."
        ),
    )
    parser.add_argument(
        "--question",
        required=True,
        help="Natural-language question to pass to the ReActAgent.",
    )

    args = parser.parse_args()

    try:
        provider = _build_search_provider(args.search_provider)
    except (SearchError, APIKeyError) as e:
        print(f"\n[ERROR] Failed to initialize search provider:\n", file=sys.stderr)
        print(str(e), file=sys.stderr)
        print("\nTip: Use --search-provider simulated for testing without an API key.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)

    max_results = (
        args.max_results
        if args.max_results is not None
        else provider.DEFAULT_MAX_RESULTS
    )

    agent = ReActAgent(search_provider=provider, max_results=max_results)
    result = agent.run(args.question)

    # Print the final answer to stdout for quick inspection.
    print(result.final_answer)


if __name__ == "__main__":
    main()


