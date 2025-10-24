import pandas as pd
import plotly.express as px
import json
from app.repo.metrics_repo import fetch_timeseries, fetch_snapshot
from app.repo.compare_repo import fetch_top_competitors

def _clean(df: pd.DataFrame) -> pd.DataFrame:
    # -999999.9 → None
    df = df.replace(-999999.9, pd.NA)
    # demographics JSON → columns
    demo = pd.json_normalize(df["demographics"])
    demo.columns = [f"demo_{c}" for c in demo.columns]
    df = pd.concat([df.drop(columns=["demographics"]), demo], axis=1)
    return df

def make_visuals(df: pd.DataFrame):
    figs = {}
    # 1) 매출 추이
    figs["sales"] = px.line(df, x="month", y="sales", markers=True,
        title="📈 월별 매출 구간 추이 (0에 가까울수록 상위)")
    # 2) 업종대비 매출지수
    figs["peer"] = px.line(df, x="month", y="peer_ind_sales_idx", markers=True,
        title="업종 평균 대비 매출지수(100=평균)")
    # 3) 상권 내 순위 (낮을수록 상위)
    figs["rank"] = px.area(df, x="month", y="area_rank_pct",
        title="상권 내 매출 순위 (낮을수록 상위)", range_y=[0,100])
    # 4) 고객 성별·연령 구성
    last = df.iloc[-1]
    ages = {k.replace("demo_age.",""):v for k,v in last.items() if "demo_age" in k}
    # 연령 그룹 합산
    age_groups = {
        "남성 20대 이하": ages.get("m_1020",0),
        "남성 30대": ages.get("m_30",0),
        "남성 40대": ages.get("m_40",0),
        "남성 50대": ages.get("m_50",0),
        "남성 60대 이상": ages.get("m_60",0),
        "여성 20대 이하": ages.get("f_1020",0),
        "여성 30대": ages.get("f_30",0),
        "여성 40대": ages.get("f_40",0),
        "여성 50대": ages.get("f_50",0),
        "여성 60대 이상": ages.get("f_60",0),
    }
    figs["age"] = px.bar(x=list(age_groups.keys()), y=list(age_groups.values()),
        title="최근 고객 연령·성별 분포 (%)")
    return figs

def build_llm_context(mct: str):
    ts = fetch_timeseries(mct, "2024-01-01", "2025-10-01")
    snap = fetch_snapshot(mct)
    df = _clean(pd.DataFrame(ts))
    competitors = fetch_top_competitors(mct)

    context = {
        "merchant": snap,
        "summary": {
            "avg_sales_idx": float(df["peer_ind_sales_idx"].mean(skipna=True)),
            "avg_rank_area": float(df["area_rank_pct"].mean(skipna=True)),
            "avg_delivery": float(df["delivery_ratio"].mean(skipna=True)),
        },
        "customers": df.filter(regex="demo_age").iloc[-1].to_dict(),
        "competitors": competitors,
        "timeseries": ts,
    }
    return context, df
