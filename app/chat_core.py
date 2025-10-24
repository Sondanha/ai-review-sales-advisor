# app/chat_core.py
from __future__ import annotations
import os, json
from typing import Any, Dict, Tuple

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# 공통 LLM 클라이언트(가능하면 우선)
from app.llm_client import generate as llm_generate

# SDK 백업
try:
    import google.generativeai as genai
except Exception:
    genai = None

BYPASS_CLIENT = os.getenv("LLM_BYPASS_CLIENT", "1") == "1"  # 1이면 llm_client 우회 사용


# ----------------------------
# 내부 유틸
# ----------------------------
def _json_default(o):
    try:
        import pandas as pd, numpy as np
        from datetime import date, datetime; import decimal
        if isinstance(o, (datetime, date)): return o.isoformat()
        if isinstance(o, pd.Timestamp):     return o.to_pydatetime().isoformat()
        if isinstance(o, (np.integer,)):    return int(o)
        if isinstance(o, (np.floating, decimal.Decimal)): return float(o)
        if isinstance(o, (np.bool_,)):      return bool(o)
    except Exception:
        pass
    return str(o)

def _finish_reason_label(reason: int | None) -> str:
    return {
        1:"STOP",2:"MAX_TOKENS",3:"SAFETY",4:"RECITATION",5:"OTHER",
        6:"BLOCKLIST",7:"PROHIBITED_CONTENT",8:"SPII",9:"MALFORMED_FUNCTION_CALL",
    }.get(reason, "UNKNOWN")

def _extract_block_info_from_obj(resp_obj: Any) -> Dict[str, Any]:
    info: Dict[str, Any] = {}
    pf = getattr(resp_obj, "prompt_feedback", None)
    if pf:
        info["block_reason"] = getattr(pf, "block_reason", None)
        sr = getattr(pf, "safety_ratings", None) or []
        info["safety_ratings"] = [getattr(r, "category", None) for r in sr]
    return info

def _extract_text_and_reason(resp: Any) -> Tuple[str, int | None, Dict[str, Any]]:
    # 문자열
    if isinstance(resp, str):
        return resp.strip(), None, {}

    # dict
    if isinstance(resp, dict):
        if "error" in resp and resp.get("error"):
            return "", None, {"error": resp["error"]}
        for k in ("text","output","message","content"):
            v = resp.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip(), resp.get("finish_reason"), resp.get("usage", {})
        cands = resp.get("candidates") or []
        if cands:
            c0 = cands[0]; reason = c0.get("finish_reason")
            parts = ((c0.get("content") or {}).get("parts") or [])
            if parts:
                t = parts[0].get("text") or ""
                return t.strip(), reason, resp.get("usage", {})
            return "", reason, resp.get("usage", {})
        pf = resp.get("prompt_feedback") or {}
        if pf:
            return "", 3, {"prompt_feedback": pf, "usage": resp.get("usage", {})}
        return "", resp.get("finish_reason"), resp.get("usage", {})

    # SDK 객체
    try:
        usage = getattr(resp, "usage_metadata", None)
        usage_dict = {}
        if usage:
            usage_dict = {
                "input_tokens": getattr(usage, "prompt_token_count", None),
                "output_tokens": getattr(usage, "candidates_token_count", None),
                "total_tokens": getattr(usage, "total_token_count", None),
            }
        cands = getattr(resp, "candidates", None)
        if cands:
            c0 = cands[0]; reason = getattr(c0, "finish_reason", None)
            content = getattr(c0, "content", None)
            parts = getattr(content, "parts", None) if content else None
            if parts and getattr(parts[0], "text", None):
                return parts[0].text.strip(), reason, usage_dict
            return "", reason, usage_dict
        # candidates 없음 → 차단 정보 surface
        block_info = _extract_block_info_from_obj(resp)
        if block_info:
            return "", 3, {"prompt_feedback": block_info} | usage_dict
        # fallback
        t = getattr(resp, "text", "") or ""
        return str(t).strip(), None, usage_dict
    except Exception:
        return "", None, {}

