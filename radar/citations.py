"""Deterministic citation and link assembly. No model involvement.

Every identifier, URL, and citation string here is built only from structured
fields that a source API returned. Missing pieces are omitted, never guessed.
DOI validation against Crossref is the single gate for any DOI that did not come
straight from a structured search result.
"""
from __future__ import annotations

import logging
import re

from .normalize import Paper

log = logging.getLogger("radar.citations")

# Case-insensitive DOI pattern. Used both to extract candidates from free text
# and, in summarize.py, as a backstop to reject summaries that leak a DOI.
DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)


def extract_doi_candidates(text: str) -> list[str]:
    """Pull every DOI-shaped substring from free text. Candidates only.

    A candidate is never trusted until validate_doi confirms it against Crossref.
    """
    if not text:
        return []
    # Strip common trailing punctuation that regularly clings to a scraped DOI.
    out = []
    for m in DOI_RE.findall(text):
        out.append(m.rstrip(".,);]>\"'"))
    # Preserve order, drop duplicates.
    seen: set[str] = set()
    uniq = []
    for d in out:
        k = d.lower()
        if k not in seen:
            seen.add(k)
            uniq.append(d)
    return uniq


def canonical_url(p: Paper) -> str:
    """Preferred outbound link, built from structured fields only."""
    if p.doi:
        return f"https://doi.org/{p.doi}"
    if p.arxiv_id:
        return f"https://arxiv.org/abs/{p.arxiv_id}"
    return p.source_url


def citation_line(p: Paper) -> str:
    """A human-readable citation assembled from structured fields.

    Any missing piece is omitted, never guessed.
    """
    authors = ""
    if p.authors:
        authors = ", ".join(p.authors[:3]) + (" et al." if len(p.authors) > 3 else "")
    year = (p.published or "")[:4]
    bits = [b for b in [authors, p.title, p.venue, year] if b]
    return ". ".join(bits)


def validate_doi(doi: str, http) -> bool:
    """A DOI is confirmed real only if Crossref returns a record for it exactly.

    Used for any DOI that did not come straight from a structured search API,
    for example a DOI regex-extracted from a news feed.
    """
    if not doi:
        return False
    data = http.get_json(f"https://api.crossref.org/works/{doi}")
    if not data:
        return False
    returned = data.get("message", {}).get("DOI", "")
    return returned.lower() == doi.lower()


def finalize(p: Paper) -> Paper:
    """Set the canonical source_url from structured fields just before output."""
    p.source_url = canonical_url(p)
    return p
