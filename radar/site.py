"""Static site generator for Research Radar.

Renders run objects (topic or big-story) into a GitHub Pages site under docs/.

Public-display rule: cards show only title, citation, venue/date (via citation),
the AI summary, an optional why-notable line (big-story mode), a preprint tag,
and an outbound link to the source. Raw publisher abstracts are never rendered.
"""
from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from radar import config


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s or "section"


def _label(run: dict) -> str:
    """Short label for a run, used in the contents nav and section heading."""
    if run.get("mode") == "bigstory":
        return "Big stories this week"
    return run.get("query") or "Topic"

_env = Environment(
    loader=FileSystemLoader(str(config.TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "j2", "xml"]),
)


def _format_generated(value: str | None) -> str:
    """Turn an ISO timestamp into a friendly display string.

    Falls back to the raw value if it cannot be parsed.
    """
    if not value:
        return ""
    raw = str(value)
    iso = raw.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return raw
    return dt.strftime("%B %d, %Y at %H:%M UTC")


def render_site(runs: list[dict], out_dir: Path | None = None) -> Path:
    """Render the full site to out_dir (defaults to config.DOCS_DIR).

    Copies style.css into out_dir/assets, renders index.html, and returns the
    path to the written index.html.
    """
    out_dir = Path(out_dir) if out_dir is not None else config.DOCS_DIR
    assets_dir = out_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    shutil.copyfile(config.TEMPLATES_DIR / "style.css", assets_dir / "style.css")

    ordered = sorted(
        runs,
        key=lambda r: r.get("generated_at") or "",
        reverse=True,
    )
    # One menu entry per category: keep the most recent run for each label and
    # drop older repeats, so the sidebar is a clean category list.
    categories: list[dict] = []
    seen_labels: set[str] = set()
    for run in ordered:
        label = _label(run)
        if label in seen_labels:
            continue
        seen_labels.add(label)
        run["generated_display"] = _format_generated(run.get("generated_at"))
        run["label"] = label
        categories.append(run)

    # Stable, unique anchor per category (index prefix avoids slug collisions).
    for i, run in enumerate(categories):
        run["anchor"] = f"sec{i + 1}-{_slug(run['label'])}"

    ordered = categories

    site_title = config.settings().get("site_title", "Research Radar")
    site_owner = config.settings().get("site_owner", "Research Radar")

    template = _env.get_template("index.html.j2")
    html = template.render(
        runs=ordered,
        site_title=site_title,
        site_owner=site_owner,
    )

    index_path = out_dir / "index.html"
    index_path.write_text(html, encoding="utf-8")
    return index_path


SAMPLE = [
    {
        "mode": "topic",
        "query": "CRISPR base editing",
        "generated_at": "2026-06-20T15:00:00Z",
        "count": 3,
        "items": [
            {
                "title": "Improved adenine base editors with reduced off-target activity",
                "summary": (
                    "Researchers report a redesigned adenine base editor that lowers "
                    "off-target edits while keeping on-target efficiency high in human cells."
                ),
                "why_notable": None,
                "authors": ["A. Author", "B. Author"],
                "venue": "Nature",
                "published": "2026-05-12",
                "doi": "10.1038/s41586-026-00000-0",
                "arxiv_id": None,
                "url": "https://doi.org/10.1038/s41586-026-00000-0",
                "citation": "A. Author, B. Author et al. Improved adenine base editors with reduced off-target activity. Nature. 2026",
                "source_api": "openalex",
                "is_preprint": False,
                "abstract_available": True,
            },
            {
                "title": "A survey of delivery vehicles for in vivo base editing",
                "summary": None,
                "why_notable": None,
                "authors": ["C. Writer"],
                "venue": "Journal of Gene Medicine",
                "published": "2026-04-03",
                "doi": "10.1002/jgm.00000",
                "arxiv_id": None,
                "url": "https://doi.org/10.1002/jgm.00000",
                "citation": "C. Writer et al. A survey of delivery vehicles for in vivo base editing. Journal of Gene Medicine. 2026",
                "source_api": "openalex",
                "is_preprint": False,
                "abstract_available": False,
            },
            {
                "title": "Compact prime editors engineered for AAV delivery",
                "summary": (
                    "A preprint describes shrunken prime editor variants that fit within "
                    "adeno-associated virus packaging limits, broadening therapeutic reach."
                ),
                "why_notable": None,
                "authors": ["D. Scholar", "E. Scholar"],
                "venue": "bioRxiv",
                "published": "2026-06-01",
                "doi": None,
                "arxiv_id": None,
                "url": "https://www.biorxiv.org/content/10.1101/2026.06.01.000000v1",
                "citation": "D. Scholar, E. Scholar et al. Compact prime editors engineered for AAV delivery. bioRxiv. 2026",
                "source_api": "biorxiv",
                "is_preprint": True,
                "abstract_available": True,
            },
        ],
    }
]


if __name__ == "__main__":
    path = render_site(SAMPLE)
    print(f"Wrote {path}")
