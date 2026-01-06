"""API Key Validation Utilities

Centralized validation for API keys with helpful, actionable error messages.
"""

import os
from typing import Optional, Tuple


class APIKeyError(Exception):
    """Raised when API key validation fails.
    
    This exception includes helpful setup instructions to guide users
    toward resolving the configuration issue.
    """
    pass


def validate_tavily_api_key(
    api_key: Optional[str] = None,
    raise_on_invalid: bool = True,
) -> Tuple[bool, Optional[str]]:
    """Validate a Tavily API key.
    
    Args:
        api_key: The API key to validate. If None, checks TAVILY_API_KEY env var.
        raise_on_invalid: If True, raises APIKeyError on validation failure.
                         If False, returns (False, error_message) instead.
    
    Returns:
        Tuple of (is_valid, error_message). error_message is None if valid.
    
    Raises:
        APIKeyError: If raise_on_invalid=True and validation fails.
    """
    # Get the effective API key
    effective_key = api_key or os.getenv("TAVILY_API_KEY")
    
    # Check if key is missing
    if not effective_key:
        error_msg = _get_missing_key_error()
        if raise_on_invalid:
            raise APIKeyError(error_msg)
        return False, error_msg
    
    # Check if key is just whitespace
    if not effective_key.strip():
        error_msg = _get_empty_key_error()
        if raise_on_invalid:
            raise APIKeyError(error_msg)
        return False, error_msg
    
    # Check for common placeholder values
    placeholder_values = {
        "your-api-key",
        "your-tavily-api-key",
        "your-key",
        "your-key-here",
        "tvly-your-key",
        "test-key",
    }
    if effective_key.lower() in placeholder_values:
        error_msg = _get_placeholder_key_error(effective_key)
        if raise_on_invalid:
            raise APIKeyError(error_msg)
        return False, error_msg
    
    # Basic format validation (Tavily keys typically start with "tvly-")
    # This is a soft check - we don't want to be too strict in case format changes
    if len(effective_key) < 10:
        error_msg = _get_invalid_format_error(effective_key)
        if raise_on_invalid:
            raise APIKeyError(error_msg)
        return False, error_msg
    
    return True, None


def _get_missing_key_error() -> str:
    """Generate error message for missing API key."""
    return """Tavily API key not configured.

To use Tavily search, you need to set your API key:

  1. Get an API key from https://tavily.com
  
  2. Set the environment variable:
     
     export TAVILY_API_KEY="tvly-your-actual-key"
  
  3. Or pass it explicitly via CLI:
     
     --api-key "tvly-your-actual-key"

Alternatively, use the simulated provider for testing:
  
  --provider simulated
"""


def _get_empty_key_error() -> str:
    """Generate error message for empty API key."""
    return """Tavily API key is empty.

The TAVILY_API_KEY environment variable is set but contains only whitespace.

To fix this:

  1. Get a valid API key from https://tavily.com
  
  2. Set the environment variable with a valid key:
     
     export TAVILY_API_KEY="tvly-your-actual-key"

Alternatively, use the simulated provider for testing:
  
  --provider simulated
"""


def _get_placeholder_key_error(placeholder: str) -> str:
    """Generate error message for placeholder API key."""
    return f"""Tavily API key appears to be a placeholder: "{placeholder}"

You need to replace this with your actual API key from Tavily.

To fix this:

  1. Get your actual API key from https://tavily.com
  
  2. Replace the placeholder with your real key:
     
     export TAVILY_API_KEY="tvly-your-actual-key"

Alternatively, use the simulated provider for testing:
  
  --provider simulated
"""


def _get_invalid_format_error(key: str) -> str:
    """Generate error message for invalid API key format."""
    # Mask the key for security (show first 4 chars only)
    masked_key = key[:4] + "..." if len(key) > 4 else "***"
    
    return f"""Tavily API key appears to be invalid: "{masked_key}"

The provided API key is too short or has an unexpected format.

To fix this:

  1. Verify you have the correct API key from https://tavily.com
  
  2. Ensure you're using the full key (Tavily keys typically start with "tvly-"):
     
     export TAVILY_API_KEY="tvly-your-actual-key"

Alternatively, use the simulated provider for testing:
  
  --provider simulated
"""


def get_setup_instructions() -> str:
    """Get general setup instructions for Tavily API key.
    
    Returns:
        Formatted setup instructions as a string.
    """
    return """Tavily API Key Setup Instructions:

1. Sign up for a Tavily account at https://tavily.com

2. Get your API key from the Tavily dashboard

3. Set the environment variable:
   
   # For bash/zsh (add to ~/.bashrc or ~/.zshrc for persistence)
   export TAVILY_API_KEY="tvly-your-actual-key"
   
   # For fish shell
   set -x TAVILY_API_KEY "tvly-your-actual-key"

4. Verify the key is set:
   
   echo $TAVILY_API_KEY

5. Run your HDRP command with Tavily provider:
   
   python -m HDRP.cli run --query "your question" --provider tavily

For testing without an API key, use the simulated provider:
   
   python -m HDRP.cli run --query "your question" --provider simulated
"""


