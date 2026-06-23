"""Thin wrapper over the Anthropic SDK for triage and summarize calls.

The model writes prose only. Callers pass it title and abstract text and nothing
else (no URLs, DOIs, author lists), so it has nothing to copy a fake citation
from. Model ids and token limits come from config/models.yaml.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

from . import config

log = logging.getLogger("radar.llm")


@lru_cache(maxsize=1)
def _client():
    # Imported lazily so the data pipeline and tests can run without the SDK or a
    # key present. Raises a clear error only when an actual call is attempted.
    from anthropic import Anthropic

    if not config.anthropic_key():
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Export it (or put it in .env) before "
            "running triage or summarize. The data pipeline runs without it."
        )
    return Anthropic()


def call(model: str, system: str, user: str, max_tokens: int) -> str:
    """One messages.create call. Returns joined text blocks, stripped."""
    resp = _client().messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(
        b.text for b in resp.content if getattr(b, "type", None) == "text"
    ).strip()


def triage_model() -> str:
    return config.models().get("triage_model", "claude-haiku-4-5-20251001")


def summary_model() -> str:
    return config.models().get("summary_model", "claude-sonnet-4-6")


def max_tokens_triage() -> int:
    return int(config.models().get("max_tokens_triage", 200))


def max_tokens_summary() -> int:
    return int(config.models().get("max_tokens_summary", 600))
