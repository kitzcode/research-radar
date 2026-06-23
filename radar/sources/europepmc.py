"""Europe PMC adapter. Turns the Europe PMC REST search into Paper records.

FIELD NAMES: per the Europe PMC REST docs (resultType=core), results live under
resultList.result; each result carries title, abstractText, doi, pmid, pmcid,
source, firstPublicationDate, pubYear, journalInfo.journal.title, journalTitle,
authorString, and authorList.author[].fullName. This adapter reads those names
and falls back defensively (authorString split, journalTitle, pubYear) when a
nested field is absent. The code tolerates missing keys so a shape change
degrades gracefully rather than raising.

NOTE ON LIVE VERIFICATION: the build environment blocked outbound network from
the tooling (curl, python requests, and WebFetch were all denied), so these key
names are taken from the official Europe PMC REST documentation and prior known
responses, not confirmed against a live JSON dump in this run. The defensive
fallbacks above mean a renamed field yields None (never a crash, never fabricated
data). Re-run fetch() with network access to confirm the exact shapes.
"""
from __future__ import annotations

import logging
from typing import Optional

from ..normalize import Paper, clean_abstract

log = logging.getLogger("radar.sources.europepmc")

SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


def _authors(result: dict) -> list[str]:
    """Prefer the structured authorList.author[].fullName, fall back to authorString."""
    authors = []
    author_list = (result.get("authorList") or {}).get("author") or []
    for a in author_list:
        name = (a or {}).get("fullName") or (a or {}).get("name")
        if name:
            authors.append(name)
    if authors:
        return authors
    author_string = result.get("authorString")
    if author_string:
        return [a.strip() for a in author_string.split(",") if a.strip()]
    return []


def _venue(result: dict) -> Optional[str]:
    journal_info = result.get("journalInfo") or {}
    journal = journal_info.get("journal") or {}
    return journal.get("title") or result.get("journalTitle")


def _published(result: dict) -> Optional[str]:
    return result.get("firstPublicationDate") or result.get("pubYear")


def _source_url(result: dict, doi: Optional[str]) -> str:
    """Europe PMC article URL when there is no DOI but a pmid/pmcid exists."""
    if doi:
        return f"https://doi.org/{doi}"
    source = result.get("source")
    art_id = result.get("pmid") or result.get("pmcid") or result.get("id")
    if source and art_id:
        return f"https://europepmc.org/article/{source}/{art_id}"
    return ""


def _paper_from_result(result: dict) -> Paper:
    title = result.get("title") or ""
    abstract = clean_abstract(result.get("abstractText"))
    doi = result.get("doi")
    authors = _authors(result)
    venue = _venue(result)
    published = _published(result)
    source_url = _source_url(result, doi)

    raw = {
        "id": result.get("id"),
        "source": result.get("source"),
        "pmid": result.get("pmid"),
        "pmcid": result.get("pmcid"),
        "doi": doi,
        "title": result.get("title"),
        "has_abstractText": result.get("abstractText") is not None,
        "firstPublicationDate": result.get("firstPublicationDate"),
        "pubYear": result.get("pubYear"),
        "journalTitle": result.get("journalTitle"),
        "authorString": result.get("authorString"),
    }

    return Paper(
        title=title,
        abstract=abstract,
        authors=authors,
        venue=venue,
        published=published,
        doi=doi,
        arxiv_id=None,
        source_url=source_url,
        source_api="europepmc",
        is_preprint=False,
        cited_by_count=None,
        raw=raw,
    )


def fetch(query, since, limit, http, email) -> list[Paper]:
    params = {
        "query": query,
        "format": "json",
        "resultType": "core",
        "pageSize": limit,
    }
    data = http.get_json(SEARCH_URL, params=params)
    if not data:
        log.warning("europepmc: no data for query %r", query)
        return []

    results = (data.get("resultList") or {}).get("result") or []
    papers = []
    for result in results:
        try:
            paper = _paper_from_result(result)
        except Exception as exc:  # noqa: BLE001
            log.warning("europepmc: skipping a malformed result: %s", exc)
            continue
        # Apply the since lower bound when the record exposes a usable date.
        if since is not None and paper.published and paper.published[:10] < since:
            continue
        papers.append(paper)
    return papers
