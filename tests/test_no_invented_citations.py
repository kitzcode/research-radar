"""Prime directive: a summary never carries a URL, DOI, or DOI-shaped string.

The model is mocked so the test runs offline. We check both that a clean model
response survives and that the code-side post-check blanks a leaky one.
"""
import re

from radar import llm, summarize
from radar.citations import DOI_RE
from radar.normalize import Paper


def _paper():
    return Paper(
        title="Improved base editors",
        abstract="The authors engineer a base editor and measure off-target activity in cells.",
        authors=["A. Author"], venue="Nature", published="2026-01-01",
        doi="10.1038/s41586-026-00000-0", arxiv_id=None,
        source_url="", source_api="openalex",
    )


def test_clean_summary_has_no_identifiers(monkeypatch):
    clean = ("Researchers redesigned a base editor and tested how often it edits "
             "unintended sites, reporting lower off-target activity.")
    monkeypatch.setattr(llm, "call", lambda *a, **k: clean)
    p = summarize.summarize_paper(_paper())
    assert p.summary is not None
    low = p.summary.lower()
    assert "http" not in low
    assert "doi" not in low
    assert DOI_RE.search(p.summary) is None


def test_postcheck_blanks_summary_with_doi():
    leaky = "This work is great. See 10.1038/s41586-026-00000-0 for details."
    assert summarize.enforce_grounding(leaky) is None


def test_postcheck_blanks_summary_with_url():
    leaky = "Read more at https://doi.org/10.1038/x."
    assert summarize.enforce_grounding(leaky) is None


def test_summarizer_output_blanked_when_model_leaks_doi(monkeypatch):
    # Even if the model disobeys and emits a DOI, summarize_paper must blank it.
    monkeypatch.setattr(llm, "call",
                        lambda *a, **k: "Great paper, 10.1234/abcd.5678 explains it.")
    p = summarize.summarize_paper(_paper())
    assert p.summary is None
