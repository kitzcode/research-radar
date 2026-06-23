"""Big-story RSS feed fetching for mode B.

fetch_feeds pulls each configured feed, parses it with feedparser, and validates
that the feed is usable before yielding entries. A feed that fails to parse
(feedparser bozo flag set with no entries) or that has zero entries is logged and
skipped, so a dead or redirected feed is never fatal and never fabricated.
"""
from __future__ import annotations

import logging

import feedparser

log = logging.getLogger("radar.feeds")


def fetch_feeds(feeds, http) -> list[dict]:
    out: list[dict] = []
    for feed in feeds or []:
        name = feed.get("name")
        url = feed.get("url")
        kind = feed.get("kind")

        if not url:
            log.warning("feeds: skipping %r, no url", name)
            continue

        resp = http.get(url)
        if resp is None or resp.status_code != 200:
            code = None if resp is None else resp.status_code
            log.warning("feeds: skipping %r, bad response (status %s) from %s",
                        name, code, url)
            continue

        try:
            parsed = feedparser.parse(resp.text)
        except Exception as exc:  # noqa: BLE001  never let one feed kill the batch
            log.warning("feeds: skipping %r, parse error: %s", name, exc)
            continue

        entries = parsed.entries or []
        # Fail closed: a bozo feed with no entries, or any empty feed, is skipped.
        if not entries or (getattr(parsed, "bozo", 0) and not entries):
            log.warning("feeds: skipping %r, no usable entries (bozo=%s) from %s",
                        name, getattr(parsed, "bozo", 0), url)
            continue

        for entry in entries:
            content = None
            content_list = entry.get("content")
            if content_list:
                content = (content_list[0] or {}).get("value")
            summary = entry.get("summary")
            if not content:
                content = summary

            out.append({
                "feed_name": name,
                "kind": kind,
                "title": entry.get("title"),
                "link": entry.get("link"),
                "published": entry.get("published"),
                "summary": summary,
                "content": content,
            })

    return out
