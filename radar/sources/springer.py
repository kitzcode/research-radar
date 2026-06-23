"""Optional Springer Nature adapter, key-gated.

Only used to recover Nature-family DOIs (prefix 10.1038) that OpenAlex and
Crossref miss. Without an API key it returns None immediately, so an absent key
never fails the build. The Springer Meta API returns records under "records".
"""
from __future__ import annotations

import logging
from typing import Optional

from ..normalize import Paper, clean_abstract

log = logging.getLogger("radar.sources.springer")

META_URL = "https://api.springernature.com/meta/v2/json"


def fetch_by_doi(doi, http, email, api_key=None) -> Optional[Paper]:
    if not api_key:
        # No key: skip gracefully, this source is optional.
        return None
    if not doi:
        return None

    params = {"q": f"doi:{doi}", "api_key": api_key}
    data = http.get_json(META_URL, params=params)
    if not data:
        log.warning("springer: no data for doi %r", doi)
        return None

    records = data.get("records") or []
    if not records:
        log.warning("springer: no records for doi %r", doi)
        return None
    rec = records[0]

    title = rec.get("title") or ""
    abstract = clean_abstract(rec.get("abstract"))

    authors = []
    for c in rec.get("creators") or []:
        name = c.get("creator") if isinstance(c, dict) else None
        if name:
            authors.append(name)

    venue = rec.get("publicationName")
    published = rec.get("publicationDate") or rec.get("onlineDate")
    real_doi = rec.get("doi") or doi

    raw = {
        "doi": rec.get("doi"),
        "title": rec.get("title"),
        "publicationName": rec.get("publicationName"),
        "publicationDate": rec.get("publicationDate"),
        "has_abstract": bool(rec.get("abstract")),
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
        source_api="springer",
        is_preprint=False,
        cited_by_count=None,
        raw=raw,
    )
