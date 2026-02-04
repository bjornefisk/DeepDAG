import argparse
import sys

from HDRP.tools.eval.react_agent import ReActAgent
from HDRP.tools.search import SearchProvider
from HDRP.tools.search.base import SearchError
from HDRP.tools.search.api_key_validator import APIKeyError
from HDRP.services.shared.pipeline_runner import build_search_provider



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
        provider = build_search_provider(args.search_provider)
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


