from typing import Any, Dict, List, Optional
from datetime import date
from app.repo.metrics_repo import fetch_timeseries, fetch_snapshot

def _fmt_pct(x: Optional[float]) -> str:
    if x is None:
        return "-"
    return f"{x:.1f}%"

def _fmt_rank(x: Optional[float]) -> str:
    if x is None:
        return "-"
    return f"P{x:.0f}"

def _delta(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    return a - b

def build_dashboard_cards(mct: str, start: str, end: str) -> Dict[str, Any]:
    ts = fetch_timeseries(mct, start, end)
    snap = fetch_snapshot(mct)

    latest = ts[-1] if ts else None
    prev = ts[-2] if len(ts) >= 2 else None

    cards: List[Dict[str, Any]] = []
    if latest:
        # 매출지수(업종대비)
        cards.append({
            "key": "peer_ind_sales_idx",
            "title": "업종대비 매출지수",
            "value": _fmt_pct(latest.get("peer_ind_sales_idx")),
            "delta": _fmt_pct(_delta(latest.get("peer_ind_sales_idx"), prev.get("peer_ind_sales_idx") if prev else None)),
            "tooltip": "업종 평균=100",
            "badge": "▲" if _delta(latest.get("peer_ind_sales_idx"), prev.get("peer_ind_sales_idx") if prev else None) and _delta(latest.get("peer_ind_sales_idx"), prev.get("peer_ind_sales_idx")) > 0 else " "
        })
        # 건수지수(업종대비)
        cards.append({
            "key": "peer_ind_cnt_idx",
            "title": "업종대비 건수지수",
            "value": _fmt_pct(latest.get("peer_ind_cnt_idx")),
            "delta": _fmt_pct(_delta(latest.get("peer_ind_cnt_idx"), prev.get("peer_ind_cnt_idx") if prev else None)),
            "tooltip": "업종 평균=100",
            "badge": "▲" if _delta(latest.get("peer_ind_cnt_idx"), prev.get("peer_ind_cnt_idx") if prev else None) and _delta(latest.get("peer_ind_cnt_idx"), prev.get("peer_ind_cnt_idx")) > 0 else " "
        })
        # 업종 내 백분위
        cards.append({
            "key": "ind_rank_pct",
            "title": "업종 내 백분위",
            "value": _fmt_rank(latest.get("ind_rank_pct")),
            "delta": _fmt_pct(_delta(prev.get("ind_rank_pct"), latest.get("ind_rank_pct")) if prev else None),  # 낮을수록 개선 → prev - now
            "tooltip": "낮을수록 상위",
            "badge": "▲" if prev and latest.get("ind_rank_pct") is not None and prev.get("ind_rank_pct") and latest["ind_rank_pct"] < prev["ind_rank_pct"] else " "
        })
        # 상권 내 백분위
        cards.append({
            "key": "area_rank_pct",
            "title": "상권 내 백분위",
            "value": _fmt_rank(latest.get("area_rank_pct")),
            "delta": _fmt_pct(_delta(prev.get("area_rank_pct"), latest.get("area_rank_pct")) if prev else None),
            "tooltip": "낮을수록 상위",
            "badge": "▲" if prev and latest.get("area_rank_pct") is not None and prev.get("area_rank_pct") and latest["area_rank_pct"] < prev["area_rank_pct"] else " "
        })
        # 배달매출 비율
        cards.append({
            "key": "delivery_ratio",
            "title": "배달 비중",
            "value": _fmt_pct(latest.get("delivery_ratio")),
            "delta": _fmt_pct(_delta(latest.get("delivery_ratio"), prev.get("delivery_ratio") if prev else None)),
            "tooltip": "음수는 0으로 보정",
            "badge": ""
        })
        # 신규/재방문
        demo = latest.get("demographics") or {}
        visit = demo.get("visit") or {}
        cards.append({
            "key": "visit_mix",
            "title": "방문 구성",
            "value": f"신규 {_fmt_pct(visit.get('new'))} / 재방문 {_fmt_pct(visit.get('revisit'))}",
            "delta": "",
            "tooltip": "최근 월 방문자 구성",
            "badge": ""
        })

    context = {
        "merchant": {
            "id": mct,
            "name": snap.get("name") if snap else None,
            "industry": snap.get("industry") if snap else None,
            "bizarea": snap.get("bizarea") if snap else None,
            "month": snap.get("month") if snap else None
        },
        "timeseries": ts,      # LLM 참고용 원자료
        "cards": cards         # UI 카드 사양
    }
    return context
