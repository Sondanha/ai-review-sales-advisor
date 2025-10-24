# app/llm_client.py
from __future__ import annotations
import os, json
from typing import Any, Dict, Tuple

try:
    import google.generativeai as genai
except Exception:
    genai = None

# ==============================
# Internal helpers
# ==============================
def _extract_from_obj(resp: Any) -> Tuple[str, int | None, Dict[str, Any]]:
    # SDK object
    try:
        usage = getattr(resp, "usage_metadata", None)
        usage_dict: Dict[str, Any] = {}
        if usage:
            usage_dict = {
                "input_tokens": getattr(usage, "prompt_token_count", None),
                "output_tokens": getattr(usage, "candidates_token_count", None),
                "total_tokens": getattr(usage, "total_token_count", None),
            }
        cands = getattr(resp, "candidates", None)
        if cands:
            c0 = cands[0]
            reason = getattr(c0, "finish_reason", None)
            content = getattr(c0, "content", None)
            parts = getattr(content, "parts", None) if content else None
            if parts and getattr(parts[0], "text", None):
                return parts[0].text.strip(), reason, usage_dict
            return "", reason, usage_dict

        # blocked without candidates
        pf = getattr(resp, "prompt_feedback", None)
        if pf:
            info = {
                "prompt_feedback": {
                    "block_reason": getattr(pf, "block_reason", None),
                    "safety_ratings": [getattr(r, "category", None) for r in (getattr(pf, "safety_ratings", []) or [])],
                }
            }
            return "", 3, {**usage_dict, **info}

        t = getattr(resp, "text", "") or ""
        return str(t).strip(), None, usage_dict
    except Exception:
        pass

    # dict fallback
    if isinstance(resp, dict):
        if resp.get("error"):
            return "", None, {"error": resp["error"]}
        cands = resp.get("candidates") or []
        if cands:
            reason = cands[0].get("finish_reason")
            parts = ((cands[0].get("content") or {}).get("parts") or [])
            if parts:
                return (parts[0].get("text") or "").strip(), reason, resp.get("usage", {})
            return "", reason, resp.get("usage", {})
        for k in ("text", "output", "message", "content"):
            v = resp.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip(), resp.get("finish_reason"), resp.get("usage", {})
        pf = resp.get("prompt_feedback")
        if pf:
            return "", 3, {"prompt_feedback": pf, "usage": resp.get("usage", {})}
        return "", resp.get("finish_reason"), resp.get("usage", {})}

    t = getattr(resp, "text", "") or ""
    return str(t).strip(), None, {}

def _ensure_sdk() -> bool:
    if not genai:
        return False
    api_key = os.getenv("GEMINI_API_KEY")
    try:
        genai.configure(api_key=api_key)
    except Exception:
        pass
    return True

def _safe_dump_json(data: Dict[str, Any]) -> str:
    # compact JSON only. no reviews. db metrics only should be passed in.
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))

def _truncate(s: str, limit: int = 6000) -> str:
    return s if len(s) <= limit else s[:limit]

def _default_generation_config(max_output_tokens: int, temperature: float, extra: Dict | None) -> Dict:
    cfg = {
        "max_output_tokens": int(max_output_tokens),
        "temperature": float(temperature),
        "top_p": 0.9,
        "top_k": 40,
        "candidate_count": 1,
        "stop_sequences": [],
        "response_mime_type": "text/plain",
    }
    if isinstance(extra, dict):
        cfg.update(extra)
    return cfg

def _default_safety(kwargs: Dict | None) -> list[Dict[str, str]]:
    # conservative defaults; no relaxed sexual terms to avoid surprises
    ss = (kwargs or {}).get("safety_settings")
    if isinstance(ss, list):
        return ss
    return [
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HARASSMENT",        "threshold": "BLOCK_ONLY_HIGH"},
        {"category": "HARM_CATEGORY_HATE_SPEECH",       "threshold": "BLOCK_ONLY_HIGH"},
        {"category": "HARM_CATEGORY_SEXUAL_CONTENT",    "threshold": "BLOCK_ONLY_HIGH"},
        {"category": "HARM_CATEGORY_SEXUAL_AND_MINORS", "threshold": "BLOCK_ONLY_HIGH"},
    ]

# ==============================
# JSON-only entrypoint (use this)
# ==============================
def generate_json(
    task: str,
    data: Dict[str, Any],
    *,
    model: str,
    temperature: float = 0.25,
    max_output_tokens: int = 384,
    generation_config: Dict | None = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Strict JSON-only calling path.
    - No reviews.
    - Uses ONLY the provided DB-derived dict.
    - Adds a minimal system guard to ignore external knowledge.
    """
    if not _ensure_sdk():
        return {"text": "", "finish_reason": None, "usage": {}, "error": "Gemini SDK not available"}

    # Build minimal, neutral prompt
    prefix = (
        "역할: 매출·지표 분석 보고서 작성자.\n"
        "규칙: 외부 지식 금지. 아래 JSON 필드만 근거. 민감/비속어는 중립 표현으로 치환. 과장 금지. 간결.\n"
        f"작업: {task.strip()}\n"
        "데이터(JSON):\n"
    )
    payload = _safe_dump_json(data)
    prompt = _truncate(prefix + payload)

    model_obj = genai.GenerativeModel(model)
    cfg = _default_generation_config(max_output_tokens, temperature, generation_config)
    safety = _default_safety(kwargs)

    try:
        resp = model_obj.generate_content(
            prompt,
            generation_config=cfg,
            safety_settings=safety,
            request_options={"timeout": 30},
        )
        text, reason, usage = _extract_from_obj(resp)
        return {"text": text, "finish_reason": reason, "usage": usage}
    except Exception as e:
        return {"text": "", "finish_reason": None, "usage": {}, "error": str(e)}

# ==============================
# Backward-compatible prompt entrypoint
# ==============================
def generate(
    prompt: str,
    model: str,
    temperature: float = 0.3,
    max_output_tokens: int = 512,
    **kwargs,
):
    """
    Legacy API. Prefer generate_json() for DB-only use.
    """
    if not _ensure_sdk():
        return {"text": "", "finish_reason": None, "usage": {}, "error": "Gemini SDK not available"}

    prompt = _truncate(prompt)

    cfg = _default_generation_config(max_output_tokens, temperature, kwargs.get("generation_config"))
    safety = _default_safety(kwargs)

    try:
        model_obj = genai.GenerativeModel(model)
        resp = model_obj.generate_content(
            prompt,
            generation_config=cfg,
            safety_settings=safety,
            request_options={"timeout": 30},
        )
        text, reason, usage = _extract_from_obj(resp)
        return {"text": text, "finish_reason": reason, "usage": usage}
    except Exception as e:
        return {"text": "", "finish_reason": None, "usage": {}, "error": str(e)}
