"""STUB for arxiv adapter. Replaced by the source-adapters build step.

Implements the adapter contract documented in radar/sources/__init__.py so the
package imports during foundation setup. Returns no papers until implemented.
"""
from __future__ import annotations

import logging

from ..normalize import Paper  # noqa: F401  (used by the real implementation)

log = logging.getLogger("radar.sources.arxiv")


def fetch(query, since, limit, http, email):
    raise NotImplementedError("arxiv.fetch not implemented yet")
