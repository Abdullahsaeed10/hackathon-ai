"""
Verdict — Flask app.
All HTTP routes, SSE streaming, upload endpoint.

Production: gunicorn --worker-class gevent --workers 1 --bind 0.0.0.0:80 app:app
            (gevent worker is non-negotiable for SSE — sync workers buffer the stream)
"""

import json
import logging
import os
import re
import secrets
import time
import urllib.request
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request, send_from_directory
from flask_cors import CORS

load_dotenv()

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("verdict.app")

# ── Sweep old uploads on startup ───────────────────────────────────────────────
from storage import sweep_old_uploads, save_upload, get_upload_path, load_verdict, new_upload_id

deleted = sweep_old_uploads()
if deleted:
    logger.info(f"Swept {deleted} stale upload(s)")

# ── Flask app ──────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder="static", static_url_path="/static")
CORS(app, resources={r"/api/*": {"origins": "*"}})

STATIC = Path(__file__).parent / "static"

# ── Allowed upload extensions ──────────────────────────────────────────────────
ALLOWED_EXTS = {".csv", ".json", ".md", ".txt", ".pdf"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


# ── Models cache ──────────────────────────────────────────────────────────────

_models_cache: list | None = None
_models_cache_ts: float = 0
_MODELS_TTL = 600  # 10 minutes


def _default_models() -> list:
    return [
        {"name": "gemini-2.5-pro", "display_name": "Gemini 2.5 Pro", "description": "Most capable model for complex reasoning.", "recommended_for": "reasoning"},
        {"name": "gemini-2.5-flash", "display_name": "Gemini 2.5 Flash", "description": "Fast and efficient for high-volume tasks.", "recommended_for": "fast"},
    ]


def _fetch_gemini_models() -> list:
    global _models_cache, _models_cache_ts
    now = time.time()
    if _models_cache is not None and now - _models_cache_ts < _MODELS_TTL:
        return _models_cache

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return _default_models()

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())

        models = []
        for m in data.get("models", []):
            if "generateContent" not in m.get("supportedGenerationMethods", []):
                continue
            name = m["name"].replace("models/", "")
            models.append({
                "name": name,
                "display_name": m.get("displayName", name),
                "description": (m.get("description", ""))[:160],
                "recommended_for": None,
            })

        def _ver(n):
            nums = [int(x) for x in re.findall(r"\d+", n)]
            return tuple(nums[:3]) + (0, 0, 0)

        pros   = [m for m in models if "pro"   in m["name"] and "preview" not in m["name"]]
        flashs = [m for m in models if "flash" in m["name"] and "preview" not in m["name"]]
        if pros:
            sorted(pros, key=lambda m: _ver(m["name"]), reverse=True)[0]["recommended_for"] = "reasoning"
        if flashs:
            sorted(flashs, key=lambda m: _ver(m["name"]), reverse=True)[0]["recommended_for"] = "fast"

        _models_cache = models or _default_models()
        _models_cache_ts = now
        return _models_cache
    except Exception as exc:
        logger.warning(f"Failed to fetch Gemini models: {exc}")
        return _default_models()


def _build_model_config(reasoning: str, fast: str):
    from agent import ModelConfig, MODEL_PRO, MODEL_FLASH
    available = _fetch_gemini_models()
    names = {m["name"] for m in available}
    rec_r = next((m["name"] for m in available if m.get("recommended_for") == "reasoning"), MODEL_PRO)
    rec_f = next((m["name"] for m in available if m.get("recommended_for") == "fast"), MODEL_FLASH)

    if reasoning and reasoning not in names:
        logger.warning(f"Unknown reasoning model '{reasoning}', using {rec_r}")
        reasoning = rec_r
    elif not reasoning:
        reasoning = rec_r

    if fast and fast not in names:
        logger.warning(f"Unknown fast model '{fast}', using {rec_f}")
        fast = rec_f
    elif not fast:
        fast = rec_f

    return ModelConfig(reasoning=reasoning, fast=fast)


