"""
Scout-only tools.
Goal: given a hackathon URL, describe the competitive field —
clusters, gaps, threats. No scoring, no rubric.
"""

import json
import logging
import re
import secrets
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

import storage
from agent import gemini_call, get_current_config
from tools_shared import fetch_page, enrich_project, write_project_description

logger = logging.getLogger(__name__)


# ── validate_hackathon_url ─────────────────────────────────────────────────────

def validate_hackathon_url(url: str) -> dict:
    """
    Quick heuristic check: fetch the URL and count submission links.
    No Gemini call — fast enough for a pre-flight check.
    Returns {"valid": bool, "submission_count": int, "error": str}.
    """
    try:
        html = fetch_page(url)
    except Exception as e:
        return {"valid": False, "submission_count": 0, "error": f"Could not reach the page: {str(e)[:120]}"}

    if not html:
        return {"valid": False, "submission_count": 0, "error": "The page returned no content."}

    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        abs_href = href if href.startswith("http") else urljoin(url, href)
        if any(pat.search(abs_href) for pat in _SUBMISSION_LINK_PATTERNS):
            seen.add(abs_href)

    count = len(seen)
    if count == 0:
        return {
            "valid": False,
            "submission_count": 0,
            "error": (
                "No submissions found on this page. "
                "Please check that the URL points to a hackathon submissions page."
            ),
        }

    return {"valid": True, "submission_count": count, "error": ""}


# ── extract_projects_from_html ─────────────────────────────────────────────────

_SUBMISSION_LINK_PATTERNS = [
    re.compile(r"/submissions?/[\w][\w\-]+", re.I),
    re.compile(r"/projects?/[\w][\w\-]+", re.I),
    re.compile(r"/apps?/[\w][\w\-]+", re.I),
    re.compile(r"/hacks?/[\w][\w\-]+", re.I),
    re.compile(r"/teams?/[\w][\w\-]+", re.I),
    # lablab.ai: /team-<name>/<project-slug> or /project-<name>/<project-slug>
    re.compile(r"/team-[\w][\w\-]+/[\w][\w\-]+", re.I),
    re.compile(r"/project-[\w][\w\-]+/[\w][\w\-]+", re.I),
    # devpost: /software/<slug>
    re.compile(r"/software/[\w][\w\-]+", re.I),
]

_FLASH_EXTRACT_PROMPT = """\
You are a web scraper assistant.

Below is the HTML of a hackathon submissions page. Extract every project/submission listed.
For each one return:
  title        — project name (exact name, do not invent)
  team         — team or person name (empty string if not found)
  description  — raw description snippet from the page (empty string if not found)
  submission_url — absolute URL to the project's own page (empty string if not found)

IMPORTANT: Only extract what is actually present in the HTML. Do not invent project names, teams, or URLs.
If you cannot find any submissions, return an empty array [].

Return ONLY a JSON array. No markdown. Example:
[{{"title":"...", "team":"...", "description":"...", "submission_url":"https://..."}}]

Base URL (use to resolve relative links): {base_url}

HTML (truncated to first 100 000 chars):
{html}
"""


def extract_projects_from_html(html: str, base_url: str) -> list[dict]:
    """
    Two-pass: fast anchor-tag heuristics first, then Gemini Flash on the HTML.
    Returns [{title, team, description, submission_url}].
    Raises RuntimeError if 0 projects found (fail loudly, never hallucinate).
    """
    soup = BeautifulSoup(html, "html.parser")
    heuristic = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        abs_href = href if href.startswith("http") else urljoin(base_url, href)
        if any(pat.search(abs_href) for pat in _SUBMISSION_LINK_PATTERNS):
            if abs_href not in seen:
                seen.add(abs_href)
                # Title: prefer an h tag inside the anchor, then h tag in parent, then anchor text
                h_in_a = a.find(re.compile(r"h[1-6]"))
                title = ""
                if h_in_a:
                    title = h_in_a.get_text(strip=True)
                if not title:
                    parent = a.find_parent(["article", "li", "div"])
                    if parent:
                        h_in_parent = parent.find(re.compile(r"h[1-6]"))
                        if h_in_parent:
                            title = h_in_parent.get_text(strip=True)
                if not title:
                    title = a.get_text(separator=" ", strip=True)

                # Description: p tag inside anchor first, then parent
                desc = ""
                p_in_a = a.find("p")
                if p_in_a:
                    desc = p_in_a.get_text(strip=True)[:300]
                elif not desc:
                    parent = a.find_parent(["article", "li", "div"])
                    if parent:
                        p_el = parent.find("p")
                        if p_el:
                            desc = p_el.get_text(strip=True)[:300]

                heuristic.append({
                    "title": title[:120],
                    "team": "",
                    "description": desc,
                    "submission_url": abs_href,
                })

    if len(heuristic) >= 3:
        logger.info(f"extract_projects: heuristic found {len(heuristic)} entries")
        return heuristic

    # Fall back to Gemini Flash
    logger.info("extract_projects: heuristic found <3; using Gemini Flash")
    prompt = _FLASH_EXTRACT_PROMPT.format(html=html[:100_000], base_url=base_url)
    raw = gemini_call(prompt, model_tier="fast", response_mime_type="application/json")
    try:
        projects = json.loads(raw)
        for p in projects:
            url = p.get("submission_url", "")
            if url and not url.startswith("http"):
                p["submission_url"] = urljoin(base_url, url)
        if not projects:
            raise RuntimeError("Gemini Flash extraction returned 0 projects")
        logger.info(f"extract_projects: Gemini Flash found {len(projects)} entries")
        return projects
    except json.JSONDecodeError as exc:
        logger.error(f"Flash project extraction JSON parse failed: {exc}")

    raise RuntimeError(
        f"extract_projects_from_html: 0 projects found from {base_url}. "
        "The page DOM may have changed. Do not invent submissions."
    )