def _sdk_generate(prompt: str, model_name: str, max_output_tokens: int, temperature: float, **kwargs) -> Dict[str, Any]:
    if not genai:
        return {"text":"", "finish_reason":None, "usage":{}, "error":"SDK not available"}
    api_key = os.getenv("GEMINI_API_KEY")
    try:
        genai.configure(api_key=api_key)
    except Exception:
        pass
    try:
        model = genai.GenerativeModel(model_name)
        generation_config = {
            "max_output_tokens": max_output_tokens,
            "temperature": temperature,
            "top_p": 0.9, "top_k": 40,
            "candidate_count": 1,
            "stop_sequences": [],
            "response_mime_type": "text/plain",
        }
        if isinstance(kwargs.get("generation_config"), dict):
            generation_config.update(kwargs["generation_config"])
        resp = model.generate_content(
            prompt,
            generation_config=generation_config,
            safety_settings=[
                {"category":"HARM_CATEGORY_DANGEROUS_CONTENT","threshold":"BLOCK_NONE"},
                {"category":"HARM_CATEGORY_HARASSMENT","threshold":"BLOCK_ONLY_HIGH"},
                {"category":"HARM_CATEGORY_HATE_SPEECH","threshold":"BLOCK_ONLY_HIGH"},
                {"category":"HARM_CATEGORY_SEXUAL_CONTENT","threshold":"BLOCK_NONE"},
                {"category":"HARM_CATEGORY_SEXUAL_AND_MINORS","threshold":"BLOCK_NONE"},
            ],
            request_options={"timeout": 30},
        )
        text, reason, usage = _extract_text_and_reason(resp)
        out = {"text": text, "finish_reason": reason, "usage": usage}
        if not text and not reason:
            out["error"] = "empty_response"
            out["debug"] = _extract_block_info_from_obj(resp)
        return out
    except Exception as e:
        return {"text":"", "finish_reason":None, "usage":{}, "error":str(e)}


