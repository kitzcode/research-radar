"""A missing abstract is never summarized and renders as "Abstract unavailable".

The model must not even be called for an abstract-less paper, the summary stays
None, and the rendered site shows the unavailable note rather than a summary.
"""
from radar import llm, site, store, summarize
from radar.normalize import Paper


def _no_abstract_paper():
    return Paper(
        title="A paper with no abstract", abstract=None, authors=["X"],
        venue="Venue", published="2026-01-01", doi="10.1/none",
        arxiv_id=None, source_url="", source_api="openalex",
    )


def test_no_abstract_is_not_summarized(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("llm.call must not be invoked for a missing abstract")
    monkeypatch.setattr(llm, "call", boom)
    p = summarize.summarize_paper(_no_abstract_paper())
    assert p.summary is None


def test_item_marks_abstract_unavailable():
    item = store.item_dict(_no_abstract_paper())
    assert item["summary"] is None
    assert item["abstract_available"] is False


def test_site_renders_abstract_unavailable(tmp_path):
    run = store.build_run("topic", "demo", [_no_abstract_paper()], for_public=True)
    out = site.render_site([run], out_dir=tmp_path)
    html = out.read_text(encoding="utf-8")
    assert "Abstract unavailable" in html
    # The raw abstract field (None here) must never leak as text either way.
    assert "_abstract" not in html
