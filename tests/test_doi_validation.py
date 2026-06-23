"""A DOI is trusted only if it came from a structured search or passed Crossref.

validate_doi returns False for a missing record (404 modeled as get_json -> None)
and True for a recorded valid Crossref record. A regex-extracted DOI is never
attached to a Paper in big-story mode unless validation confirms it.
"""
import json

from conftest import FIXTURES

from radar import bigstory_mode, citations


class FakeHttp:
    def __init__(self, response):
        self._response = response
        self.calls = []

    def get_json(self, url, params=None, headers=None):
        self.calls.append(url)
        # Allow a callable to vary the response by URL.
        if callable(self._response):
            return self._response(url)
        return self._response

    def get(self, *a, **k):
        return None


def test_validate_doi_false_on_404():
    http = FakeHttp(None)  # non-200 -> get_json returns None
    assert citations.validate_doi("10.9999/does-not-exist", http) is False


def test_validate_doi_true_on_recorded_record():
    with (FIXTURES / "crossref_valid.json").open() as fh:
        record = json.load(fh)
    doi = record["message"]["DOI"]
    http = FakeHttp(record)
    assert citations.validate_doi(doi, http) is True


def test_validate_doi_false_on_mismatched_record():
    # Crossref returns a record but for a different DOI: must not be trusted.
    http = FakeHttp({"message": {"DOI": "10.1/other"}})
    assert citations.validate_doi("10.1/requested", http) is False


def test_bigstory_only_keeps_confirmed_doi():
    # Entry text contains a DOI-shaped string, but Crossref does not confirm it.
    entry = {"summary": "A breakthrough described in 10.1234/fake.5678 today.",
             "content": "", "link": "https://news.example/story"}
    http = FakeHttp(None)  # validation always fails
    assert bigstory_mode._confirm_primary_doi(entry, http) is None


def test_bigstory_keeps_doi_when_confirmed():
    entry = {"summary": "See 10.1234/real.0001.", "content": "", "link": "x"}
    # Confirm only when the requested DOI is echoed back.
    def resp(url):
        doi = url.rsplit("/works/", 1)[-1]
        return {"message": {"DOI": doi}}
    http = FakeHttp(resp)
    assert bigstory_mode._confirm_primary_doi(entry, http) == "10.1234/real.0001"


def _echo_http():
    def resp(url):
        return {"message": {"DOI": url.rsplit("/works/", 1)[-1]}}
    return FakeHttp(resp)


def test_external_doi_is_primary_not_commentary():
    # Link embeds the commentary's own DOI; text also cites an external paper.
    entry = {
        "summary": "Our news piece 10.1038/d41586-026-01970-2 covers 10.1126/science.abc1234.",
        "content": "",
        "link": "https://www.nature.com/articles/d41586-026-01970-2",
    }
    doi, is_commentary = bigstory_mode.confirm_doi(entry, _echo_http())
    assert doi == "10.1126/science.abc1234"
    assert is_commentary is False


def test_self_doi_is_labeled_commentary():
    # Only the entry's own DOI is present, so it must be flagged as commentary.
    entry = {
        "summary": "A Nature news article, DOI 10.1038/d41586-026-01970-2.",
        "content": "",
        "link": "https://www.nature.com/articles/d41586-026-01970-2",
    }
    doi, is_commentary = bigstory_mode.confirm_doi(entry, _echo_http())
    assert doi == "10.1038/d41586-026-01970-2"
    assert is_commentary is True
