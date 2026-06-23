"""Big-story mode (mode B): watch journal news feeds, find the primary paper.

Entry: python -m radar bigstory  (also the weekly cron).

For each feed entry we regex-scan for DOI candidates, validate every candidate
against Crossref, and only then fetch the confirmed paper's real abstract and
metadata. Nothing is ever linked or summarized without a confirmed identifier.
"""
from __future__ import annotations

import logging

from . import citations, config, store, summarize
from .http import Http
from .normalize import Paper
from .sources import crossref, openalex

log = logging.getLogger("radar.bigstory")


def _is_self_doi(doi: str, link: str | None) -> bool:
    """True when a DOI is the feed item's own (the commentary), not the paper.

    Journal news links embed the article's own DOI suffix (for example a Nature
    link .../articles/d41586-026-01970-2 for DOI 10.1038/d41586-026-01970-2).
    Such a DOI points at the commentary itself, not at the primary research the
    write-up is about.
    """
    if not link or not doi:
        return False
    suffix = doi.rsplit("/", 1)[-1].lower()
    return suffix in link.lower()


def _confirm_primary_doi(entry: dict, http: Http) -> str | None:
    """Return the first Crossref-confirmed DOI in the entry, else None.

    Candidates come only from the entry's own text. Each is validated against
    Crossref before it is trusted. Unconfirmed candidates are discarded. This
    helper does not distinguish primary from commentary, see confirm_doi.
    """
    result = confirm_doi(entry, http)
    return result[0] if result else None


def confirm_doi(entry: dict, http: Http) -> tuple[str, bool] | None:
    """Confirm a DOI for a feed entry and say whether it is primary research.

    Prefers an external DOI (a primary research paper the news is about). Falls
    back to the entry's own DOI only when no external one is confirmable, and
    flags it as commentary. Returns (doi, is_commentary) or None when nothing
    can be confirmed. Unconfirmed candidates are never returned.
    """
    link = entry.get("link")
    text = " ".join(filter(None, [entry.get("summary"), entry.get("content"),
                                   entry.get("link")]))
    candidates = citations.extract_doi_candidates(text)
    external = [c for c in candidates if not _is_self_doi(c, link)]
    self_dois = [c for c in candidates if _is_self_doi(c, link)]

    # Prefer a confirmed external (primary research) DOI.
    for cand in external:
        if citations.validate_doi(cand, http):
            log.info("confirmed primary DOI %s for %s", cand, entry.get("title", "")[:50])
            return (cand, False)
        log.info("rejected unconfirmed external DOI %s", cand)

    # Fall back to the commentary's own DOI, clearly labeled.
    for cand in self_dois:
        if citations.validate_doi(cand, http):
            log.info("only commentary DOI %s confirmed for %s", cand, entry.get("title", "")[:50])
            return (cand, True)
        log.info("rejected unconfirmed self DOI %s", cand)
    return None


def _fetch_primary(doi: str, http: Http, email: str) -> Paper | None:
    """Fetch the confirmed paper, preferring OpenAlex, falling back to Crossref."""
    paper = openalex.fetch_by_doi(doi, http, email)
    if paper is None:
        paper = crossref.fetch_by_doi(doi, http, email)
    # Springer fallback only for Nature-family DOIs missing an abstract.
    if paper is not None and not paper.abstract and doi.startswith("10.1038"):
        try:
            from .sources import springer
            sp = springer.fetch_by_doi(doi, http, email, api_key=config.springer_key())
            if sp is not None and sp.abstract:
                paper.abstract = sp.abstract
                paper.raw.setdefault("springer", sp.raw)
        except Exception as exc:  # noqa: BLE001  optional source, never fatal
            log.warning("springer fallback failed: %s", exc)
    return paper


def run(ignore_seen: bool = False, http: Http | None = None,
        render: bool = True) -> dict:
    """Run the big-story pipeline and return the public run object."""
    from . import feeds  # local import keeps feedparser optional for topic mode

    http = http or Http()
    email = config.contact_email()
    seen = set() if ignore_seen else store.load_seen()
    new_seen = set(seen)

    entries = feeds.fetch_feeds(config.feeds(), http)
    log.info("collected %d feed entries", len(entries))

    papers: list[Paper] = []
    for entry in entries:
        link = entry.get("link")
        # Quick skip on the entry link before any network work.
        link_key = store.seen_key_for(None, link)
        if link_key and link_key in seen:
            continue

        confirmed = confirm_doi(entry, http)
        if not confirmed:
            log.info("no confirmable DOI, skipping: %s", entry.get("title", "")[:60])
            continue
        doi, is_commentary = confirmed

        doi_key = store.seen_key_for(doi, None)
        if doi_key in seen:
            continue

        paper = _fetch_primary(doi, http, email)
        if paper is None or not paper.has_identifier():
            log.info("could not fetch confirmed paper for DOI %s", doi)
            continue

        # Mark commentary clearly so the site never presents it as primary research.
        paper.is_commentary = is_commentary
        # The why-notable note is derived only from the editors' framing text.
        framing = " ".join(filter(None, [entry.get("title"), entry.get("summary")]))
        paper.raw.setdefault("feed_framing", framing)
        papers.append(paper)

        if doi_key:
            new_seen.add(doi_key)
        if link_key:
            new_seen.add(link_key)

    # Triage, summarize, and add why-notable.
    kept: list[Paper] = []
    require_relevant = bool(config.settings().get("relevance_threshold", True))
    for p in papers:
        # Big stories use the paper title as the topic for the relevance gate.
        summarize.triage(p, p.title)
        if p.relevant or not require_relevant:
            kept.append(p)
    for p in kept:
        summarize.summarize_paper(p)
        summarize.summarize_why_notable(p, p.raw.get("feed_framing", ""))

    kept = [citations.finalize(p) for p in kept if p.has_identifier()]

    public_run = store.build_run("bigstory", None, kept, for_public=True)
    local_run = store.build_run("bigstory", None, kept, for_public=False)
    local_run["generated_at"] = public_run["generated_at"]

    store.write_drafts(local_run, "weekly")
    store.append_archive(public_run, "weekly")
    runs = store.append_public_run(public_run)

    if not ignore_seen:
        store.save_seen(new_seen)

    if render:
        from . import site
        site.render_site(runs)

    return public_run
