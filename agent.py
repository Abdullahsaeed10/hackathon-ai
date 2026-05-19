"""
Shared agent loop — Gemini client wrapper, SSE event yielder.

Model routing:
  reasoning tier — planning, scoring, cluster analysis, final summary
  fast tier      — link extraction, description writing, freeform parsing

All API calls go through gemini_call() so tools can choose their tier.
run_agent() is a generator that yields SSE event dicts.
"""

import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass
from typing import Generator, Literal

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# ── Rate-limit helpers ─────────────────────────────────────────────────────────

_RETRY_DELAY_RE = re.compile(r"retry in ([\d.]+)s", re.I)
_MAX_RETRY_WAIT = 65.0  # cap so we never sleep more than ~1 min


def _is_rate_limited(exc) -> bool:
    s = str(exc).lower()
    return "resource_exhausted" in s or "429" in s or "quota" in s


def _retry_delay(exc_str: str) -> float:
    m = _RETRY_DELAY_RE.search(exc_str)
    delay = float(m.group(1)) if m else 35.0
    return min(delay + 2, _MAX_RETRY_WAIT)


def _friendly_error(exc_str: str) -> str:
    """Strip verbose JSON from Gemini error responses for user display."""
    low = exc_str.lower()
    if "resource_exhausted" in low or "quota" in low:
        delay = _retry_delay(exc_str)
        return (
            f"Gemini API quota exceeded. "
            f"Please wait {delay:.0f}s and try again, or switch to a model with available quota "
            f"(e.g. Gemini 2.5 Flash). See ai.dev/rate-limit for your usage."
        )
    if "input token count exceeds" in low or ("invalid_argument" in low and "token" in low):
        return (
            "Page content is too large for the model's context window even after truncation. "
            "Try setting a smaller submission limit (e.g. Top 5 or Top 10)."
        )
    # Trim raw API errors to something readable
    return exc_str[:300]


# Max chars to inject into Gemini context from any single tool result.
# Prevents token-limit errors when fetch_page returns multi-MB HTML pages.
_MAX_TOOL_RESULT_CHARS = 90_000

MODEL_PRO = "gemini-2.5-pro"
MODEL_FLASH = "gemini-2.5-flash"


@dataclass
class ModelConfig:
    reasoning: str
    fast: str


DEFAULT_CONFIG = ModelConfig(reasoning=MODEL_PRO, fast=MODEL_FLASH)

# Per-greenlet/thread storage so tools can pick up the current request's config
_local = threading.local()

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        _client = genai.Client(api_key=api_key)
    return _client


def get_current_config() -> ModelConfig:
    """Return the ModelConfig for the current request (or default)."""
    return getattr(_local, "model_config", DEFAULT_CONFIG)


# ── Simple (non-agentic) Gemini call ──────────────────────────────────────────

def gemini_call(
    prompt: str,
    model_tier: Literal["reasoning", "fast"] = "fast",
    system: str | None = None,
    temperature: float = 0.3,
    response_mime_type: str | None = None,
) -> str:
    """
    One-shot text generation. model_tier picks from the current request's ModelConfig.
    Retries up to 2 times on 429 with the stated retry delay.
    """
    model_cfg = get_current_config()
    model_id = model_cfg.reasoning if model_tier == "reasoning" else model_cfg.fast
    client = _get_client()

    call_cfg: dict = {"temperature": temperature}
    if system:
        call_cfg["system_instruction"] = system
    if response_mime_type:
        call_cfg["response_mime_type"] = response_mime_type

    config = types.GenerateContentConfig(**call_cfg)

    for attempt in range(3):
        t0 = time.time()
        try:
            response = client.models.generate_content(
                model=model_id,
                contents=prompt,
                config=config,
            )
            logger.debug(f"gemini_call({model_id}) {time.time()-t0:.2f}s")
            try:
                return response.candidates[0].content.parts[0].text
            except (IndexError, AttributeError):
                return ""
        except Exception as exc:
            if _is_rate_limited(exc) and attempt < 2:
                delay = _retry_delay(str(exc))
                logger.warning(f"gemini_call rate limited on {model_id}, waiting {delay:.0f}s (attempt {attempt + 1})")
                time.sleep(delay)
                continue
            raise


# ── Helper: extract function call from response ────────────────────────────────

def _get_fn_call(response):
    try:
        for part in response.candidates[0].content.parts:
            if hasattr(part, "function_call") and part.function_call and part.function_call.name:
                return part.function_call
    except (IndexError, AttributeError):
        pass
    return None


def _get_text(response) -> str:
    try:
        parts = response.candidates[0].content.parts
        return "\n".join(p.text for p in parts if hasattr(p, "text") and p.text)
    except (IndexError, AttributeError):
        return ""


def _args_to_dict(args) -> dict:
    """Convert MapComposite / proto-map / dict to plain dict."""
    if args is None:
        return {}
    try:
        return dict(args)
    except Exception:
        return {}


def _short(v, n=50) -> str:
    s = str(v)
    return s[:n] + "…" if len(s) > n else s


# ── The agent loop ─────────────────────────────────────────────────────────────