# ── cluster_projects ───────────────────────────────────────────────────────────

_CLUSTER_PROMPT = """\
You are the Verdict court's chief analyst.

Below is a JSON list of hackathon projects (each with title, ai_description, tech_stack, tracks).
Group them into 4-7 thematic clusters. Be specific — not 'AI Tools' but 'RAG wrappers', 'Voice agents', etc.

Return ONLY this JSON (no markdown):
{{
  "clusters": {{
    "c1": {{"label": "RAG WRAPPERS", "project_ids": ["p_..."]}},
    "c2": ...
  }}
}}

Projects:
{projects}
"""


def cluster_projects(projects: list[dict]) -> dict:
    # Give each project a stable ID
    for p in projects:
        p.setdefault("id", "p_" + secrets.token_urlsafe(3))

    slim = [
        {"id": p["id"], "title": p.get("title"), "ai_description": p.get("ai_description"), "tech_stack": p.get("tech_stack", []), "tracks": p.get("tracks", [])}
        for p in projects
    ]
    prompt = _CLUSTER_PROMPT.format(projects=json.dumps(slim, ensure_ascii=False)[:20_000])
    raw = gemini_call(prompt, model_tier="reasoning", response_mime_type="application/json")
    try:
        result = json.loads(raw)
        clusters = result.get("clusters", result)
        # Stamp cluster label onto each project
        for cid, c in clusters.items():
            for pid in c.get("project_ids", []):
                for p in projects:
                    if p.get("id") == pid:
                        p["cluster"] = cid
                        break
        return clusters
    except Exception as exc:
        logger.error(f"cluster_projects failed: {exc}")
        return {}


# ── identify_gaps ──────────────────────────────────────────────────────────────

_GAPS_PROMPT = """\
You are a venture judge surveying a hackathon field.

Projects by cluster:
{clusters_summary}

Identify 3-5 significant gaps — valuable problems nobody is building here.
Be judicial, not cheerful. Each gap should feel like an indictment.

Return ONLY a JSON array (no markdown):
[{{"headline": "No one is building ...", "reasoning": "..."}}]
"""


def identify_gaps(projects: list[dict], clusters: dict) -> list[dict]:
    cluster_summary = {
        cid: {
            "label": c.get("label"),
            "projects": [p.get("title") for p in projects if p.get("cluster") == cid][:8],
        }
        for cid, c in clusters.items()
    }
    prompt = _GAPS_PROMPT.format(clusters_summary=json.dumps(cluster_summary, ensure_ascii=False))
    raw = gemini_call(prompt, model_tier="reasoning", response_mime_type="application/json")
    try:
        return json.loads(raw)
    except Exception:
        return [{"headline": "The court finds many gaps.", "reasoning": "Analysis unavailable."}]


# ── identify_threats ───────────────────────────────────────────────────────────

_THREATS_PROMPT = """\
You are a competition judge. From this list of projects, identify the top 5 most polished,
ambitious, or technically impressive — the ones the court would consider genuine threats.

Projects (JSON):
{projects}

Return ONLY a JSON array (no markdown):
[{{"project_id": "p_...", "reasoning": "One dry, judicial sentence."}}]
"""


def identify_threats(projects: list[dict]) -> list[dict]:
    slim = [{"id": p.get("id"), "title": p.get("title"), "ai_description": p.get("ai_description"), "verdict_line": p.get("verdict_line"), "tracks": p.get("tracks", [])} for p in projects[:40]]
    prompt = _THREATS_PROMPT.format(projects=json.dumps(slim, ensure_ascii=False))
    raw = gemini_call(prompt, model_tier="reasoning", response_mime_type="application/json")
    try:
        return json.loads(raw)
    except Exception:
        return []


# ── pick_favorite ──────────────────────────────────────────────────────────────

