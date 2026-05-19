"""
Judgment-only tools.
Goal: given a rubric and submissions, score each against the rubric and produce a ranked leaderboard.

Three ingestion paths:
  ingest_from_hackathon_url — scrape + extract
  ingest_from_file          — CSV / JSON / MD / TXT / PDF
  ingest_from_text          — freeform text → Flash parse
"""

import json
import logging
import secrets
from pathlib import Path

import storage
from agent import gemini_call, get_current_config
from tools_shared import fetch_page, enrich_project, write_project_description

logger = logging.getLogger(__name__)


# ── Ingestion — hackathon URL ──────────────────────────────────────────────────

def ingest_from_hackathon_url(url: str) -> list[dict]:
    """Reuse Scout's fetch + extract pipeline."""
    from tools_scout import extract_projects_from_html
    html = fetch_page(url)
    if not html:
        return []
    return extract_projects_from_html(html, url)


# ── Ingestion — uploaded file ──────────────────────────────────────────────────

_FLASH_PARSE_PROMPT = """\
Parse the following text into a JSON list of submission records.
Each record must have: title, team (empty string if unknown), description, submission_url (empty string if unknown).
Return ONLY the JSON array, no markdown.

Text:
{text}
"""


def _flash_parse(text: str) -> list[dict]:
    prompt = _FLASH_PARSE_PROMPT.format(text=text[:40_000])
    raw = gemini_call(prompt, model_tier="fast", response_mime_type="application/json")
    try:
        return json.loads(raw)
    except Exception:
        return []


def ingest_from_file(file_id: str) -> list[dict]:
    path = storage.get_upload_path(file_id)
    if not path:
        return []

    ext = path.suffix.lower()

    if ext == ".csv":
        return _ingest_csv(path)
    elif ext == ".json":
        return _ingest_json(path)
    elif ext in (".md", ".txt"):
        return _flash_parse(path.read_text(encoding="utf-8", errors="replace"))
    elif ext == ".pdf":
        return _ingest_pdf(path)
    else:
        return _flash_parse(path.read_text(encoding="utf-8", errors="replace"))


def _ingest_csv(path: Path) -> list[dict]:
    import pandas as pd

    df = pd.read_csv(path, dtype=str).fillna("")
    cols = {c.lower(): c for c in df.columns}

    def pick(*candidates):
        for c in candidates:
            if c in cols:
                return cols[c]
        return None

    title_col = pick("title", "name", "project", "project name")
    team_col = pick("team", "author", "authors", "submitter")
    desc_col = pick("description", "summary", "abstract", "pitch")
    url_col = pick("url", "link", "submission", "submission_url")

    if not title_col:
        # No recognizable columns — treat whole CSV as freeform
        return _flash_parse(path.read_text(encoding="utf-8", errors="replace"))

    records = []
    for _, row in df.iterrows():
        records.append({
            "title": row.get(title_col, ""),
            "team": row.get(team_col, "") if team_col else "",
            "description": row.get(desc_col, "") if desc_col else "",
            "submission_url": row.get(url_col, "") if url_col else "",
        })
    return records


def _ingest_json(path: Path) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    # Try standard shapes
    if isinstance(raw, list):
        return raw
    for key in ("submissions", "data", "projects", "entries", "items"):
        if isinstance(raw, dict) and key in raw and isinstance(raw[key], list):
            return raw[key]
    # Fall back to Flash parse
    return _flash_parse(json.dumps(raw)[:40_000])


