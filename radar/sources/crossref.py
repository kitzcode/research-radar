"""Crossref adapter. Re-exports validate_doi and resolves a single DOI to a Paper.

Used for DOI validation (re-exported validate_doi) and for fetch_by_doi, which
builds one Paper from the Crossref /works/<doi> record. Crossref abstracts are
JATS XML, so tags are stripped before clean_abstract runs.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from ..citations import validate_doi  # noqa: F401  re-exported per contract
from ..normalize import Paper, clean_abstract

log = logging.getLogger("radar.sources.crossref")

WORKS_URL = "https://api.crossref.org/works"

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_jats(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    return clean_abstract(_TAG_RE.sub(" ", text))


def _iso_from_date_parts(date_parts) -> Optional[str]:
    """Build an ISO date string from Crossref date-parts ([[y, m, d]])."""
    if not date_parts:
        return None
    parts = date_parts[0] if isinstance(date_parts[0], list) else date_parts
    if not parts:
        return None
    bits = []
    for i, val in enumerate(parts[:3]):
        if val is None:
            break
        bits.append(f"{int(val):04d}" if i == 0 else f"{int(val):02d}")
    return "-".join(bits) if bits else None


def fetch_by_doi(doi, http, email) -> Optional[Paper]:
    if not doi:
        return None
    data = http.get_json(f"{WORKS_URL}/{doi}")
    if not data:
        log.warning("crossref: no data for doi %r", doi)
        return None
    message = data.get("message")
    if not message:
        log.warning("crossref: empty message for doi %r", doi)
        return None

    titles = message.get("title") or []
    title = titles[0] if titles else ""

    abstract = _strip_jats(message.get("abstract"))

    authors = []
    for a in message.get("author") or []:
        given = (a or {}).get("given", "")
        family = (a or {}).get("family", "")
        name = f"{given} {family}".strip()
        if name:
            authors.append(name)

    containers = message.get("container-title") or []
    venue = containers[0] if containers else None

    published = None
    pub = message.get("published") or message.get("published-online") or message.get("published-print")
    if pub:
        published = _iso_from_date_parts(pub.get("date-parts"))

    real_doi = message.get("DOI") or doi
    is_preprint = message.get("type") == "posted-content"

    raw = {
        "DOI": message.get("DOI"),
        "title": titles,
        "container-title": containers,
        "type": message.get("type"),
        "published": pub,
        "has_abstract": message.get("abstract") is not None,
        "author_count": len(message.get("author") or []),
    }

    return Paper(
        title=title,
        abstract=abstract,
        authors=authors,
        venue=venue,
        published=published,
        doi=real_doi,
        arxiv_id=None,
        source_url=f"https://doi.org/{real_doi}",
        source_api="crossref",
        is_preprint=is_preprint,
        cited_by_count=None,
        raw=raw,
    )
