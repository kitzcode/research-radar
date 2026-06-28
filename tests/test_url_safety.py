"""Outbound links must be http(s). A hostile scheme is never emitted to a href.

A compromised or malicious API record could carry a javascript: or data: URL in
source_url. HTML escaping does not neutralize a dangerous scheme, so canonical_url
gates it, and topic_mode.assemble drops a record left with no usable link.
"""
from radar import citations, topic_mode
from radar.normalize import Paper


def _paper(source_url, doi=None, arxiv_id=None):
    return Paper(title="t", abstract="a", authors=[], venue=None, published=None,
                 doi=doi, arxiv_id=arxiv_id, source_url=source_url, source_api="x")


def test_safe_http_url_allows_http_and_https():
    assert citations.safe_http_url("https://example.org/x") == "https://example.org/x"
    assert citations.safe_http_url("http://example.org/x") == "http://example.org/x"


def test_safe_http_url_blocks_dangerous_schemes():
    for bad in ["javascript:alert(1)", "data:text/html,<script>1</script>",
                "vbscript:msgbox", " javascript:alert(1)", "JAVASCRIPT:alert(1)", ""]:
        assert citations.safe_http_url(bad) == ""


def test_canonical_url_drops_hostile_source_url():
    p = _paper("javascript:alert(document.cookie)")
    assert citations.canonical_url(p) == ""


def test_canonical_url_keeps_doi_over_anything():
    p = _paper("javascript:alert(1)", doi="10.1/x")
    assert citations.canonical_url(p) == "https://doi.org/10.1/x"


def test_assemble_drops_record_with_only_hostile_url():
    safe = _paper("https://openalex.org/W1")
    hostile = _paper("javascript:alert(1)")
    kept = topic_mode.assemble([safe, hostile])
    urls = [p.source_url for p in kept]
    assert "https://openalex.org/W1" in urls
    # The hostile record is finalized to an empty url and then dropped.
    assert all("javascript" not in (u or "") for u in urls)
    assert len(kept) == 1