def run_agent(
    system_prompt: str,
    user_goal: str,
    tools_map: dict,
    tool_declarations: list[dict],
    max_iterations: int = 50,
    model_config: ModelConfig | None = None,
) -> Generator[dict, None, None]:
    """
    Generator. Yields SSE event dicts at every step.

    SSE shapes:
      {"type": "thought",     "text": "→ ..."}
      {"type": "tool_call",   "tool": "...", "args_summary": "..."}
      {"type": "tool_result", "tool": "...", "summary": "..."}
      {"type": "final",       "verdict_id": "...", "report": {...}}
      {"type": "error",       "message": "..."}
    """
    cfg = model_config or DEFAULT_CONFIG
    _local.model_config = cfg

    client = _get_client()

    # Build tool config
    tool = types.Tool(function_declarations=tool_declarations)
    config = types.GenerateContentConfig(
        tools=[tool],
        system_instruction=system_prompt,
        temperature=0.3,
    )

    messages: list[types.Content] = [
        types.Content(role="user", parts=[types.Part(text=user_goal)])
    ]

    yield {"type": "thought", "text": "→ the court is convened"}

    verdict_id: str | None = None
    report: dict | None = None

    active_model = cfg.reasoning

    for iteration in range(max_iterations):
        t0 = time.time()

        # API call with fallback: reasoning model → fast model on quota exhaustion
        response = None
        for api_attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=active_model,
                    contents=messages,
                    config=config,
                )
                break
            except Exception as exc:
                exc_str = str(exc)
                if not _is_rate_limited(exc):
                    logger.error(f"Gemini API error at iteration {iteration}: {exc}")
                    yield {"type": "error", "message": _friendly_error(exc_str)}
                    return

                if api_attempt == 0 and cfg.fast and cfg.fast != active_model:
                    # First failure on reasoning model → fall back to fast model
                    yield {"type": "thought", "text": f"→ {active_model} quota exceeded — switching to {cfg.fast}"}
                    logger.warning(f"Falling back from {active_model} to {cfg.fast} due to rate limit")
                    active_model = cfg.fast
                else:
                    # Both models exhausted (or only one model configured)
                    yield {"type": "error", "message": _friendly_error(exc_str)}
                    return

        if response is None:
            yield {"type": "error", "message": "API unavailable after fallback attempt."}
            return

        elapsed = time.time() - t0
        logger.info(f"[iter {iteration}] Gemini responded in {elapsed:.2f}s")

        # Add assistant turn to history
        messages.append(response.candidates[0].content)

        fn_call = _get_fn_call(response)

        if fn_call:
            tool_name = fn_call.name
            args = _args_to_dict(fn_call.args)

            args_summary = ", ".join(
                f"{k}={_short(v, 40)}" for k, v in list(args.items())[:2]
            ) or "…"

            yield {"type": "tool_call", "tool": tool_name, "args_summary": args_summary}
            logger.info(f"→ {tool_name}({args_summary})")

            # Execute
            t1 = time.time()
            if tool_name in tools_map:
                try:
                    result = tools_map[tool_name](**args)
                except Exception as exc:
                    logger.error(f"Tool {tool_name} raised: {exc}")
                    result = {"error": str(exc)}
            else:
                result = {"error": f"Unknown tool: {tool_name}"}

            tool_elapsed = time.time() - t1
            logger.info(f"  {tool_name} done in {tool_elapsed:.2f}s")

            # Truncate large string results so they don't blow the context window.
            # fetch_page can return multi-MB HTML; cap it before injecting into history.
            if isinstance(result, str) and len(result) > _MAX_TOOL_RESULT_CHARS:
                logger.warning(
                    f"{tool_name} returned {len(result):,} chars — truncating to {_MAX_TOOL_RESULT_CHARS:,}"
                )
                result = result[:_MAX_TOOL_RESULT_CHARS]

            # Capture verdict IDs when the write tools are called
            if tool_name in ("write_scout_report", "write_judgment_report"):
                if isinstance(result, str):
                    verdict_id = result
                elif isinstance(result, dict):
                    verdict_id = result.get("id") or result.get("verdict_id")

            # Build summary for display
            if isinstance(result, str):
                summary = f"{len(result)} chars"
            elif isinstance(result, list):
                summary = f"{len(result)} items"
            elif isinstance(result, dict):
                summary = ", ".join(
                    f"{k}: {_short(v, 24)}" for k, v in list(result.items())[:3]
                )
            else:
                summary = _short(result)

            yield {
                "type": "tool_result",
                "tool": tool_name,
                "summary": summary[:140],
            }

            # Build function-response content
            fn_resp = types.FunctionResponse(
                name=tool_name,
                response={"result": result},
            )
            messages.append(
                types.Content(
                    role="user",
                    parts=[types.Part(function_response=fn_resp)],
                )
            )

        else:
            # Model returned plain text → done
            final_text = _get_text(response)
            yield {"type": "thought", "text": "→ the ruling is ready"}

            # Load and emit the final verdict
            if verdict_id:
                from storage import load_verdict
                report = load_verdict(verdict_id)
                yield {"type": "final", "verdict_id": verdict_id, "report": report}
            else:
                # No write tool was called — return text as report
                yield {
                    "type": "final",
                    "verdict_id": None,
                    "report": {"summary": final_text},
                }
            return

    yield {
        "type": "error",
        "message": "The court adjourned without a ruling — maximum iterations reached.",
    }
