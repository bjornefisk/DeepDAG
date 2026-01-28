from __future__ import annotations

import os
from typing import Dict, Optional

import requests


class NLIHttpClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("HDRP_NLI_HTTP_URL", "http://localhost:8000")).rstrip("/")
        self.timeout_seconds = float(
            timeout_seconds or os.getenv("HDRP_NLI_HTTP_TIMEOUT_SECONDS", "10")
        )

    def compute_relation(
        self,
        premise: str,
        hypothesis: str,
        variant: Optional[str] = None,
    ) -> Dict[str, float]:
        headers = {}
        if variant:
            headers["X-Model-Variant"] = variant

        response = requests.post(
            f"{self.base_url}/relation",
            json={"premise": premise, "hypothesis": hypothesis},
            headers=headers,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        return {
            "entailment": float(data["entailment"]),
            "contradiction": float(data["contradiction"]),
            "neutral": float(data["neutral"]),
        }
