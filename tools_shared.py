"""
Shared tools used by both Scout and Judgment agents.
  fetch_page            — requests + BS4, Playwright fallback
  enrich_project        — extract links, tracks, tech_stack
  write_project_description — Gemini Flash description + verdict line
  parse_rules           — Gemini Flash rubric parser
"""

import json
import logging
import re
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from agent import gemini_call

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

_TIMEOUT = 20


def _normalize_url(url: str) -> str:
    """Normalize known platform URLs to point at their submissions listing page."""
    parsed = urlparse(url)
    # lablab.ai: /ai-hackathons/{slug} → /ai-hackathons/{slug}/projects
    if "lablab.ai" in parsed.netloc:
        path = parsed.path.rstrip("/")
        if re.match(r"^/ai-hackathons/[^/]+$", path):
            url = url.rstrip("/") + "/projects"
            logger.info(f"lablab.ai URL normalized to {url}")
    return url


# ── fetch_page ─────────────────────────────────────────────────────────────────

def _is_js_rendered(html: str) -> bool:
    """Heuristic: if body text is very short the page is likely SPA-rendered."""
    soup = BeautifulSoup(html, "html.parser")
    body = soup.find("body")
    if not body:
        return True
    text = body.get_text(strip=True)
    return len(text) < 400


def _fetch_with_playwright(url: str) -> str:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        try:
            page.goto(url, timeout=45_000, wait_until="networkidle")
            time.sleep(3)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            html = page.content()
        finally:
            browser.close()
    return html


def _fetch_with_gemini_url_context(url: str) -> str:
    """
    Last-resort fetch via Gemini URL context tool — used when the server IP is
    Cloudflare-blocked. Gemini browses the URL through Google's infrastructure
    and returns a minimal HTML stub with <a> tags for every submission found.
    """
    import os
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return ""

    prompt = (
        f"Browse this hackathon submissions page: {url}\n\n"
        "Find every project/submission listed on that page. "
        "Return ONLY a plain HTML snippet — no markdown, no explanation — "
        "with one <a> tag per project:\n"
        '<a href="ABSOLUTE_URL_TO_PROJECT_PAGE">PROJECT TITLE | TEAM | SHORT DESCRIPTION</a>\n\n'
        "Rules:\n"
        "- Use the actual absolute URL to each project's own page\n"
        "- Do NOT invent projects — only list what you actually see on the page\n"
        "- If you find no projects, return exactly: <p>NO_SUBMISSIONS</p>"
    )
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(url_context=types.UrlContext())],
                temperature=0.1,
            ),
        )
        result = response.candidates[0].content.parts[0].text if response.candidates else ""
        if not result or "NO_SUBMISSIONS" in result:
            logger.info(f"Gemini URL context found no submissions for {url}")
            return ""
        logger.info(f"Gemini URL context returned {len(result)} chars for {url}")
        return result
    except Exception as exc:
        logger.error(f"Gemini URL context fetch failed: {exc}")
        return ""


def fetch_page(url: str) -> str:
    url = _normalize_url(url)
    logger.info(f"fetch_page: {url}")
    html = ""
    try:
        session = requests.Session()
        resp = session.get(url, headers=_HEADERS, timeout=_TIMEOUT, allow_redirects=True)
        resp.raise_for_status()
        html = resp.text
    except Exception as exc:
        logger.warning(f"requests failed for {url}: {exc}; trying Playwright")

    if not html or _is_js_rendered(html):
        logger.info(f"JS-rendered or empty for {url}, switching to Playwright")
        try:
            html = _fetch_with_playwright(url)
        except Exception as pw_exc:
            logger.error(f"Playwright failed: {pw_exc}")

    if not html or _is_js_rendered(html):
        logger.info(f"Playwright empty/shell for {url}, trying Gemini URL context")
        html = _fetch_with_gemini_url_context(url)

    return html


# ── enrich_project ─────────────────────────────────────────────────────────────

_GH_RE = re.compile(r"https?://github\.com/[\w\-]+/[\w\-]+", re.I)
_VIDEO_RE = re.compile(
    r"https?://(?:www\.)?(?:youtube\.com/watch\?[^\s\"'<>]+|youtu\.be/[\w\-]+|vimeo\.com/\d+)",
    re.I,
)
_DEMO_RE = re.compile(
    r"https?://[\w\-]+\.(?:app|dev|io|com|ai|xyz)/[^\s\"'<>]*",
    re.I,
)


