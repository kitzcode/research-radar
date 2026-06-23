"""OpenAlex adapter. Turns OpenAlex /works responses into Paper records.

Implements the adapter contract documented in radar/sources/__init__.py:
fetch() for topic search and fetch_by_doi() for big-story primary-paper lookup.
OpenAlex stores abstracts as an inverted index, rebuilt with reconstruct_abstract.
"""
from __future__ import annotations

import logging
from typing import Optional

from ..normalize import Paper, reconstruct_abstract, clean_abstract

log = logging.getLogger("radar.sources.openalex")

WORKS_URL = "https://api.openalex.org/works"


def _strip_doi(doi_url: Optional[str]) -> Optional[str]:
    """Return a bare DOI (10.xxxx/...) from an OpenAlex doi URL, or None."""
    if not doi_url:
        return None
    prefix = "https://doi.org/"
    if doi_url.lower().startswith(prefix):
        return doi_url[len(prefix):]
    return doi_url


def _paper_from_work(work: dict) -> Paper:
    """Build one Paper from a single OpenAlex work object."""
    title = work.get("display_name") or work.get("title") or ""

    abstract = clean_abstract(reconstruct_abstract(work.get("abstract_inverted_index")))

    authors = []
    for authorship in work.get("authorships") or []:
        author = (authorship or {}).get("author") or {}
        name = author.get("display_name")
        if name:
            authors.append(name)

    venue = None
    primary = work.get("primary_location") or {}
    source = primary.get("source") or {}
    venue = source.get("display_name")

    doi = _strip_doi(work.get("doi"))
    source_url = work.get("id") or ""

    raw = {
        "id": work.get("id"),
        "display_name": work.get("display_name"),
        "title": work.get("title"),
        "doi": work.get("doi"),
        "publication_date": work.get("publication_date"),
        "cited_by_count": work.get("cited_by_count"),
        "authorships": work.get("authorships"),
        "primary_location": work.get("primary_location"),
        "has_abstract_inverted_index": work.get("abstract_inverted_index") is not None,
    }

    return Paper(
        title=title,
        abstract=abstract,
        authors=authors,
        venue=venue,
        published=work.get("publication_date"),
        doi=doi,
        arxiv_id=None,
        source_url=source_url,
        source_api="openalex",
        is_preprint=False,
        cited_by_count=work.get("cited_by_count"),
        raw=raw,
    )


def fetch(query, since, limit, http, email) -> list[Paper]:
    params = {
        "search": query,
        "sort": "cited_by_count:desc",
        "per_page": limit,
        "mailto": email,
    }
    if since is not None:
        params["filter"] = f"from_publication_date:{since}"

    data = http.get_json(WORKS_URL, params=params)
    if not data:
        log.warning("openalex: no data for query %r", query)
        return []

    results = data.get("results") or []
    papers = []
    for work in results:
        try:
            papers.append(_paper_from_work(work))
        except Exception as exc:  # noqa: BLE001  one bad record must not kill the source
            log.warning("openalex: skipping a malformed work: %s", exc)
    return papers


def fetch_by_doi(doi, http, email) -> Optional[Paper]:
    """Fetch a single work by DOI for big-story primary-paper lookup.

    OpenAlex accepts a DOI URL as the id path, so we GET
    /works/https://doi.org/<doi>. Returns None if not found.
    """
    if not doi:
        return None
    url = f"{WORKS_URL}/https://doi.org/{doi}"
    data = http.get_json(url, params={"mailto": email})
    if not data or not data.get("id"):
        log.warning("openalex: no work for doi %r", doi)
        return None
    try:
        return _paper_from_work(data)
    except Exception as exc:  # noqa: BLE001
        log.warning("openalex: malformed work for doi %r: %s", doi, exc)
        return None
