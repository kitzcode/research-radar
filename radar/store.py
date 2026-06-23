"""Persistence: output item assembly, drafts JSON, markdown archive, seen.json.

Item dicts are assembled here from structured Paper fields and the deterministic
helpers in citations.py. Raw abstracts are kept in the local drafts JSON (under
data/, gitignored) for your own reading and are never written into docs/.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from . import citations, config
from .normalize import Paper

log = logging.getLogger("radar.store")

DRAFTS_DIR = config.DATA_DIR / "drafts"
ARCHIVE_DIR = config.DATA_DIR / "archive"
SEEN_PATH = config.DATA_DIR / "seen.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s or "untitled"


def item_dict(p: Paper, include_abstract: bool = False) -> dict:
    """Assemble one public output item from structured fields.

    The public site uses include_abstract=False. Local drafts pass True so the
    raw abstract is retained alongside the summary for provenance and reading.
    """
    p = citations.finalize(p)
    out = {
        "title": p.title,
        "summary": p.summary,                       # None when abstract unavailable
        "why_notable": p.why_notable,
        "authors": p.authors,
        "venue": p.venue,
        "published": p.published,
        "doi": p.doi,
        "arxiv_id": p.arxiv_id,
        "url": citations.canonical_url(p),
        "citation": citations.citation_line(p),
        "source_api": p.source_api,
        "is_preprint": p.is_preprint,
        "is_commentary": p.is_commentary,
        "abstract_available": p.abstract is not None,
    }
    if include_abstract:
        # Local-only fields for your own reading and provenance tracing.
        out["_abstract"] = p.abstract
        out["_relevance_reason"] = p.relevance_reason
        out["_raw"] = p.raw
    return out


def build_run(mode: str, query: str | None, papers: list[Paper],
              for_public: bool = True) -> dict:
    """Build the run object (the output JSON schema in the spec)."""
    items = [item_dict(p, include_abstract=not for_public) for p in papers]
    run = {
        "mode": mode,
        "query": query,
        "generated_at": now_iso(),
        "count": len(items),
        "items": items,
    }
    return run


def write_drafts(run: dict, slug: str) -> Path:
    """Write the local drafts JSON (keeps raw abstracts for your own reading)."""
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    date = run["generated_at"][:10]
    path = DRAFTS_DIR / f"{run['mode']}_{slug}_{date}.json"
    with path.open("w", encoding="utf-8") as fh:
        json.dump(run, fh, indent=2, ensure_ascii=False)
    log.info("wrote drafts %s", path)
    return path


def append_archive(run: dict, slug: str) -> Path:
    """Append a human-readable markdown record of the run."""
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    date = run["generated_at"][:10]
    path = ARCHIVE_DIR / f"{run['mode']}_{slug}_{date}.md"
    lines = []
    header = run.get("query") or "Big stories"
    lines.append(f"# {run['mode'].title()}: {header}")
    lines.append("")
    lines.append(f"Generated {run['generated_at']}. {run['count']} items.")
    lines.append("")
    for it in run["items"]:
        lines.append(f"## {it['title']}")
        lines.append("")
        lines.append(f"{it['citation']}")
        if it.get("is_preprint"):
            lines.append("")
            lines.append("(preprint)")
        lines.append("")
        if it.get("summary"):
            lines.append(it["summary"])
        else:
            lines.append("_Abstract unavailable._")
        if it.get("why_notable"):
            lines.append("")
            lines.append(f"Why it is getting attention: {it['why_notable']}")
        lines.append("")
        lines.append(f"Link: {it['url']}")
        lines.append("")
    with path.open("w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    log.info("wrote archive %s", path)
    return path


# ---------------------------------------------------------------------------
# seen.json dedupe for big-story mode.
# ---------------------------------------------------------------------------

def load_seen() -> set[str]:
    if not SEEN_PATH.exists():
        return set()
    try:
        with SEEN_PATH.open("r", encoding="utf-8") as fh:
            return set(json.load(fh))
    except (ValueError, OSError) as exc:
        log.warning("could not read seen.json: %s", exc)
        return set()


def save_seen(keys: set[str]) -> None:
    SEEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SEEN_PATH.open("w", encoding="utf-8") as fh:
        json.dump(sorted(keys), fh, indent=2)


def seen_key_for(doi: str | None, link: str | None) -> str | None:
    if doi:
        return f"doi:{doi.lower()}"
    if link:
        return f"url:{link}"
    return None


# ---------------------------------------------------------------------------
# Public run history. Drives the static site. Holds public items only (no raw
# abstracts), so it is safe to commit alongside docs/.
# ---------------------------------------------------------------------------

PUBLIC_RUNS_PATH = config.DATA_DIR / "public_runs.json"
MAX_PUBLIC_RUNS = 25


def load_public_runs() -> list[dict]:
    if not PUBLIC_RUNS_PATH.exists():
        return []
    try:
        with PUBLIC_RUNS_PATH.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (ValueError, OSError) as exc:
        log.warning("could not read public_runs.json: %s", exc)
        return []


def append_public_run(run_public: dict) -> list[dict]:
    """Prepend a public run, cap history, persist, and return the full list."""
    runs = load_public_runs()
    runs.insert(0, run_public)
    runs = runs[:MAX_PUBLIC_RUNS]
    PUBLIC_RUNS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PUBLIC_RUNS_PATH.open("w", encoding="utf-8") as fh:
        json.dump(runs, fh, indent=2, ensure_ascii=False)
    return runs