# ── SSE helper ─────────────────────────────────────────────────────────────────

def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


def _stream_agent(gen):
    """Wrap an agent generator into SSE bytes."""
    for event in gen:
        yield _sse(event)


# ── Frontend routes ────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(STATIC, "index.html")


@app.route("/scout")
@app.route("/judgment")
@app.route("/doctor")
@app.route("/v/<path:vid>")
def spa_routes(vid=None):
    """All client-side routes serve the same index.html."""
    return send_from_directory(STATIC, "index.html")


# ── GET /api/models ────────────────────────────────────────────────────────────

@app.route("/api/models")
def api_models():
    return jsonify({"models": _fetch_gemini_models()})


# ── POST /api/validate_hackathon ──────────────────────────────────────────────

@app.route("/api/validate_hackathon", methods=["POST"])
def api_validate_hackathon():
    data = request.get_json(force=True, silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"valid": False, "submission_count": 0, "error": "No URL provided."}), 400

    from tools_scout import validate_hackathon_url
    result = validate_hackathon_url(url)
    return jsonify(result)


# ── POST /api/scout ────────────────────────────────────────────────────────────

@app.route("/api/scout", methods=["POST"])
def api_scout():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()

    if not url:
        return jsonify({"error": "url is required"}), 400

    logger.info(f"Scout request: {url}")

    from agent import run_agent
    from tools_scout import SCOUT_TOOLS_MAP, SCOUT_SYSTEM_PROMPT
    from schemas import SCOUT_TOOLS

    model_config = _build_model_config(
        (data.get("model_reasoning") or "").strip(),
        (data.get("model_fast") or "").strip(),
    )
    logger.info(f"Scout models: reasoning={model_config.reasoning} fast={model_config.fast}")

    limit = data.get("limit")
    try:
        limit = int(limit) if limit else None
    except (TypeError, ValueError):
        limit = None

    def generate():
        t0 = time.time()
        limit_clause = f"\nLimit: process only the first {limit} projects after extraction — emit '→ limiting to top {limit} submissions' as a thought." if limit else ""
        goal = f"Scout this hackathon and produce a complete field report: {url}{limit_clause}"
        gen = run_agent(
            system_prompt=SCOUT_SYSTEM_PROMPT,
            user_goal=goal,
            tools_map=SCOUT_TOOLS_MAP,
            tool_declarations=SCOUT_TOOLS,
            max_iterations=50,
            model_config=model_config,
        )
        for event in gen:
            # Log thoughts and tool calls
            if event.get("type") == "tool_call":
                logger.info(f"  ⚖  {event['tool']}({event.get('args_summary', '')})")
            elif event.get("type") == "tool_result":
                logger.info(f"  ✓  {event['tool']}: {event.get('summary', '')}")
            yield _sse(event)
        logger.info(f"Scout complete in {time.time()-t0:.1f}s")

    return Response(
        generate(),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── POST /api/judgment (+ /api/doctor alias) ───────────────────────────────────

def _run_judgment(data: dict):
    rules = (data.get("rules") or "").strip()
    source_type = data.get("source_type", "manual_text")
    hackathon_url = (data.get("hackathon_url") or "").strip()
    manual_text = (data.get("manual_text") or "").strip()
    file_id = (data.get("uploaded_file_id") or "").strip()

    logger.info(f"Judgment request: source_type={source_type}")

    from agent import run_agent
    from tools_judgment import JUDGMENT_TOOLS_MAP, JUDGMENT_SYSTEM_PROMPT
    from schemas import JUDGMENT_TOOLS

    model_config = _build_model_config(
        (data.get("model_reasoning") or "").strip(),
        (data.get("model_fast") or "").strip(),
    )
    logger.info(f"Judgment models: reasoning={model_config.reasoning} fast={model_config.fast}")

    limit = data.get("limit")
    try:
        limit = int(limit) if limit else None
    except (TypeError, ValueError):
        limit = None

    def generate():
        t0 = time.time()

        # Build a structured goal for the agent
        goal_parts = [
            f"Source type: {source_type}",
            f"Rules / rubric: {rules or '(use defaults)'}",
        ]
        if source_type == "hackathon_url":
            goal_parts.append(f"Hackathon URL: {hackathon_url}")
        elif source_type == "uploaded_file":
            goal_parts.append(f"File ID: {file_id}")
        elif source_type == "manual_text":
            goal_parts.append(f"Submissions text:\n{manual_text[:6000]}")

        if limit:
            goal_parts.append(f"Limit: process only the first {limit} submissions — emit '→ limiting to top {limit} submissions' as a thought.")
        goal = (
            "Pass judgment on the following submissions against the provided rubric.\n\n"
            + "\n".join(goal_parts)
        )

        gen = run_agent(
            system_prompt=JUDGMENT_SYSTEM_PROMPT,
            user_goal=goal,
            tools_map=JUDGMENT_TOOLS_MAP,
            tool_declarations=JUDGMENT_TOOLS,
            max_iterations=80,
            model_config=model_config,
        )
        for event in gen:
            if event.get("type") == "tool_call":
                logger.info(f"  ⚖  {event['tool']}({event.get('args_summary', '')})")
            elif event.get("type") == "tool_result":
                logger.info(f"  ✓  {event['tool']}: {event.get('summary', '')}")
            yield _sse(event)
        logger.info(f"Judgment complete in {time.time()-t0:.1f}s")

    return Response(
        generate(),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.route("/api/judgment", methods=["POST"])
def api_judgment():
    data = request.get_json(silent=True) or {}
    return _run_judgment(data)


@app.route("/api/doctor", methods=["POST"])
def api_doctor():
    """Backward-compat alias."""
    data = request.get_json(silent=True) or {}
    return _run_judgment(data)


# ── POST /api/upload ───────────────────────────────────────────────────────────

@app.route("/api/upload", methods=["POST"])
def api_upload():
    if "file" not in request.files:
        return jsonify({"error": "no file field"}), 400

    f = request.files["file"]
    filename = f.filename or ""
    ext = Path(filename).suffix.lower()

    if ext not in ALLOWED_EXTS:
        return jsonify({"error": f"unsupported file type: {ext}. Accepted: {', '.join(sorted(ALLOWED_EXTS))}"}), 400

    data = f.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        return jsonify({"error": "file too large (max 10 MB)"}), 413

    file_id = new_upload_id()
    save_upload(file_id, ext, data)

    # Build preview
    preview = ""
    if ext == ".pdf":
        try:
            import pypdf, io
            reader = pypdf.PdfReader(io.BytesIO(data))
            preview = (reader.pages[0].extract_text() or "")[:200]
        except Exception:
            preview = "(PDF — text extraction unavailable)"
    else:
        try:
            preview = data.decode("utf-8", errors="replace")[:200]
        except Exception:
            preview = ""

    logger.info(f"Upload: {filename} → {file_id}{ext} ({len(data)} bytes)")

    return jsonify({
        "file_id": file_id,
        "filename": filename,
        "detected_type": ext.lstrip("."),
        "preview": preview,
    })


# ── GET /api/verdict/<id> ──────────────────────────────────────────────────────

@app.route("/api/verdict/<verdict_id>")
def api_verdict(verdict_id: str):
    report = load_verdict(verdict_id)
    if not report:
        return jsonify({"error": "verdict not found"}), 404
    return jsonify(report)


# ── Health check ───────────────────────────────────────────────────────────────

@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "time": time.time()})


# ── Dev server entry point ─────────────────────────────────────────────────────

if __name__ == "__main__":
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print("⚠  GEMINI_API_KEY not set — set it in .env before making real requests")
    print("Verdict backend starting on http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
