# Research Radar: rules for the coding agent

PRIME DIRECTIVE: only real citations, never invent anything.

- The model writes prose summaries only. It never emits a URL, DOI, author, venue,
  date, or number. Code assembles all citations from structured API fields.
- A DOI is allowed only if it came from a structured search result or passed
  validate_doi() against Crossref. No exceptions.
- If an abstract is missing, do not summarize. Mark "abstract unavailable."
- Store provenance (the API fields used) for every record.
- A code-side post-check blanks any summary containing http, doi, or a DOI pattern.

OTHER RULES

- No em dashes in code comments, generated copy, or docs.
- Dead sources and bad feeds are logged and skipped, never fatal.
- Abstracts are kept only in local data/. The public docs/ site shows the AI summary,
  metadata, and an outbound link, not the publisher's verbatim abstract.
- Model names live in config/models.yaml. Verify them in the Anthropic docs.
- Tests in tests/ enforce the prime directive. Do not mark a milestone done until the
  relevant tests pass.