_FAVORITE_PROMPT = """\
You are the Verdict court's final arbiter.

Projects, gaps, and clusters are below. Pick the dark-horse project most likely to matter —
not the most popular, but the most interesting. Explain your reasoning in the court's judicial voice.

Projects: {projects}
Gaps: {gaps}

Return ONLY this JSON (no markdown):
{{"project_id": "p_...", "reasoning": "1-2 judicial sentences on why this project matters."}}
"""


def pick_favorite(projects: list[dict], clusters: dict, gaps: list[dict]) -> dict:
    slim_projects = [{"id": p.get("id"), "title": p.get("title"), "ai_description": p.get("ai_description"), "verdict_line": p.get("verdict_line")} for p in projects[:40]]
    prompt = _FAVORITE_PROMPT.format(
        projects=json.dumps(slim_projects, ensure_ascii=False),
        gaps=json.dumps(gaps, ensure_ascii=False),
    )
    raw = gemini_call(prompt, model_tier="reasoning", response_mime_type="application/json")
    try:
        fav = json.loads(raw)
        # Resolve project_id → full record
        fav_id = fav.get("project_id")
        for p in projects:
            if p.get("id") == fav_id:
                fav["project"] = p
                fav["name"] = p.get("title", "")
                fav["team"] = p.get("team", "")
                fav["ai"] = p.get("ai_description", "")
                fav["links"] = p.get("links", {})
                fav["tracks"] = p.get("tracks", [])
                fav["reason"] = fav.get("reasoning", "")
                break
        return fav
    except Exception as exc:
        logger.error(f"pick_favorite failed: {exc}")
        return {"project_id": None, "reasoning": "The court is undecided."}


# ── write_scout_report ─────────────────────────────────────────────────────────

def write_scout_report(
    source_url: str,
    projects: list[dict],
    clusters: dict,
    gaps: list[dict],
    threats: list[dict],
    favorite: dict,
) -> str:
    """Save and return verdict ID."""
    verdict_id = storage.new_verdict_id()

    # Build frontend-compatible cluster structure
    frontend_clusters = {}
    for cid, c in clusters.items():
        frontend_clusters[cid] = {
            "label": c.get("label", cid.upper()),
            "project_ids": c.get("project_ids", []),
        }

    cfg = get_current_config()
    report = {
        "id": verdict_id,
        "type": "scout",
        "source_url": source_url,
        "created_at": storage.now_iso(),
        "ts": storage.now_ts(),
        "field": _domain_label(source_url),
        "count": len(projects),
        "projects": projects,
        "clusters": frontend_clusters,
        "gaps": [g.get("headline", str(g)) if isinstance(g, dict) else str(g) for g in gaps],
        "threats": threats,
        "favorite": favorite,
        "models_used": {"reasoning": cfg.reasoning, "fast": cfg.fast},
    }

    storage.save_verdict(verdict_id, report)
    logger.info(f"Scout report saved: {verdict_id}")
    return verdict_id


def _domain_label(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "").title() + " Hackathon"
    except Exception:
        return "Hackathon"


# ── Tool map for the Scout agent ───────────────────────────────────────────────

SCOUT_TOOLS_MAP = {
    "fetch_page": fetch_page,
    "extract_projects_from_html": extract_projects_from_html,
    "enrich_project": enrich_project,
    "write_project_description": write_project_description,
    "cluster_projects": cluster_projects,
    "identify_gaps": identify_gaps,
    "identify_threats": identify_threats,
    "pick_favorite": pick_favorite,
    "write_scout_report": write_scout_report,
}

# ── Scout system prompt ────────────────────────────────────────────────────────

SCOUT_SYSTEM_PROMPT = """\
You are Verdict's Scout agent — an autonomous competitive intelligence system.

Your mission: given a hackathon URL, produce a complete field report.

Process:
1. fetch_page(url) to get the submissions listing HTML
2. extract_projects_from_html(html, base_url) to get shallow project records
3. For every project: enrich_project(project) then write_project_description(project)
   — do these in a loop, one project at a time
4. cluster_projects(all_enriched_projects) to theme-group them
5. identify_gaps(projects, clusters)
6. identify_threats(projects)
7. pick_favorite(projects, clusters, gaps)
8. write_scout_report(source_url, projects, clusters, gaps, threats, favorite)
   — this saves the report and returns the verdict ID

Important:
— Enrich and describe every project before clustering. Do not skip any.
— Cap at 50 projects if the field is very large — take a representative sample.
— Tone: solemn, judicial, deliberate. No cheerfulness, no hedging.
— The court rules. It does not suggest.
— CRITICAL: You may NEVER invent projects, teams, URLs, or details. If extract_projects_from_html
  raises an error or returns 0 entries, report "scrape failed" and stop. Do not fabricate submissions.

Thought style (use in every step):
→ summoning submissions from the field…
→ 47 contenders identified
→ enriching the record for [Project Name]
→ clustering by theme…
→ weighing the evidence…
→ the ruling is ready
"""
