"""Source adapters. Each adapter turns one API response into Paper records.

ADAPTER CONTRACT (every topic-mode source module implements this):

    def fetch(query: str, since: str | None, limit: int, http: Http,
              email: str) -> list[Paper]

    - query:  the topic search string
    - since:  ISO date "YYYY-MM-DD" lower bound, or None
    - limit:  max records to return
    - http:   a radar.http.Http instance (shared session, UA, timeout, retry)
    - email:  contact email for polite-pool / mailto parameters
    Returns a list of radar.normalize.Paper. Never raises on a dead source:
    log and return [] instead. Captures the fields used onto Paper.raw for
    provenance. Sets abstract to None when none is available (never invented).

VALIDATION / FALLBACK (crossref module):

    def validate_doi(doi: str, http: Http) -> bool          # re-exported from citations
    def fetch_by_doi(doi: str, http: Http, email: str) -> Paper | None

PRIMARY-PAPER FETCH (used by big-story mode):

    openalex.fetch_by_doi(doi, http, email) -> Paper | None

The registry below lets the pipeline look adapters up by the names used in
config/sources.yaml.
"""
from __future__ import annotations

from . import openalex, arxiv, europepmc

# Populated lazily to avoid importing optional adapters (springer) when unused.
REGISTRY = {
    "openalex": openalex,
    "arxiv": arxiv,
    "europepmc": europepmc,
}


def get(name: str):
    return REGISTRY.get(name)
