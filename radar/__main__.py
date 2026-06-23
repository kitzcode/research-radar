"""Command line entry point.

    python -m radar topic "CRISPR base editing" --since 2025-01-01 --n 12
    python -m radar bigstory [--ignore-seen]
    python -m radar render        # re-render docs/ from saved public runs

Topic and bigstory call the Anthropic API for triage and summaries, so they need
ANTHROPIC_API_KEY. Use --no-llm to run retrieval and assembly only (no API key
needed) for testing the data pipeline.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="radar", description="Research Radar")
    parser.add_argument("-v", "--verbose", action="store_true", help="info-level logs")
    sub = parser.add_subparsers(dest="command", required=True)

    p_topic = sub.add_parser("topic", help="summarize recent papers on a topic")
    p_topic.add_argument("query", help="the topic to search")
    p_topic.add_argument("--since", default=None, help="ISO date lower bound (YYYY-MM-DD)")
    p_topic.add_argument("--n", type=int, default=None, help="per-source result cap")
    p_topic.add_argument("--no-llm", action="store_true",
                         help="skip triage and summaries (no API key needed)")
    p_topic.add_argument("--no-render", action="store_true", help="do not write docs/")

    p_topics = sub.add_parser("topics", help="run the saved watchlist (config/topics.yaml)")
    p_topics.add_argument("--only", default=None,
                          help="run only watchlist topics containing this substring")
    p_topics.add_argument("--since", default=None, help="ISO date lower bound (YYYY-MM-DD)")
    p_topics.add_argument("--n", type=int, default=None, help="per-source result cap")
    p_topics.add_argument("--list", action="store_true", dest="list_only",
                          help="print the watchlist and exit, do not run")
    p_topics.add_argument("--no-llm", action="store_true",
                          help="skip triage and summaries (no API key needed)")
    p_topics.add_argument("--no-render", action="store_true", help="do not write docs/")

    p_big = sub.add_parser("bigstory", help="weekly journal news to primary papers")
    p_big.add_argument("--ignore-seen", action="store_true", help="re-process seen items")
    p_big.add_argument("--no-render", action="store_true", help="do not write docs/")

    sub.add_parser("render", help="re-render docs/ from saved public runs")

    args = parser.parse_args(argv)
    _setup_logging(args.verbose)

    if args.command == "topic":
        from . import topic_mode
        run = topic_mode.run(
            args.query, since=args.since, n=args.n,
            do_llm=not args.no_llm, render=not args.no_render,
        )
        print(json.dumps(run, indent=2, ensure_ascii=False))
        return 0

    if args.command == "topics":
        from . import config, topic_mode
        topics = config.watchlist_topics()
        if args.only:
            needle = args.only.lower()
            topics = [t for t in topics if needle in t.lower()]
        if args.list_only:
            print(f"{len(topics)} watchlist topic(s):")
            for t in topics:
                print(f"  - {t}")
            return 0
        if not topics:
            print("no matching watchlist topics (check config/topics.yaml or --only)")
            return 1
        defaults = config.watchlist_defaults()
        since = args.since
        if since is None and defaults.get("since_days"):
            from datetime import date, timedelta
            since = (date.today() - timedelta(days=int(defaults["since_days"]))).isoformat()
        n = args.n or defaults.get("per_source_count")
        runs = topic_mode.run_many(
            topics, since=since, n=n,
            do_llm=not args.no_llm, render=not args.no_render,
        )
        total = sum(r["count"] for r in runs)
        print(f"ran {len(runs)} topic(s), {total} items total. docs/ updated.")
        return 0

    if args.command == "bigstory":
        from . import bigstory_mode
        run = bigstory_mode.run(ignore_seen=args.ignore_seen, render=not args.no_render)
        print(json.dumps(run, indent=2, ensure_ascii=False))
        return 0

    if args.command == "render":
        from . import site, store
        runs = store.load_public_runs()
        path = site.render_site(runs)
        print(f"rendered {path} from {len(runs)} run(s)")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
