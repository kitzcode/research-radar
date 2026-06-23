"""Grounded triage and summarization, plus the code-side grounding backstop.

The model is given only the title and abstract text. It writes prose only. A
hard post-check (enforce_grounding) blanks any summary that leaks a URL, a DOI,
or a DOI-shaped string. This is the last line of defense for the prime directive.
"""
from __future__ import annotations

import json
import logging
import re

from . import llm
from .citations import DOI_RE
from .normalize import Paper

log = logging.getLogger("radar.summarize")


# ---------------------------------------------------------------------------
# Prompt contracts (kept verbatim, do not let the model emit identifiers).
# ---------------------------------------------------------------------------

TRIAGE_SYSTEM = (
    "You are a relevance filter for a research paper digest. You will receive a paper's\n"
    "title and abstract and a topic. Decide whether the paper is genuinely about the topic.\n"
    "Respond with a single JSON object and nothing else:\n"
    '{"relevant": true|false, "reason": "<10 words or fewer>"}\n'
    "Do not add any other text. Do not invent details about the paper. Judge only from the\n"
    "title and abstract provided."
)

SUMMARY_SYSTEM = (
    "You summarize a single research paper for a knowledgeable reader. You will be given the\n"
    "paper's title and its abstract. Write a clear summary of 3 to 5 sentences covering: what\n"
    "the paper studied, what they did, and what they found or claim.\n"
    "Hard rules:\n"
    "- Use only information present in the title and abstract provided. Add nothing else.\n"
    "- Do not state any number, statistic, author name, institution, date, journal, or\n"
    "  citation. Those are handled elsewhere. Write prose about the science only.\n"
    "- Do not include any URL, DOI, or reference.\n"
    "- If the abstract is too thin to summarize, say so in one sentence rather than guessing.\n"
    "Write only the summary text, no preamble, no headings."
)

WHY_NOTABLE_SYSTEM = (
    "You will be given the editors' framing text for a research story (the headline and\n"
    "blurb a journal's news section wrote about a paper). In one or two sentences, say why\n"
    "this work is getting attention, based only on that framing text.\n"
    "Hard rules:\n"
    "- Use only the framing text provided. Add no facts of your own.\n"
    "- Do not state any number, author name, institution, date, journal, URL, or DOI.\n"
    "- This is the editors' framing, not verified fact. Write only the one or two sentences."
)


def enforce_grounding(text: str | None) -> str | None:
    """Code-side post-check. Blank a summary that leaks an identifier.

    Returns the text unchanged when clean, or None when it contains http, the
    token doi, or a DOI-shaped string. A blanked summary is logged. This is a
    hard backstop for the prime directive and is not trusted to the model.
    """
    if not text:
        return None
    low = text.lower()
    if "http" in low or "doi" in low or DOI_RE.search(text):
        log.warning("summary blanked by grounding post-check (leaked identifier)")
        return None
    return text


def _parse_triage(raw: str) -> dict:
    """Parse the triage JSON defensively. Fall back to not-relevant on failure."""
    if not raw:
        return {"relevant": False, "reason": "empty triage response"}
    cleaned = raw.strip()
    # Strip code fences if the model wrapped the JSON.
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    # Grab the first {...} block if there is surrounding prose.
    m = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if m:
        cleaned = m.group(0)
    try:
        obj = json.loads(cleaned)
        return {
            "relevant": bool(obj.get("relevant", False)),
            "reason": str(obj.get("reason", ""))[:120],
        }
    except (ValueError, AttributeError):
        log.warning("could not parse triage JSON: %r", raw[:200])
        return {"relevant": False, "reason": "unparseable triage response"}


def triage(paper: Paper, topic: str) -> Paper:
    """Mark a paper relevant or not for the topic, from title + abstract only.

    A paper with no abstract is judged on the title alone (abstract sent as a
    short note). Sets paper.relevant and paper.relevance_reason.
    """
    abstract = paper.abstract or "(no abstract available)"
    user = f"Topic: {topic}\n\nTitle: {paper.title}\n\nAbstract: {abstract}"
    raw = llm.call(llm.triage_model(), TRIAGE_SYSTEM, user, llm.max_tokens_triage())
    verdict = _parse_triage(raw)
    paper.relevant = verdict["relevant"]
    paper.relevance_reason = verdict["reason"]
    return paper


def summarize_paper(paper: Paper) -> Paper:
    """Summarize from title + abstract only. Never summarize a missing abstract.

    If the abstract is None, the summary stays None (the record renders as
    "abstract unavailable"). The summary is passed through enforce_grounding.
    """
    if not paper.abstract:
        paper.summary = None
        return paper
    user = f"Title: {paper.title}\n\nAbstract: {paper.abstract}"
    raw = llm.call(llm.summary_model(), SUMMARY_SYSTEM, user, llm.max_tokens_summary())
    paper.summary = enforce_grounding(raw)
    return paper


def summarize_why_notable(paper: Paper, framing_text: str) -> Paper:
    """Big-story mode only. Derive a short why-notable note from feed framing.

    framing_text is the journal news headline plus blurb. The model is told this
    is the editors' framing and may not add facts. Passed through the same
    grounding post-check.
    """
    if not framing_text or not framing_text.strip():
        paper.why_notable = None
        return paper
    raw = llm.call(
        llm.summary_model(), WHY_NOTABLE_SYSTEM, framing_text.strip(),
        llm.max_tokens_summary(),
    )
    paper.why_notable = enforce_grounding(raw)
    return paper
