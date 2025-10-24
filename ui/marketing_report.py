# ui/marketing_report.py
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import json
from datetime import date, datetime
import decimal
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from app.repo.metrics_repo import fetch_timeseries, fetch_snapshot
from app.repo.compare_repo import fetch_top_competitors

# LLM 비활성 데모 모드
USE_LLM = False  # 항상 하드코딩 스토리라인 출력

# ----------------------------
# Helpers
# ----------------------------
def _json_default(o):
    if isinstance(o, (datetime, date)): return o.isoformat()
    if isinstance(o, pd.Timestamp):     return o.to_pydatetime().isoformat()
    if isinstance(o, np.integer):       return int(o)
    if isinstance(o, (np.floating, decimal.Decimal)): return float(o)
    if isinstance(o, np.bool_):         return bool(o)
    return str(o)

def _clean(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty: return df
    df = df.replace(-999999.9, pd.NA)

    num_cols = [c for c in ["sales","peer_ind_sales_idx","area_rank_pct","delivery_ratio"] if c in df.columns]
    for c in num_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    if "delivery_ratio" in df.columns:
        df["delivery_ratio"] = df["delivery_ratio"].clip(lower=0)

    if "month" in df.columns:
        df["month"] = pd.to_datetime(df["month"], errors="coerce")
        bad = df["month"].isna()
        if bad.any():
            df.loc[bad, "month"] = pd.to_datetime(df.loc[bad, "month"].astype(str), format="%Y%m", errors="coerce")

    if "demographics" in df.columns:
        def _ensure_dict(x):
            if isinstance(x, str):
                try: return json.loads(x)
                except Exception: return {}
            return x or {}
        df["demographics"] = df["demographics"].apply(_ensure_dict)
        demo = pd.json_normalize(df["demographics"])
        if not demo.empty:
            demo.columns = [f"demo_{c}" for c in demo.columns]
            df = pd.concat([df.drop(columns=["demographics"]), demo], axis=1)
    return df

def _story_from_df(df: pd.DataFrame, ctx: dict) -> str:
    """차트 스토리라인에 맞춘 데모 텍스트. LLM 미사용."""
    if df.empty:
        return "데이터가 부족합니다."

    # 1) 매출 구간 추이: 변동성 판단
    sales = df["sales"] if "sales" in df.columns else pd.Series(dtype=float)
    sales_var = float(sales.std(skipna=True)) if not sales.empty else 0.0
    sales_line = "월별 매출 구간은 큰 변동 없이 안정적이다." if sales_var < 0.03 else "월별 매출 구간에 변동이 존재한다."

    # 2) 상권 내 순위: 낮을수록 상위
    rank_line = ""
    if "area_rank_pct" in df.columns:
        rank_start = float(df["area_rank_pct"].dropna().iloc[0]) if df["area_rank_pct"].notna().any() else None
        rank_end = float(df["area_rank_pct"].dropna().iloc[-1]) if df["area_rank_pct"].notna().any() else None
        if rank_start and rank_end:
            trend = "개선" if rank_end < rank_start else "악화"
            rank_line = f"상권 내 매출 순위는 {int(round(rank_start))}%→{int(round(rank_end))}%로 {trend}되며 상위권을 유지한다."

    # 3) 업종 평균 대비 매출지수
    peer_line = ""
    if "peer_ind_sales_idx" in df.columns:
        peer = df["peer_ind_sales_idx"].dropna()
        if not peer.empty:
            p_avg = float(peer.mean())
            p_last = float(peer.iloc[-1])
            peer_line = f"업종 평균 대비 매출지수는 평균 약 {int(round(p_avg))}, 최근 {int(round(p_last))}로 평균(100)을 크게 상회한다."

    # 4) 고객 분포(최근 월)
    demo_line = ""
    last = df.tail(1).to_dict("records")[0]
    ages = {k.replace("demo_age.", ""): v for k, v in last.items() if str(k).startswith("demo_age.")}
    if ages:
        # 주요 4개 그룹만 노출
        tops = sorted([(k, float(ages.get(k, 0) or 0)) for k in ages], key=lambda x: x[1], reverse=True)[:4]
        label_map = {
            "m_1020":"남성 20대 이하", "m_30":"남성 30대", "m_40":"남성 40대", "m_50":"남성 50대", "m_60":"남성 60대 이상",
            "f_1020":"여성 20대 이하", "f_30":"여성 30대", "f_40":"여성 40대", "f_50":"여성 50대", "f_60":"여성 60대 이상",
        }
        top_txt = ", ".join([f"{label_map.get(k,k)} {int(round(v))}%" for k,v in tops if v > 0])
        if top_txt:
            demo_line = f"최근 고객층은 {top_txt} 비중이 높다."

    # 5) 액션 제안
    actions = [
        "20~30대 유입이 높은 시간대에 SNS 쿠폰형 프로모션을 집행",
        "상위 10% 순위 유지 목적의 평일 저녁 타겟 할인 운영",
        "업종 평균 대비 강점을 살린 세트·구독형 상품 노출 강화",
    ]

    parts = [sales_line, rank_line, peer_line, demo_line]
    parts = [p for p in parts if p]
    body = " ".join(parts) if parts else "핵심 지표 기준 안정적인 성과를 유지하고 있다."
    tips = "\n".join([f"- {t}" for t in actions])
    return f"{body}\n개선 제안:\n{tips}"

# ----------------------------
# Visuals
# ----------------------------
def make_visuals(df: pd.DataFrame) -> dict:
    figs = {}
    if df.empty: return figs
    if {"month","sales"}.issubset(df.columns):
        figs["sales"] = px.line(df, x="month", y="sales",
                                title="월별 매출 구간 추이 (0에 가까울수록 상위)", markers=True)
    if {"month","peer_ind_sales_idx"}.issubset(df.columns):
        figs["peer_sales"] = px.line(df, x="month", y="peer_ind_sales_idx",
                                     title="업종 평균 대비 매출지수 (100=평균)", markers=True)
    if {"month","area_rank_pct"}.issubset(df.columns):
        figs["rank"] = px.area(df, x="month", y="area_rank_pct",
                               title="상권 내 매출 순위 (낮을수록 상위)", range_y=[0, 100])
    last = df.tail(1).to_dict("records")
    if last:
        last = last[0]
        age_fields = {k.replace("demo_age.", ""): v for k, v in last.items() if str(k).startswith("demo_age.")}
        if age_fields:
            age_groups = {
                "남성 20대 이하": age_fields.get("m_1020", 0),
                "남성 30대": age_fields.get("m_30", 0),
                "남성 40대": age_fields.get("m_40", 0),
                "남성 50대": age_fields.get("m_50", 0),
                "남성 60대 이상": age_fields.get("m_60", 0),
                "여성 20대 이하": age_fields.get("f_1020", 0),
                "여성 30대": age_fields.get("f_30", 0),
                "여성 40대": age_fields.get("f_40", 0),
                "여성 50대": age_fields.get("f_50", 0),
                "여성 60대 이상": age_fields.get("f_60", 0),
            }
            figs["age"] = px.bar(x=list(age_groups.keys()), y=list(age_groups.values()),
                                 title="최근 고객 연령·성별 분포 (%)")
    return figs

# ----------------------------
# Data assembly
# ----------------------------
def build_llm_context(mct: str):
    ts = fetch_timeseries(mct, "2024-01-01", "2025-10-01")
    snap = fetch_snapshot(mct)
    comp = fetch_top_competitors(mct)

    df = _clean(pd.DataFrame(ts))

    avg_sales_idx = float(df["peer_ind_sales_idx"].mean(skipna=True)) if "peer_ind_sales_idx" in df.columns and not df.empty else None
    avg_rank_area = float(df["area_rank_pct"].mean(skipna=True)) if "area_rank_pct" in df.columns and not df.empty else None
    avg_delivery = float(df["delivery_ratio"].mean(skipna=True)) if "delivery_ratio" in df.columns and not df.empty else None
    customers = df.filter(regex=r"^demo_age\.").tail(1).to_dict("records")[0] if not df.filter(regex=r"^demo_age\.").empty else {}

    context = {
        "merchant": snap,
        "summary": {
            "avg_sales_idx": avg_sales_idx,
            "avg_rank_area": avg_rank_area,
            "avg_delivery": avg_delivery,
        },
        "customers": customers,
        "competitors": comp,
        "timeseries": ts,
    }
    return context, df

# ----------------------------
# Public API
# ----------------------------
def render_report(mct: str, show_debug: bool = False):
    ctx, df = build_llm_context(mct)
    if not ctx or not ctx.get("merchant"):
        st.warning("해당 가맹점 데이터를 찾을 수 없습니다.")
        return

    m = ctx["merchant"]
    st.subheader(f"🏪 {m.get('name','')} — {m.get('industry','')}/{m.get('bizarea','')}")
    st.caption(f"최근 데이터 기준월: {m.get('month','')}")

    st.markdown("### 📈 시각적 분석")
    figs = make_visuals(df)
    if figs:
        for fig in figs.values():
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("시각화 가능한 데이터가 없습니다.")

    st.markdown("### 🏁 동일 상권 내 경쟁 매장 (상위 3개)")
    comp = ctx.get("competitors", []) or []
    if comp:
        st.dataframe(pd.DataFrame(comp), use_container_width=True)
    else:
        st.info("경쟁 매장 데이터가 없습니다.")

    # ---------------- DEMO 스토리라인 ----------------
    st.markdown("### 🤖 AI 기반 마케팅 인사이트 (Demo)")
    st.write(_story_from_df(df, ctx))

    if show_debug:
        st.markdown("#### 📦 스토리라인 산출 입력(축약)")
        slim = {
            "merchant": {k: ctx.get("merchant", {}).get(k) for k in ("name","industry","bizarea","month")},
            "timeseries_rows": len(ctx.get("timeseries") or []),
            "competitors_rows": len(ctx.get("competitors") or []),
            "has_demo_age": bool(df.filter(regex=r'^demo_age\.').shape[1]),
            "avg_peer_idx": ctx.get("summary", {}).get("avg_sales_idx"),
            "avg_rank_pct": ctx.get("summary", {}).get("avg_rank_area"),
        }
        st.json(slim)
