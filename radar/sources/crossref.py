"""STUB for crossref adapter. Replaced by the source-adapters build step."""
from __future__ import annotations

import logging

from ..citations import validate_doi  # noqa: F401  re-exported per contract

log = logging.getLogger("radar.sources.crossref")


def fetch_by_doi(doi, http, email):
    raise NotImplementedError("crossref.fetch_by_doi not implemented yet")
