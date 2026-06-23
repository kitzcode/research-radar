# Research Radar

An AI agent that reads and summarizes research papers from their real abstracts,
in two modes:

1. Topic mode (on demand): give it a topic, it retrieves recent relevant papers,
   summarizes each from its real abstract, and lists them.
2. Big-story mode (scheduled): it watches Nature and Science news feeds, finds the
   primary research papers those write-ups are about, and summarizes them with a
   short "why it got attention" note.

Output is written to JSON, a markdown archive, and a static site for GitHub Pages.
Design is light teal on white.

## Prime directive: only real citations, never invent anything

This is the rule everything else is built around. See `CLAUDE.md` for the full
contract. In short:

- The model writes prose summaries only. It never emits a URL, DOI, author, venue,
  date, or number. All identifiers and citation strings are assembled in Python
  from structured API fields (`radar/citations.py`).
- A DOI is trusted only if it came from a structured search result or passed
  `validate_doi()` against Crossref.
- If an abstract is missing, the record is marked "abstract unavailable" and never
  summarized.
- A code-side post-check (`summarize.enforce_grounding`) blanks any summary that
  contains http, doi, or a DOI-shaped string. This is a hard backstop.
- Provenance (the API fields used) is stored on every record.

The test suite in `tests/` enforces these properties.

## Install

```
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then add your ANTHROPIC_API_KEY
```

## Usage

```
# Topic mode (needs ANTHROPIC_API_KEY for triage + summaries)
python -m radar topic "CRISPR base editing" --since 2025-01-01 --n 12

# Run retrieval and assembly only, no API key needed (data pipeline check)
python -m radar topic "CRISPR base editing" --no-llm

# Big-story mode (weekly cron also runs this)
python -m radar bigstory [--ignore-seen]

# Re-render docs/ from saved public runs
python -m radar render

# Add -v for info-level logs on any command.
```

Topic and big-story modes call the Anthropic API. The data layer (retrieval,
normalization, citations, dedupe, site render) runs without a key via `--no-llm`.

## Data sources

Topic mode queries OpenAlex, arXiv, and Europe PMC (all free, no key). Crossref is
used to validate DOIs and as an abstract fallback. Springer Nature Meta is an
optional abstract source for Nature-family DOIs (set `SPRINGER_API_KEY` to enable,
skipped gracefully otherwise). All endpoints were confirmed live during the build.
Europe PMC field names (`abstractText`, `authorList`, `journalInfo.journal.title`,
`firstPublicationDate`) were verified against a live response.

Big-story feeds live in `config/feeds.yaml`. The Nature flagship and Science News
feeds were verified live. The dedicated Nature News RSS path returns 404 and is
omitted; the flagship feed already carries Nature news items. The feed fetcher
fails closed: a feed that does not parse or has no entries is logged and skipped,
never fabricated.

## Configuration

- `config/models.yaml`: model ids and token limits. Verify ids at docs.claude.com.
- `config/sources.yaml`: which sources are active and the per-source result cap.
- `config/feeds.yaml`: big-story feed URLs.
- `config/settings.yaml`: contact email (used in User-Agent and OpenAlex mailto),
  default lookback window, site title and owner.

## Tests

```
python -m pytest tests/ -q
```

The tests use recorded fixtures and a mocked model, so they run offline without an
API key. They check: summaries carry no identifiers and the post-check blanks a
leaky one; every output item has a traceable identifier; DOI validation gates
regex-extracted DOIs; and a missing abstract is never summarized and renders as
"abstract unavailable."

## GitHub Pages

The site renders into `docs/`. To publish: Settings, Pages, Source = Deploy from a
branch, branch = main, folder = /docs. The public site shows the AI summary,
metadata, and an outbound link to the DOI. It does not republish the publisher's
verbatim abstract; raw abstracts stay in local `data/` (gitignored) for your own
reading.

## Automation

- `.github/workflows/digest.yml`: weekly cron for big-story mode, commits results.
- `.github/workflows/topic.yml`: manual dispatch with a topic input.

Both read `ANTHROPIC_API_KEY` (and optional `SPRINGER_API_KEY`) from repo secrets.