def validate_google_api_key(
    api_key: Optional[str] = None,
    cx: Optional[str] = None,
    raise_on_invalid: bool = True,
) -> Tuple[bool, Optional[str]]:
    """Validate Google Custom Search API credentials.
    
    Args:
        api_key: The API key to validate. If None, checks GOOGLE_API_KEY env var.
        cx: The Custom Search Engine ID. If None, checks GOOGLE_CX env var.
        raise_on_invalid: If True, raises APIKeyError on validation failure.
                         If False, returns (False, error_message) instead.
    
    Returns:
        Tuple of (is_valid, error_message). error_message is None if valid.
    
    Raises:
        APIKeyError: If raise_on_invalid=True and validation fails.
    """
    # Get the effective credentials
    effective_key = api_key or os.getenv("GOOGLE_API_KEY")
    effective_cx = cx or os.getenv("GOOGLE_CX")
    
    # Check if API key is missing
    if not effective_key:
        error_msg = _get_google_missing_key_error()
        if raise_on_invalid:
            raise APIKeyError(error_msg)
        return False, error_msg
    
    # Check if CX is missing
    if not effective_cx:
        error_msg = _get_google_missing_cx_error()
        if raise_on_invalid:
            raise APIKeyError(error_msg)
        return False, error_msg
    
    # Check if key is just whitespace
    if not effective_key.strip():
        error_msg = _get_google_empty_key_error()
        if raise_on_invalid:
            raise APIKeyError(error_msg)
        return False, error_msg
    
    # Check if CX is just whitespace
    if not effective_cx.strip():
        error_msg = _get_google_empty_cx_error()
        if raise_on_invalid:
            raise APIKeyError(error_msg)
        return False, error_msg
    
    # Check for common placeholder values in API key
    placeholder_values = {
        "your-api-key",
        "your-google-api-key",
        "your-key",
        "your-key-here",
    }
    if effective_key.lower() in placeholder_values:
        error_msg = _get_google_placeholder_key_error(effective_key)
        if raise_on_invalid:
            raise APIKeyError(error_msg)
        return False, error_msg
    
    # Check for common placeholder values in CX
    cx_placeholders = {
        "your-cx",
        "your-search-engine-id",
        "your-cse-id",
    }
    if effective_cx.lower() in cx_placeholders:
        error_msg = _get_google_placeholder_cx_error(effective_cx)
        if raise_on_invalid:
            raise APIKeyError(error_msg)
        return False, error_msg
    
    # Basic format validation
    if len(effective_key) < 20:
        error_msg = _get_google_invalid_format_error(effective_key)
        if raise_on_invalid:
            raise APIKeyError(error_msg)
        return False, error_msg
    
    return True, None


def _get_google_missing_key_error() -> str:
    """Generate error message for missing Google API key."""
    return """Google API key not configured.

To use Google Custom Search, you need to set your API key:

  1. Get an API key from Google Cloud Console:
     https://console.cloud.google.com/apis/credentials
     
     Enable the "Custom Search API" for your project.
  
  2. Set the environment variable:
     
     export GOOGLE_API_KEY="your-actual-api-key"
  
  3. You also need a Custom Search Engine ID (see GOOGLE_CX error).

Alternatively, use the simulated provider for testing:
  
  --provider simulated
"""


def _get_google_missing_cx_error() -> str:
    """Generate error message for missing Google CX."""
    return """Google Custom Search Engine ID (CX) not configured.

To use Google Custom Search, you need both an API key AND a CX:

  1. Create a Custom Search Engine at:
     https://cse.google.com/cse/create/new
  
  2. Get your Search Engine ID (CX) from the control panel.
  
  3. Set the environment variable:
     
     export GOOGLE_CX="your-search-engine-id"

Alternatively, use the simulated provider for testing:
  
  --provider simulated
"""


def _get_google_empty_key_error() -> str:
    """Generate error message for empty Google API key."""
    return """Google API key is empty.

The GOOGLE_API_KEY environment variable is set but contains only whitespace.

To fix this:

  1. Get a valid API key from Google Cloud Console:
     https://console.cloud.google.com/apis/credentials
  
  2. Set the environment variable with a valid key:
     
     export GOOGLE_API_KEY="your-actual-api-key"

Alternatively, use the simulated provider for testing:
  
  --provider simulated
"""


def _get_google_empty_cx_error() -> str:
    """Generate error message for empty Google CX."""
    return """Google Custom Search Engine ID (CX) is empty.

The GOOGLE_CX environment variable is set but contains only whitespace.

To fix this:

  1. Get your Search Engine ID from:
     https://cse.google.com/cse/all
  
  2. Set the environment variable with a valid CX:
     
     export GOOGLE_CX="your-search-engine-id"

Alternatively, use the simulated provider for testing:
  
  --provider simulated
"""


def _get_google_placeholder_key_error(placeholder: str) -> str:
    """Generate error message for placeholder Google API key."""
    return f"""Google API key appears to be a placeholder: "{placeholder}"

You need to replace this with your actual API key from Google Cloud Console.

To fix this:

  1. Get your actual API key from:
     https://console.cloud.google.com/apis/credentials
  
  2. Replace the placeholder with your real key:
     
     export GOOGLE_API_KEY="your-actual-api-key"

Alternatively, use the simulated provider for testing:
  
  --provider simulated
"""


def _get_google_placeholder_cx_error(placeholder: str) -> str:
    """Generate error message for placeholder Google CX."""
    return f"""Google Custom Search Engine ID appears to be a placeholder: "{placeholder}"

You need to replace this with your actual Search Engine ID.

To fix this:

  1. Get your actual CX from:
     https://cse.google.com/cse/all
  
  2. Replace the placeholder with your real CX:
     
     export GOOGLE_CX="your-search-engine-id"

Alternatively, use the simulated provider for testing:
  
  --provider simulated
"""


def _get_google_invalid_format_error(key: str) -> str:
    """Generate error message for invalid Google API key format."""
    masked_key = key[:4] + "..." if len(key) > 4 else "***"
    
    return f"""Google API key appears to be invalid: "{masked_key}"

The provided API key is too short or has an unexpected format.

To fix this:

  1. Verify you have the correct API key from:
     https://console.cloud.google.com/apis/credentials
  
  2. Ensure you're using the full key:
     
     export GOOGLE_API_KEY="your-actual-api-key"

Alternatively, use the simulated provider for testing:
  
  --provider simulated
"""
