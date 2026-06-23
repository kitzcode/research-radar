"""Configuration loading: yaml files in config/ plus secrets from .env.

Everything that varies (model ids, contact email, source scope, feeds) is read
here so nothing is hardcoded in pipeline source.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Repo root is the parent of the radar/ package directory.
ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"
TEMPLATES_DIR = ROOT / "templates"

# Load .env once at import so os.environ has ANTHROPIC_API_KEY etc.
load_dotenv(ROOT / ".env")


def _load_yaml(name: str) -> dict:
    path = CONFIG_DIR / name
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


@lru_cache(maxsize=None)
def models() -> dict:
    return _load_yaml("models.yaml")


@lru_cache(maxsize=None)
def sources() -> dict:
    return _load_yaml("sources.yaml")


@lru_cache(maxsize=None)
def settings() -> dict:
    return _load_yaml("settings.yaml")


@lru_cache(maxsize=None)
def feeds() -> list[dict]:
    return _load_yaml("feeds.yaml").get("feeds", [])


@lru_cache(maxsize=None)
def _topics_doc() -> dict:
    return _load_yaml("topics.yaml")


def watchlist_topics() -> list[str]:
    """The saved keyword watchlist (point-of-care / IVD presets)."""
    return [t for t in _topics_doc().get("topics", []) if t and t.strip()]


def watchlist_defaults() -> dict:
    """Default lookback and per-source count for watchlist runs."""
    return _topics_doc().get("defaults", {}) or {}


def contact_email() -> str:
    """Contact address used in User-Agent and the OpenAlex mailto parameter."""
    return settings().get("contact_email", "anonymous@example.com")


def active_topic_sources() -> list[str]:
    s = sources()
    scope = s.get("scope", "all_science")
    return s.get("topic_sources", {}).get(scope, [])


def per_source_count() -> int:
    return int(sources().get("per_source_count", 8))


def anthropic_key() -> str | None:
    return os.environ.get("ANTHROPIC_API_KEY")


def springer_key() -> str | None:
    return os.environ.get("SPRINGER_API_KEY")
