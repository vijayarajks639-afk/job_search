"""
Agentic search + match engine.

Builds a single prompt from the resume, the GCC target list, the seed roles
(already fetched by fetch_jobs.py) and any referral contacts, then runs Claude
Code headless (`claude -p`) with web search to source recent India roles, score
fitment (three hats), and draft honest tailoring + referral notes.

Output: data/jobs_matched/matched_<ts>.json

Usage:
    python agent_run.py [--seed-file data/jobs_raw/seeds_X.json] [--model sonnet]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

import config


def _latest_seed_file():
    files = sorted(config.JOBS_RAW_DIR.glob("seeds_*.json"))
    return files[-1] if files else None


def _load_seeds(seed_file) -> list[dict]:
    if seed_file is None:
        return []
    data = json.loads(seed_file.read_text(encoding="utf-8"))
    seeds = []
    for p in data.get("postings", []):
        seeds.append({
            "company": p.get("company"),
            "title": p.get("title"),
            "location": p.get("location"),
            "url": p.get("url"),
            "posted_date": p.get("posted_date"),
            "source": p.get("source"),
            # keep JD short to control token usage
            "description": (p.get("description") or "")[:600],
        })
    return seeds


def _load_contacts() -> list[dict]:
    if not config.CONTACTS_CSV.exists():
        return []
    with config.CONTACTS_CSV.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_prompt() -> str:
    template = config.MATCH_PROMPT.read_text(encoding="utf-8")
    resume = config.MASTER_RESUME.read_text(encoding="utf-8")
    gcc = config.ROOT.joinpath("gcc_targets.md").read_text(encoding="utf-8")
    seeds = _load_seeds(_latest_seed_file())
    contacts = _load_contacts()

    return (template
            .replace("{RESUME}", resume)
            .replace("{GCC_LIST}", gcc)
            .replace("{SEED_JOBS}", json.dumps(seeds, ensure_ascii=False, indent=2) or "[]")
            .replace("{CONTACTS}", json.dumps(contacts, ensure_ascii=False) or "[]")
            .replace("{TODAY}", datetime.now().date().isoformat())
            .replace("{RECENT_DAYS}", str(config.RECENT_DAYS))
            .replace("{FIT_THRESHOLD}", str(config.FIT_THRESHOLD)))


def _extract_json(text: str) -> dict:
    """
    Extract the first JSON object from the agent's reply, tolerating code fences
    and any prose before/after it. raw_decode stops at the end of the first valid
    object, so trailing notes ("Extra data") no longer break parsing.
    """
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
        t = re.sub(r"\n?```\s*$", "", t).strip()
    start = t.find("{")
    if start == -1:
        raise ValueError("no JSON object found in agent output")
    obj, _ = json.JSONDecoder().raw_decode(t[start:])
    return obj


def _invoke_claude(claude: str, prompt: str, model: str, timeout: int) -> dict:
    # WebSearch only (no WebFetch) — prevents per-page crawling that bloats turns
    # and triggers long-run socket drops.
    cmd = [claude, "-p",
           "--output-format", "json",
           "--allowedTools", "WebSearch",
           "--permission-mode", "bypassPermissions",
           "--model", model]
    proc = subprocess.run(cmd, input=prompt, capture_output=True,
                          text=True, encoding="utf-8", errors="replace",
                          timeout=timeout)
    if proc.returncode != 0 and not proc.stdout:
        raise RuntimeError(f"claude exited {proc.returncode}: {proc.stderr[:500]}")
    return json.loads(proc.stdout)


def run_agent(model: str, timeout: int = 600) -> dict:
    claude = shutil.which("claude")
    if not claude:
        raise RuntimeError("`claude` CLI not found on PATH.")

    prompt = build_prompt()
    envelope = _invoke_claude(claude, prompt, model, timeout)

    # Retry once on transient API/socket errors (long agentic runs occasionally drop).
    if envelope.get("is_error") and "API Error" in str(envelope.get("result", "")):
        envelope = _invoke_claude(claude, prompt, model, timeout)

    if envelope.get("is_error"):
        raise RuntimeError(f"claude reported error: {str(envelope.get('result'))[:500]}")
    result_text = envelope.get("result", "")
    # Persist raw output for debugging (overwritten each run).
    (config.LOGS_DIR / "last_agent_output.txt").write_text(result_text, encoding="utf-8")
    payload = _extract_json(result_text)
    # Web searches run via a sub-model, so sum per-model counts (top-level is 0).
    searches = sum(mu.get("webSearchRequests", 0)
                   for mu in envelope.get("modelUsage", {}).values())
    payload["_meta"] = {
        "model": model,
        "cost_usd": envelope.get("total_cost_usd"),
        "duration_ms": envelope.get("duration_ms"),
        "web_searches": searches,
    }
    return payload


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args()

    config.ensure_dirs()
    payload = run_agent(args.model, args.timeout)

    matches = payload.get("matches", [])
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = config.JOBS_MATCHED_DIR / f"matched_{ts}.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    top = [m for m in matches if m.get("fit_score", 0) >= config.FIT_THRESHOLD]
    print(f"Agent returned {len(matches)} matches ({len(top)} >= fit {config.FIT_THRESHOLD}).")
    print(f"  cost~${payload['_meta'].get('cost_usd')}, "
          f"web_searches={payload['_meta'].get('web_searches')}")
    print(f"Wrote {out}")
    for m in matches[:10]:
        print(f"  [{m.get('fit_score')}] {m.get('company')} — {m.get('title')}")


if __name__ == "__main__":
    main()
