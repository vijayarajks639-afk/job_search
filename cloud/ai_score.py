"""
Live AI fit-scoring for the public cloud demo — Anthropic API (Haiku).

The local pipeline scores jobs with the `claude -p` CLI, which can't run on
Streamlit Community Cloud. For the public demo we score ONE posting at a time
against the visitor's uploaded resume via the Anthropic API, using the cheapest
capable model and a tight token budget. Spend is bounded by the caps in
cloud/usage.py (daily / monthly / per-session) and by the UI requiring an
explicit "Analyze my fit" click per posting.

PRIVACY: resume text is passed in memory only. Nothing here writes it to disk or
logs it; callers log only the resulting company/fit number.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import config
from sources.base import JobPosting

# Exact dated id (alias "claude-haiku-4-5" also resolves) — cheapest capable tier.
MODEL = "claude-haiku-4-5"
MAX_TOKENS = 700

# Bound input tokens: trim resume + posting description before sending.
_RESUME_CHARS = 6000
_DESC_CHARS = 1500

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "cloud_score_prompt.md"


def _build_prompt(resume_text: str, posting: JobPosting) -> str:
    template = _PROMPT_PATH.read_text(encoding="utf-8")
    posting_block = (
        f"Company: {posting.company}\n"
        f"Title: {posting.title}\n"
        f"Location: {posting.location or 'India'}\n"
        f"Posted: {posting.posted_date or 'unknown'}\n"
        f"Description:\n{(posting.description or '')[:_DESC_CHARS]}"
    )
    return (template
            .replace("{RESUME}", resume_text[:_RESUME_CHARS])
            .replace("{POSTING}", posting_block))


def _parse_json(text: str) -> dict:
    """Defensively extract the JSON object from the model response."""
    text = text.strip()
    # Strip ```json fences if the model added them despite instructions.
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in model response")
    return json.loads(text[start:end + 1])


def _normalize(raw: dict) -> dict:
    """Coerce model output into the shape the dashboard/cloud renderer expects."""
    hats = raw.get("three_hats") or {}
    def hat(key):
        h = hats.get(key) or {}
        return {"verdict": str(h.get("verdict", "")).lower(),
                "reason": str(h.get("reason", ""))}
    try:
        score = int(round(float(raw.get("fit_score", 0))))
    except (TypeError, ValueError):
        score = 0
    return {
        "fit_score": max(0, min(100, score)),
        "rationale": str(raw.get("rationale", "")),
        "three_hats": {
            "hr_director": hat("hr_director"),
            "hiring_manager": hat("hiring_manager"),
            "recruiter": hat("recruiter"),
        },
        "emphasize": [str(x) for x in (raw.get("emphasize") or [])][:5],
        "gaps": [str(x) for x in (raw.get("gaps") or [])][:5],
    }


def score_posting(resume_text: str, posting: JobPosting) -> dict:
    """
    Score one posting against the resume. Returns the normalized dict above.
    Raises on missing key / API error / unparseable response so the caller can
    show a friendly message (and NOT consume quota on hard failure).
    """
    if not config.AI_SCORING_ENABLED:
        raise RuntimeError("AI scoring is not configured (no ANTHROPIC_API_KEY).")

    import anthropic  # imported lazily so the app loads without the SDK/key

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": _build_prompt(resume_text, posting)}],
    )
    text = "".join(block.text for block in msg.content if block.type == "text")
    return _normalize(_parse_json(text))
