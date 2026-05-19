"""
Persistent file-based storage for Verdict.
Verdict IDs: v_ + secrets.token_urlsafe(4)
Upload IDs:  u_ + secrets.token_urlsafe(4)
"""

import json
import os
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path

_BASE = Path(__file__).parent / "data"
_VERDICTS = _BASE / "verdicts"
_UPLOADS = _BASE / "uploads"

_VERDICTS.mkdir(parents=True, exist_ok=True)
_UPLOADS.mkdir(parents=True, exist_ok=True)


# ── IDs ────────────────────────────────────────────────────────────────────────

def new_verdict_id() -> str:
    return "v_" + secrets.token_urlsafe(4)


def new_upload_id() -> str:
    return "u_" + secrets.token_urlsafe(4)


# ── Verdicts ───────────────────────────────────────────────────────────────────

def save_verdict(verdict_id: str, data: dict) -> None:
    """Atomic write — tmp then rename to avoid partial reads."""
    path = _VERDICTS / f"{verdict_id}.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.rename(path)


def load_verdict(verdict_id: str) -> dict | None:
    path = _VERDICTS / f"{verdict_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def list_verdicts() -> list[str]:
    return [p.stem for p in sorted(_VERDICTS.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)]


# ── Uploads ────────────────────────────────────────────────────────────────────

def save_upload(file_id: str, ext: str, data: bytes) -> Path:
    path = _UPLOADS / f"{file_id}{ext}"
    path.write_bytes(data)
    return path


def get_upload_path(file_id: str) -> Path | None:
    """Find the upload file regardless of extension."""
    matches = list(_UPLOADS.glob(f"{file_id}.*"))
    return matches[0] if matches else None


def sweep_old_uploads(max_age_seconds: int = 86400) -> int:
    """Delete uploads older than max_age_seconds. Returns count deleted."""
    cutoff = time.time() - max_age_seconds
    count = 0
    for p in _UPLOADS.iterdir():
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
                count += 1
        except Exception:
            pass
    return count


# ── Timestamps ─────────────────────────────────────────────────────────────────

def now_ts() -> str:
    dt = datetime.now(timezone.utc)
    day = str(dt.day)  # no leading zero, cross-platform
    return dt.strftime(f"{day} %B %Y · %H:%M GMT")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
