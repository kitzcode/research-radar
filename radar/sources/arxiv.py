"""arXiv adapter. Turns the arXiv Atom API into Paper records.

The arXiv API returns Atom XML, parsed here with feedparser. Records are
preprints (is_preprint=True) and this adapter does not assert DOIs (doi=None);
DOI resolution is left to the crossref/openalex validators downstream.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

import feedparser

from ..normalize import Paper, clean_abstract

log = logging.getLogger("radar.sources.arxiv")

# HTTPS endpoint. The http:// form returns a 301 redirect.
QUERY_URL = "https://export.arxiv.org/api/query"

# arXiv entry ids look like http://arxiv.org/abs/2401.01234v1 ; pull the id and
# drop the trailing version suffix (v1, v2, ...).
_ARXIV_ID_RE = re.compile(r"arxiv\.org/abs/(.+?)(v\d+)?$", re.IGNORECASE)


def _arxiv_id_from_url(entry_id: Optional[str]) -> Optional[str]:
    if not entry_id:
        return None
    m = _ARXIV_ID_RE.search(entry_id.strip())
    if m:
        return m.group(1)
    return None


def _paper_from_entry(entry) -> Paper:
    title = clean_abstract(getattr(entry, "title", "")) or ""

    abstract = clean_abstract(getattr(entry, "summary", None))

    authors = []
    for a in getattr(entry, "authors", None) or []:
        # feedparser yields dict-like author entries with a "name" key.
        name = a.get("name") if isinstance(a, dict) else getattr(a, "name", None)
        if name:
            authors.append(name)

    entry_id = getattr(entry, "id", None)
    arxiv_id = _arxiv_id_from_url(entry_id)
    published = getattr(entry, "published", None)

    raw = {
        "id": entry_id,
        "title": getattr(entry, "title", None),
        "published": published,
        "author_names": authors,
    }

    return Paper(
        title=title,
        abstract=abstract,
        authors=authors,
        venue="arXiv",
        published=published,
        doi=None,
        arxiv_id=arxiv_id,
        source_url=entry_id or "",
        source_api="arxiv",
        is_preprint=True,
        cited_by_count=None,
        raw=raw,
    )


def fetch(query, since, limit, http, email) -> list[Paper]:
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": limit,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    resp = http.get(QUERY_URL, params=params)
    if resp is None or resp.status_code != 200:
        code = None if resp is None else resp.status_code
        log.warning("arxiv: bad response (status %s) for query %r", code, query)
        return []

    parsed = feedparser.parse(resp.text)
    papers = []
    for entry in parsed.entries or []:
        try:
            paper = _paper_from_entry(entry)
        except Exception as exc:  # noqa: BLE001
            log.warning("arxiv: skipping a malformed entry: %s", exc)
            continue
        # Drop entries older than the since bound (compare ISO date prefixes).
        if since is not None and paper.published and paper.published[:10] < since:
            continue
        papers.append(paper)
    return papers
