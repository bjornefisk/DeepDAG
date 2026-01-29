#!/usr/bin/env python3
"""FastAPI NLI server with singleton model loading and metrics."""

from __future__ import annotations

import logging
import os
import time
from typing import Dict

from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field
from prometheus_client import (
    Counter,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
)

from HDRP.services.critic.nli_verifier import NLIVerifier

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="HDRP NLI Service", version="1.0.0")

METRICS_REGISTRY = CollectorRegistry()
REQUEST_COUNT = Counter(
    "hdrp_nli_http_requests_total",
    "Total NLI HTTP requests",
    ["endpoint", "status", "variant"],
    registry=METRICS_REGISTRY,
)
REQUEST_LATENCY = Histogram(
    "hdrp_nli_http_latency_seconds",
    "NLI HTTP request latency in seconds",
    ["endpoint", "variant"],
    registry=METRICS_REGISTRY,
)


class RelationRequest(BaseModel):
    premise: str = Field(..., min_length=1)
    hypothesis: str = Field(..., min_length=1)


class RelationResponse(BaseModel):
    entailment: float
    contradiction: float
    neutral: float
    variant: str


def _parse_variants() -> Dict[str, str]:
    raw_variants = os.getenv("HDRP_NLI_VARIANTS", "").strip()
    default_model_name = os.getenv(
        "HDRP_NLI_MODEL_NAME", "cross-encoder/nli-deberta-v3-base"
    )

    if not raw_variants:
        return {"control": default_model_name}

    variants: Dict[str, str] = {}
    for entry in raw_variants.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if "=" not in entry:
            raise ValueError(
                "HDRP_NLI_VARIANTS must be comma-separated name=model entries"
            )
        name, model = entry.split("=", 1)
        name = name.strip()
        model = model.strip()
        if not name or not model:
            raise ValueError(
                "HDRP_NLI_VARIANTS entries must include non-empty name and model"
            )
        variants[name] = model

    if not variants:
        variants = {"control": default_model_name}
    return variants


VARIANTS = _parse_variants()
DEFAULT_VARIANT = os.getenv("HDRP_NLI_VARIANT_DEFAULT", next(iter(VARIANTS)))
VERIFIERS: Dict[str, NLIVerifier] = {}


@app.on_event("startup")
def _load_models() -> None:
    for name, model_name in VARIANTS.items():
        logger.info("Initializing NLI model variant '%s'", name)
        verifier = NLIVerifier(model_name=model_name)
        verifier._ensure_model_loaded()
        VERIFIERS[name] = verifier
    logger.info("Loaded %d NLI variants", len(VERIFIERS))


@app.get("/health")
def health() -> Dict[str, object]:
    return {"status": "ok", "variants": sorted(VERIFIERS.keys())}


@app.get("/metrics")
def metrics() -> Response:
    return Response(
        generate_latest(METRICS_REGISTRY), media_type=CONTENT_TYPE_LATEST
    )


@app.post("/relation", response_model=RelationResponse)
def relation(payload: RelationRequest, request: Request) -> RelationResponse:
    variant = request.headers.get("X-Model-Variant") or DEFAULT_VARIANT
    if variant not in VERIFIERS:
        raise HTTPException(status_code=400, detail=f"Unknown model variant '{variant}'")

    start_time = time.time()
    status = "success"
    try:
        relation_scores = VERIFIERS[variant].compute_relation(
            premise=payload.premise, hypothesis=payload.hypothesis
        )
        return RelationResponse(
            entailment=relation_scores["entailment"],
            contradiction=relation_scores["contradiction"],
            neutral=relation_scores["neutral"],
            variant=variant,
        )
    except Exception as exc:
        status = "error"
        logger.exception("NLI inference failed for variant '%s'", variant)
        raise HTTPException(status_code=500, detail="NLI inference failed") from exc
    finally:
        duration = time.time() - start_time
        REQUEST_LATENCY.labels(endpoint="relation", variant=variant).observe(duration)
        REQUEST_COUNT.labels(endpoint="relation", status=status, variant=variant).inc()


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HDRP_NLI_HTTP_HOST", "0.0.0.0")
    port = int(os.getenv("HDRP_NLI_HTTP_PORT", "8000"))
    uvicorn.run("HDRP.services.critic.fastapi_server:app", host=host, port=port)