def _extract_links(html: str, base_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    raw = html

    github = _GH_RE.search(raw)
    video = _VIDEO_RE.search(raw)

    base_host = urlparse(base_url).netloc

    demo_candidates = [
        m.group(0) for m in _DEMO_RE.finditer(raw)
        if urlparse(m.group(0)).netloc != base_host
        and "github.com" not in m.group(0)
        and "youtu" not in m.group(0)
        and "vimeo" not in m.group(0)
    ]

    other = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("http") and urlparse(href).netloc != base_host:
            if href not in (github.group(0) if github else ""):
                if not any(x in href for x in ("youtube", "youtu.be", "vimeo")):
                    if href not in demo_candidates:
                        other.append(href)

    return {
        "submission": base_url,
        "github": github.group(0) if github else None,
        "demo": demo_candidates[0] if demo_candidates else None,
        "video": video.group(0) if video else None,
        "other": list(dict.fromkeys(other))[:6],
    }


def _extract_tech_stack(soup: BeautifulSoup) -> list[str]:
    tech = []
    for el in soup.select("[class*='tag'], [class*='chip'], [class*='badge'], [class*='tech'], [class*='stack']"):
        t = el.get_text(strip=True)
        if 2 < len(t) < 40 and t not in tech:
            tech.append(t)
    return tech[:12]


def _extract_tracks(soup: BeautifulSoup) -> list[str]:
    tracks = []
    for el in soup.select("[class*='track'], [class*='prize'], [class*='category']"):
        t = el.get_text(strip=True)
        if 2 < len(t) < 60 and t not in tracks:
            tracks.append(t)
    return tracks[:6]


def enrich_project(project: dict) -> dict:
    p = dict(project)
    url = p.get("submission_url") or p.get("links", {}).get("submission", "")
    if not url:
        p.setdefault("links", {})
        p.setdefault("tracks", [])
        p.setdefault("tech_stack", [])
        return p

    html = fetch_page(url)
    if not html:
        # Always preserve the submission URL even if the page fetch fails
        p.setdefault("links", {"submission": url})
        p["links"].setdefault("submission", url)
        p.setdefault("tracks", [])
        p.setdefault("tech_stack", [])
        return p

    soup = BeautifulSoup(html, "html.parser")
    p["links"] = _extract_links(html, url)
    p["tech_stack"] = _extract_tech_stack(soup)
    p["tracks"] = p.get("tracks") or _extract_tracks(soup)
    return p


# ── write_project_description ──────────────────────────────────────────────────

_DESC_PROMPT = """\
You are the Verdict court's AI clerk.

Project record (JSON):
{record}

Write exactly this JSON (nothing else, no markdown fences):
{{
  "ai_description": "2-3 plain sentences explaining what this project actually does. No marketing language. No 'leveraging' or 'revolutionizing'. If the description is vague, say so.",
  "verdict_line": "One judicial sentence. Slightly sharp, slightly arrogant, suitable for a courtroom. Examples: 'Yet another RAG wrapper. The court is unmoved.' · 'Brave. Foolish. Promising.' · 'The reasoning is sound; the execution is not.'"
}}
"""


def write_project_description(project: dict) -> dict:
    p = dict(project)
    prompt = _DESC_PROMPT.format(
        record=json.dumps(
            {k: v for k, v in p.items() if k not in ("links", "tech_stack")},
            ensure_ascii=False,
        )
    )
    raw = gemini_call(prompt, model_tier="fast", response_mime_type="application/json")
    try:
        obj = json.loads(raw)
        p["ai_description"] = obj.get("ai_description", "")
        p["verdict_line"] = obj.get("verdict_line", "")
    except Exception:
        p["ai_description"] = ""
        p["verdict_line"] = "The court reserves judgment."
    return p


# ── parse_rules ────────────────────────────────────────────────────────────────

_DEFAULT_RUBRIC = [
    {"criterion": "Novelty",           "weight": 25, "description": "Is the thesis genuinely original?"},
    {"criterion": "Technical Depth",   "weight": 25, "description": "What was actually built — and does it work?"},
    {"criterion": "Real-world Impact", "weight": 25, "description": "Who pays for this on Monday?"},
    {"criterion": "Clarity",           "weight": 15, "description": "Does the pitch land in 60 seconds?"},
    {"criterion": "Track Fit",         "weight": 10, "description": "Alignment with the event's stated goals."},
]

_RULES_PROMPT = """\
You are a competition rubric parser.

Rubric text:
\"\"\"
{text}
\"\"\"

Parse into a JSON array of criteria. Weights must sum to exactly 100.
If the user gave no weights, infer reasonable ones.
Return only the JSON array (no markdown):
[{{"criterion": "...", "weight": 30, "description": "What earns a high score here."}}]
"""


def parse_rules(rules_text: str) -> list[dict]:
    if not rules_text or not rules_text.strip():
        return _DEFAULT_RUBRIC

    prompt = _RULES_PROMPT.format(text=rules_text.strip())
    raw = gemini_call(prompt, model_tier="fast", response_mime_type="application/json")
    try:
        rubric = json.loads(raw)
        # Normalise weights if they don't sum to 100
        total = sum(r.get("weight", 0) for r in rubric)
        if total and total != 100:
            factor = 100 / total
            for r in rubric:
                r["weight"] = round(r["weight"] * factor)
        return rubric
    except Exception:
        return _DEFAULT_RUBRIC