# ----------------------------
# 핵심 클래스
# ----------------------------
class ChatCore:
    """
    통합 LLM + DB + 보고서 로직.
    """
    def __init__(self, database_url: str | None = None, model: str | None = None):
        # DB
        self.engine = None
        self.SessionLocal = None
        if database_url:
            self.engine = create_engine(database_url, pool_size=5, max_overflow=5, pool_pre_ping=True)
            self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)

        # LLM
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.llm_ready = bool(os.getenv("GEMINI_API_KEY"))

    # 공통 LLM 호출
    def call_llm(self, prompt: str, **gen_kwargs) -> str:
        if not self.llm_ready:
            return "(LLM 비활성화) " + prompt[:500]

        # 입력 길이 방어
        if len(prompt) > 6000:
            prompt = prompt[:6000]

        temperature = float(gen_kwargs.get("temperature", 0.3))
        head = prompt.split("데이터:\n")[0] if "데이터:\n" in prompt else prompt[:400]
        attempts = [
            {"max_output_tokens": int(gen_kwargs.get("max_output_tokens", 256)), "prompt": prompt},
            {"max_output_tokens": 384, "prompt": f"{head}\n민감 표현과 비속어는 제거. 결과만 4줄."},
            {"max_output_tokens": 512, "prompt": f"{head}\n핵심만 5문장 이하로 요약."},
        ]

        last_reason = None
        last_usage = None
        last_err = None
        last_debug = None

        for opt in attempts:
            p = opt["prompt"]
            try:
                if BYPASS_CLIENT:
                    sdk = _sdk_generate(p, self.model, opt["max_output_tokens"], temperature)
                    text, reason, usage = sdk.get("text",""), sdk.get("finish_reason"), sdk.get("usage")
                    last_err = sdk.get("error"); last_debug = sdk.get("debug")
                else:
                    resp = llm_generate(p, model=self.model, temperature=temperature, max_output_tokens=opt["max_output_tokens"])
                    text, reason, usage = _extract_text_and_reason(resp)

                last_reason, last_usage = reason, usage
                if text:
                    return text
                if reason in (3, 6, 7, 8):  # SAFETY류
                    break
                if not reason and not text:
                    last_err = last_err or "empty_response"
            except Exception as e:
                last_err = str(e)
                continue

        label = _finish_reason_label(last_reason)
        meta = ""
        if isinstance(last_usage, dict):
            meta = f" (tokens in/out/total: {last_usage.get('input_tokens')}/{last_usage.get('output_tokens')}/{last_usage.get('total_tokens')})"
        dbg = f" | debug={last_debug}" if last_debug else ""
        if last_reason == 2:
            return f"(LLM 오류: MAX_TOKENS{meta}{dbg})"
        if last_reason in (3, 6, 7, 8):
            return f"(LLM 오류: SAFETY 차단: {label}{meta}{dbg})"
        return f"(LLM 오류: {label or 'UNKNOWN'}{meta} | {last_err or '원인 불명'}{dbg})"

    # 기본 채팅
    def reply(self, messages: list[dict[str, str]]) -> str:
        user_text = self._latest_user_text(messages)
        if not user_text:
            return "질문을 입력해 주세요."
        return self.call_llm(user_text)

    # 리뷰 요약
    def summarize_reviews(self, raw_texts: list[str]) -> dict:
        if not raw_texts:
            return {"summary":"리뷰가 없습니다.","aspects":[],"sentiment":0}
        prompt = ("다음 리뷰들을 간결히 요약하고 주요 키워드 3~5개와 "
                  "감정 점수(0~100)를 JSON으로 작성하라.\n"
                  "필드: summary, aspects(list[str]), sentiment(int)\n\n"
                  + "\n\n".join(raw_texts[:30]))
        resp = self.call_llm(prompt, temperature=0.2, max_output_tokens=256)
        return self._safe_json(resp)

    # 보고서 자동 생성
    def generate_marketing_report(self, ctx: dict) -> str:
        if not ctx:
            return "데이터가 부족하여 보고서를 생성할 수 없습니다."
        prompt = (
            "너는 요식업 마케팅 분석가다.\n"
            "다음 JSON 데이터를 바탕으로 작성하라.\n"
            "1. 핵심 요약\n2. 고객층 분석\n3. 경쟁점 요약\n4. 개선 제안 3가지\n\n"
            f"데이터(JSON):\n{json.dumps(ctx, ensure_ascii=False, default=_json_default)}"
        )
        return self.call_llm(prompt, temperature=0.25, max_output_tokens=384)

    # DB 유틸
    def db(self):
        if not self.SessionLocal:
            raise RuntimeError("DB 세션이 설정되지 않았습니다.")
        return self.SessionLocal()

    # 컨텍스트 로드
    def load_context(self, user_id: str, area: str | None, category: str | None) -> dict:
        ctx: dict = {}
        if self.engine:
            with self.engine.connect() as conn:
                last = conn.execute(text("""
                    select summary_json
                    from conversations
                    where user_id=:uid
                    order by ended_at desc
                    limit 1
                """), {"uid": user_id}).scalar()
                if last:
                    ctx["last_summary"] = last

                docs = conn.execute(text("""
                    select text
                    from review_raw
                    where (:area is null or area=:area)
                      and (:category is null or category=:category)
                    order by created_at desc
                    limit 20
                """), {"area": area, "category": category}).scalars().all()
                ctx["docs"] = docs
        ctx["greeting"] = f"{area or ''}/{category or ''} 컨텍스트를 불러왔습니다."
        return ctx

    # 대화 종료 저장
    def end_conversation(self, messages: list[dict[str, str]], metadata: dict | None = None) -> None:
        if not self.engine:
            return
        summary = None
        if self.llm_ready and messages:
            try:
                prompt = "다음 대화를 5줄 이내로 요약:\n\n" + "\n".join(
                    f"{m['role']}: {m['content']}" for m in messages[-50:]
                )
                summary = self.call_llm(prompt, temperature=0.2, max_output_tokens=192)
            except Exception:
                summary = None

        with self.engine.begin() as conn:
            conv_id = conn.execute(text("""
                insert into conversations(user_id, area, category, started_at, ended_at, summary_json)
                values (:uid, :area, :category, now()-interval '5 minutes', now(), :summary)
                returning id
            """), {
                "uid": (metadata or {}).get("user_id", "demo-user"),
                "area": (metadata or {}).get("area"),
                "category": (metadata or {}).get("category"),
                "summary": summary
            }).scalar()
            for m in messages:
                conn.execute(text("""
                    insert into messages(conversation_id, role, content, created_at)
                    values (:cid, :role, :content, now())
                """), {"cid": conv_id, "role": m.get("role"), "content": m.get("content")})

    # 헬퍼
    @staticmethod
    def _latest_user_text(messages: list[dict[str, str]]) -> str | None:
        for m in reversed(messages):
            if m.get("role") == "user":
                return (m.get("content") or "").strip()
        return None

    @staticmethod
    def _safe_json(text: str) -> dict:
        try:
            return json.loads(text)
        except Exception:
            return {"summary": (text or "")[:300], "aspects": [], "sentiment": 50}


# ----------------------------
# 전역 빌더/헬퍼
# ----------------------------
def build_chat_core_from_env() -> ChatCore:
    return ChatCore(
        database_url=os.environ.get("DATABASE_URL"),
        model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
    )

def call_llm(prompt: str, **gen_kwargs) -> str:
    core = build_chat_core_from_env()
    return core.call_llm(prompt, **gen_kwargs)