def _ingest_pdf(path: Path) -> list[dict]:
    try:
        import pypdf
        reader = pypdf.PdfReader(str(path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages[:20])
    except Exception as exc:
        logger.error(f"PDF extraction failed: {exc}")
        text = path.read_bytes().decode("utf-8", errors="replace")
    return _flash_parse(text)


# ── Ingestion — manual text ────────────────────────────────────────────────────

def ingest_from_text(text: str) -> list[dict]:
    return _flash_parse(text)


# ── score_submission ───────────────────────────────────────────────────────────

_SCORE_PROMPT = """\
You are the Verdict court's scoring engine.

Rubric:
{rubric}

Submission:
{submission}

Score this submission against each rubric criterion.
Be strict. Be specific. Use the judicial register — terse, deliberate, slightly arrogant.

Return ONLY this JSON (no markdown):
{{
  "overall_score": <sum of per-criterion scores>,
  "rubric_scores": [
    {{"criterion": "...", "weight": 30, "score": 22, "max": 30, "note": "One-line judicial note."}}
  ],
  "verdict_line": "One sentence verdict in judicial voice."
}}
"""


def score_submission(submission: dict, rubric: list[dict]) -> dict:
    slim_sub = {
        k: submission.get(k)
        for k in ("title", "team", "ai_description", "tracks", "tech_stack", "links")
        if submission.get(k)
    }
    prompt = _SCORE_PROMPT.format(
        rubric=json.dumps(rubric, ensure_ascii=False),
        submission=json.dumps(slim_sub, ensure_ascii=False),
    )
    raw = gemini_call(prompt, model_tier="reasoning", response_mime_type="application/json")
    try:
        scored = json.loads(raw)
        # Build a scores dict keyed by criterion name (for frontend mini-bars)
        scores_dict = {}
        notes_dict = {}
        for rs in scored.get("rubric_scores", []):
            key = rs["criterion"].lower().replace(" ", "_").replace("-", "_")
            scores_dict[key] = rs["score"]
            notes_dict[key] = rs.get("note", "")
        scored["scores"] = scores_dict
        scored["notes"] = notes_dict
        # Also put verdict_line onto the submission
        submission["verdict_line"] = scored.get("verdict_line", "")
        submission["verdict"] = scored.get("verdict_line", "")
        return scored
    except Exception as exc:
        logger.error(f"score_submission failed: {exc}")
        return {
            "overall_score": 0,
            "rubric_scores": [],
            "verdict_line": "The court could not evaluate this submission.",
            "scores": {},
            "notes": {},
        }


# ── rank_and_finalize ──────────────────────────────────────────────────────────

def rank_and_finalize(scored: list[dict], rubric: list[dict]) -> list[dict]:
    """
    scored: list of {submission: dict, overall_score: int, rubric_scores: [...], ...}
    Returns a leaderboard list sorted by score, with rank assigned.
    """
    # Flatten — each item should have a submission + score
    flat = []
    for item in scored:
        if isinstance(item, dict):
            score = item.get("overall_score", item.get("total", 0))
            submission = item.get("submission", item.get("project", item))
            flat.append({**item, "submission": submission, "overall_score": score})

    flat.sort(key=lambda x: x.get("overall_score", 0), reverse=True)

    leaderboard = []
    for rank, item in enumerate(flat, 1):
        sub = item.get("submission", {})
        entry = {
            "rank": rank,
            "name": sub.get("title", sub.get("name", "")),
            "team": sub.get("team", ""),
            "ai": sub.get("ai_description", ""),
            "tracks": sub.get("tracks", []),
            "links": sub.get("links", {}),
            "verdict": item.get("verdict_line", sub.get("verdict_line", "")),
            "scores": item.get("scores", {}),
            "notes": item.get("notes", {}),
            "total": item.get("overall_score", 0),
            "rubric_scores": item.get("rubric_scores", []),
            "project": sub,
        }
        leaderboard.append(entry)

    return leaderboard


# ── write_court_summary ────────────────────────────────────────────────────────

_SUMMARY_PROMPT = """\
You are the presiding judge of Verdict court.

Below is the final leaderboard of judged submissions.
Write one solemn judicial paragraph (4-6 sentences) summarising the ruling.
Name the winner and explain why. Note any patterns.
Tone: solemn, deliberate, slightly arrogant. No hedging.

Leaderboard (top 5):
{leaderboard}

Rubric:
{rubric}
"""


def write_court_summary(leaderboard: list[dict], rubric: list[dict]) -> str:
    top5 = [
        {"rank": e.get("rank"), "name": e.get("name"), "total": e.get("total"), "verdict": e.get("verdict")}
        for e in leaderboard[:5]
    ]
    prompt = _SUMMARY_PROMPT.format(
        leaderboard=json.dumps(top5, ensure_ascii=False),
        rubric=json.dumps(rubric, ensure_ascii=False),
    )
    return gemini_call(prompt, model_tier="reasoning")


# ── write_judgment_report ──────────────────────────────────────────────────────

def write_judgment_report(
    source_type: str,
    source_details: str,
    rules_raw: str,
    rubric: list[dict],
    leaderboard: list[dict],
    summary: str,
) -> str:
    verdict_id = storage.new_verdict_id()
    cfg = get_current_config()

    # Build frontend-compatible criteria list
    criteria = []
    for r in rubric:
        key = r["criterion"].lower().replace(" ", "_").replace("-", "_")
        criteria.append({
            "key": key,
            "name": r["criterion"],
            "weight": r.get("weight", 0),
            "description": r.get("description", ""),
        })

    report = {
        "id": verdict_id,
        "type": "judgment",
        "created_at": storage.now_iso(),
        "ts": storage.now_ts(),
        "source": {"type": source_type, "details": source_details},
        "rules_raw": rules_raw,
        "rubric": rubric,
        "criteria": criteria,
        "field": source_details[:80] if source_details else "Submitted Entries",
        "count": len(leaderboard),
        "bench": leaderboard,
        "leaderboard": leaderboard,
        "summary": summary,
        "models_used": {"reasoning": cfg.reasoning, "fast": cfg.fast},
    }

    storage.save_verdict(verdict_id, report)
    logger.info(f"Judgment report saved: {verdict_id}")
    return verdict_id


# ── Tool map for the Judgment agent ───────────────────────────────────────────

JUDGMENT_TOOLS_MAP = {
    "parse_rules": __import__("tools_shared", fromlist=["parse_rules"]).parse_rules,
    "ingest_from_hackathon_url": ingest_from_hackathon_url,
    "ingest_from_file": ingest_from_file,
    "ingest_from_text": ingest_from_text,
    "fetch_page": fetch_page,
    "enrich_project": enrich_project,
    "write_project_description": write_project_description,
    "score_submission": score_submission,
    "rank_and_finalize": rank_and_finalize,
    "write_court_summary": write_court_summary,
    "write_judgment_report": write_judgment_report,
}

# ── Judgment system prompt ─────────────────────────────────────────────────────

JUDGMENT_SYSTEM_PROMPT = """\
You are Verdict's Judgment agent — an autonomous ranking and scoring system.

Your mission: given a rubric and a set of submissions, score each one and produce a ranked leaderboard.

Process:
1. parse_rules(rules_text) — parse the rubric first, always. Even if empty.
2. Ingest submissions using exactly one of:
   — ingest_from_hackathon_url(url)  if source_type is "hackathon_url"
   — ingest_from_file(file_id)       if source_type is "uploaded_file"
   — ingest_from_text(text)          if source_type is "manual_text"
3. For EVERY submission: enrich_project(submission) then write_project_description(submission)
   — enrich ALL submissions before scoring any.
4. For EVERY enriched submission: score_submission(submission, rubric)
5. rank_and_finalize(all_scored_submissions, rubric)
6. write_court_summary(leaderboard, rubric)
7. write_judgment_report(source_type, source_details, rules_raw, rubric, leaderboard, summary)

Important:
— Enrich all submissions first. Then score all. Do not interleave enrich and score.
— If a submission has no URL, enrich step is a no-op — still call it.
— Cap at 30 submissions if the field is very large.
— Tone: solemn, judicial. No hedging.
— CRITICAL: You may NEVER invent projects, teams, scores, or details. Only score what was ingested.
  If ingestion returns 0 entries, report "ingestion failed" and stop. Do not fabricate submissions.

Thought style:
→ parsing the rules of judgment…
→ summoning submissions from the field…
→ enriching the record for [Project Name]
→ scoring [Project Name] against the rubric
→ weighing the evidence…
→ the ruling is ready
"""
