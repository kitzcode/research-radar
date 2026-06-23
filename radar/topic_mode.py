"""Topic mode (mode A): retrieve, triage, summarize, assemble, write, render.

CLI: python -m radar topic "CRISPR base editing" --since 2025-01-01 --n 12
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from . import citations, config, sources, store, summarize
from .http import Http
from .normalize import Paper, dedupe

log = logging.getLogger("radar.topic")


def _default_since() -> str:
    days = int(config.settings().get("since_days_default", 120))
    return (date.today() - timedelta(days=days)).isoformat()


def retrieve(query: str, since: str | None, n: int, http: Http,
             source_names: list[str], email: str) -> list[Paper]:
    """Query each active source, normalize to Paper, dedupe across sources.

    A source that raises (including the not-implemented stub) is logged and
    skipped, never fatal.
    """
    collected: list[Paper] = []
    for name in source_names:
        mod = sources.get(name)
        if mod is None:
            log.warning("unknown source in config: %s", name)
            continue
        try:
            got = mod.fetch(query, since, n, http, email)
            log.info("source %s returned %d", name, len(got))
            collected.append((name, got))
        except NotImplementedError:
            log.warning("source %s not implemented yet, skipping", name)
        except Exception as exc:  # noqa: BLE001  a dead source is never fatal
            log.warning("source %s failed: %s", name, exc)
    # Interleave by preference order so dedupe keeps the higher-priority copy.
    flat: list[Paper] = []
    for _name, papers in collected:
        flat.extend(papers)
    return dedupe(flat)


def assemble(papers: list[Paper]) -> list[Paper]:
    """Finalize links and drop any record without a usable identifier."""
    out = []
    for p in papers:
        citations.finalize(p)
        if p.has_identifier():
            out.append(p)
        else:
            log.warning("dropping record with no identifier: %s", p.title[:60])
    return out


def run(query: str, since: str | None = None, n: int | None = None,
        do_llm: bool = True, http: Http | None = None,
        render: bool = True) -> dict:
    """Run the full topic pipeline and return the public run object."""
    since = since or _default_since()
    n = n or config.per_source_count()
    http = http or Http()
    email = config.contact_email()
    source_names = config.active_topic_sources()

    log.info("topic '%s' since %s n=%d sources=%s", query, since, n, source_names)
    papers = retrieve(query, since, n, http, source_names, email)
    log.info("retrieved %d unique papers", len(papers))

    if do_llm:
        keep: list[Paper] = []
        require_relevant = bool(config.settings().get("relevance_threshold", True))
        for p in papers:
            summarize.triage(p, query)
            if p.relevant or not require_relevant:
                keep.append(p)
            else:
                log.info("triaged out: %s (%s)", p.title[:50], p.relevance_reason)
        papers = keep
        for p in papers:
            summarize.summarize_paper(p)

    papers = assemble(papers)

    slug = store.slugify(query)
    public_run = store.build_run("topic", query, papers, for_public=True)
    local_run = store.build_run("topic", query, papers, for_public=False)
    # Keep generated_at consistent between the two views.
    local_run["generated_at"] = public_run["generated_at"]

    store.write_drafts(local_run, slug)
    store.append_archive(public_run, slug)
    runs = store.append_public_run(public_run)

    if render:
        from . import site  # imported lazily so data runs do not need jinja
        site.render_site(runs)

    return public_run


def run_many(topics: list[str], since: str | None = None, n: int | None = None,
             do_llm: bool = True, render: bool = True) -> list[dict]:
    """Run a list of topics (the saved watchlist) and render the site once.

    A shared HTTP session is reused across topics. Each topic is written to its
    own drafts JSON and markdown archive and prepended to the public run history,
    so the site shows every topic with the most recent run on top.
    """
    http = Http()
    results: list[dict] = []
    for topic in topics:
        log.info("watchlist topic: %s", topic)
        try:
            run_obj = run(topic, since=since, n=n, do_llm=do_llm, http=http, render=False)
            results.append(run_obj)
        except Exception as exc:  # noqa: BLE001  one bad topic never sinks the batch
            log.warning("topic '%s' failed: %s", topic, exc)
    if render:
        from . import site, store
        site.render_site(store.load_public_runs())
    return results
