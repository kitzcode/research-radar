"""The normalized Paper record and shared normalization helpers.

Every source adapter returns Paper objects. Raw payload fields used are retained
on Paper.raw for provenance, so any claim can be traced back to its source.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Paper:
    title: str
    abstract: Optional[str]          # None if unavailable, never invented
    authors: list[str]
    venue: Optional[str]
    published: Optional[str]         # ISO date string from the API
    doi: Optional[str]               # real, from API or Crossref-validated
    arxiv_id: Optional[str]
    source_url: str                  # canonical link, set or rebuilt in citations.py
    source_api: str                  # "openalex" | "arxiv" | "europepmc" | ...
    is_preprint: bool = False
    is_commentary: bool = False      # mode B: the item is the news/commentary, not primary research
    cited_by_count: Optional[int] = None
    raw: dict = field(default_factory=dict)   # provenance: fields used

    # Filled later by the pipeline:
    relevant: Optional[bool] = None
    relevance_reason: Optional[str] = None
    summary: Optional[str] = None
    why_notable: Optional[str] = None         # mode B only

    def has_identifier(self) -> bool:
        """A record is valid for output only if it has a usable identifier."""
        return bool(self.doi or self.arxiv_id or self.source_url)

    def to_dict(self) -> dict:
        return asdict(self)


def reconstruct_abstract(inv: Optional[dict]) -> str:
    """Rebuild plain text from OpenAlex abstract_inverted_index.

    The index maps each word to the list of positions where it appears.
    Returns an empty string when the index is missing.
    """
    if not inv:
        return ""
    pairs = [(pos, word) for word, positions in inv.items() for pos in positions]
    pairs.sort()
    return " ".join(w for _, w in pairs)


def clean_abstract(text: Optional[str]) -> Optional[str]:
    """Trim and collapse whitespace. Return None for empty or missing text.

    Adapters that pull abstracts from JATS or HTML should strip tags first;
    this is the final whitespace pass. We never fabricate an abstract, so an
    empty result becomes None and the record is marked abstract unavailable.
    """
    if not text:
        return None
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _norm_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()


def dedupe(papers: list[Paper]) -> list[Paper]:
    """Deduplicate across sources by DOI first, then by normalized title.

    Order is preserved. The first occurrence wins, so callers should sort by
    preference (for example newest or most cited) before calling.
    """
    seen_doi: set[str] = set()
    seen_title: set[str] = set()
    out: list[Paper] = []
    for p in papers:
        key_doi = (p.doi or "").lower()
        key_title = _norm_title(p.title)
        if key_doi and key_doi in seen_doi:
            continue
        if not key_doi and key_title and key_title in seen_title:
            continue
        if key_doi:
            seen_doi.add(key_doi)
        if key_title:
            seen_title.add(key_title)
        out.append(p)
    return out
