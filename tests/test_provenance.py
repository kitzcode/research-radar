"""Every output item carries a verifiable identifier traceable to a raw payload.

Runs the OpenAlex adapter against a recorded fixture (no network), then the
topic-mode assembly step, and asserts each item has a doi, arxiv_id, or real
source_url, and that the identifier is present in the captured raw payload.
"""
import json

from conftest import FIXTURES

from radar import topic_mode
from radar.sources import openalex


class FakeHttp:
    """Returns a recorded OpenAlex payload for any get_json call."""
    def __init__(self, payload):
        self.payload = payload

    def get_json(self, url, params=None, headers=None):
        return self.payload

    def get(self, *a, **k):
        return None


def _load():
    with (FIXTURES / "openalex_works.json").open() as fh:
        return json.load(fh)


def test_every_item_has_traceable_identifier():
    payload = _load()
    http = FakeHttp(payload)
    papers = openalex.fetch("crispr base editing", None, 5, http, "test@example.com")
    assert papers, "fixture should yield papers"

    items = topic_mode.assemble(papers)
    assert items, "assembly should keep papers with identifiers"

    for p in items:
        # A usable identifier must exist.
        assert p.doi or p.arxiv_id or p.source_url, "record has no identifier"
        # And it must trace back to the captured raw payload.
        raw_blob = json.dumps(p.raw).lower()
        ident = (p.doi or p.arxiv_id or p.source_url).lower()
        # The DOI from OpenAlex is stored bare; the raw doi field may carry the
        # full https://doi.org/ URL, so check the bare suffix is present.
        needle = ident.rsplit("/", 1)[-1] if p.doi else ident
        assert needle in raw_blob, f"identifier {ident} not found in provenance raw"


def test_records_without_identifier_are_dropped():
    from radar.normalize import Paper
    good = Paper(title="ok", abstract="a", authors=[], venue=None, published=None,
                 doi="10.1/x", arxiv_id=None, source_url="", source_api="openalex")
    bad = Paper(title="no id", abstract="a", authors=[], venue=None, published=None,
                doi=None, arxiv_id=None, source_url="", source_api="openalex")
    kept = topic_mode.assemble([good, bad])
    titles = [p.title for p in kept]
    assert "ok" in titles
    assert "no id" not in titles
