import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import json
from datetime import datetime, timedelta
import streamlit as st
from streamlit.components.v1 import html as component_html

from app.services.card_items_service import build_dashboard_cards
from ui.components.cards import render_dashboard
from ui import marketing_report

# ---------- Config ----------
BRAND = "AI 세일즈 어드바이저"
AREA_DEFAULT = "뚝섬"
CATEGORY_DEFAULT = "이자카야"

st.set_page_config(page_title="세일즈 어드바이저", page_icon="💬", layout="wide")

# ---------- CSS ----------
BASE_CSS = r"""
section.main > div.block-container{ max-width: 980px; }
:root{
  --bg:#FFFFFF; --panel:#FFFFFF; --panel-2:#F7F8FB;
  --ink:#1B1F2A; --muted:#5B6475; --accent:#2E5AAC;
  --border:#E0E4EE; --border-strong:#CCD3E1; --review-ink:#1B1F2A;
}
@media (prefers-color-scheme: dark){
  :root{
    --bg:#0F1220; --panel:#141A2A; --panel-2:#1A2235;
    --ink:#E6EAF2; --muted:#9AA4B2; --accent:#6AA2FF;
    --border:rgba(255,255,255,.12); --border-strong:rgba(255,255,255,.2); --review-ink:#FFFFFF;
  }
}
html, body, [data-testid="stAppViewContainer"]{ background:var(--bg); color:var(--ink); }

.toprow{ border-bottom:1px solid var(--border); padding:.5rem .25rem; margin:-.5rem 0 .25rem 0; }
.brand-title-left{ text-align:left; font-weight:800; font-size:16px; line-height:34px; }

/* Hero */
.hero{ background:linear-gradient(180deg, rgba(245,197,66,.10), transparent 60%); border:1.5px solid var(--border-strong);
  border-radius:18px; padding:18px 16px 12px 16px; margin:6px 0 10px 0; text-align:center; }
.hero .kicker{ font-size:12px; color:var(--muted); margin:0 0 6px 0;}
.hero h1{ margin:0; font-size:clamp(18px,3vw,24px); line-height:1.12; }  /* 더 작게 */
.hero .highlight{ color:var(--accent); background:rgba(46,90,172,.10); padding:0 .25em; border-radius:.35em;}
.hero .highlight-brand{ color:#111; background:linear-gradient(90deg, #F8D96B, #EFC437); -webkit-background-clip:text; -webkit-text-fill-color:transparent; font-weight:900; }
.hero-controls{ display:flex; gap:10px; justify-content:center; align-items:center; margin:8px auto 0 auto; width:min(720px,92vw); }
.small-label{ font-size:11px; opacity:.8; margin-right:4px; }
.hero :where([class*="st-emotion-cache"]) label{ display:none; }

/* 리뷰 티커 */
.ticker{ margin:8px auto 6px auto; width:100%; max-width:980px; padding:8px 10px; border:1.5px solid var(--border-strong);
  border-radius:999px; background:var(--panel-2); font-size:12.5px; display:flex; align-items:center; gap:8px; justify-content:center; }

/* 카드뉴스 더 작게 */
.cards{ display:flex; gap:8px; overflow-x:auto; padding:10px 4px 0 4px; scroll-snap-type:x mandatory; }
.card{ flex:0 0 auto; width:180px; height:140px; scroll-snap-align:start; border:1.5px solid var(--border-strong);
  border-radius:12px; background:var(--panel); display:flex; flex-direction:column; overflow:hidden; cursor:pointer; box-shadow:0 3px 10px rgba(15,23,42,.10); }
.card__head{ padding:6px 8px 4px 8px; font-weight:800; font-size:12px; border-bottom:1px solid var(--border); } 
/* 제목 더 작게 */
.card__body{ flex:1 1 auto; display:flex; align-items:center; justify-content:center; background:var(--panel-2); opacity:.9; font-size:12px; }

/* --- 카드뉴스 내부 텍스트 크기 조정 --- */
[data-testid="stHorizontalBlock"] {
  gap: 6px !important;
}
[data-testid="stElementContainer"] {
  font-size: 10px !important; /* 전체 폰트 축소 */
}
[data-testid="stMetricLabel"] {
  font-size: 10px !important;
}
[data-testid="stMetricValue"] {
  font-size: 14px !important;
  font-weight: 700 !important;
}
[data-testid="stMetricDelta"] {
  font-size: 10px !important;
}




/* KPI 타이틀 더 작게 */
.kpi-title{ font-weight:800; font-size:14px; margin:2px 0 6px 0; opacity:.9; }

/* KPI 박스: 동일 크기 + 숫자/라벨 더 작게 */
.kpi-wrap .stHorizontalBlock{ gap:8px; }
.kpi-wrap [data-testid="stVerticalBlock"]{ padding:0; margin:0; }
.kpi-wrap [data-testid="column"]{ padding:0 !important; }
.kpi-wrap [data-testid="stMetric"]{
  border:1.5px solid var(--border-strong);
  border-radius:10px;
  padding:6px 8px;
  min-width:120px; max-width:120px;
  min-height:76px;
  display:flex; align-items:center; background:var(--panel);
}
.kpi-wrap [data-testid="stMetricLabel"]{ font-size:11px; color:var(--muted); }
.kpi-wrap [data-testid="stMetricValue"]{ font-size:16px; font-weight:800; }
.kpi-wrap [data-testid="stMetricDelta"]{ font-size:11px; }

/* 보고서/설명 */
.report-row{ margin:6px 0 8px 0; }
.report-desc{ font-size:13px; line-height:1.32; opacity:.95; margin-top:6px; }

/* 리뷰 섹션 */
.reviews-panel{ margin:10px 0 0 0; padding:10px; border:1.5px solid var(--border-strong); border-radius:12px; background:var(--panel-2); }
.reviews-title{ font-weight:800; margin-bottom:6px; color:var(--review-ink); font-size:14px; }
.rev-grid{ display:grid; grid-template-columns:1fr 1fr; gap:10px; }
.review-col-title{ font-weight:700; margin-bottom:6px; color:var(--review-ink); font-size:12.5px; }
.review-item{ margin:3px 0; font-size:12.5px; color:var(--review-ink); }

/* --- 카드뉴스 내부 텍스트 크기 조정 --- */
[data-testid="stHorizontalBlock"]{ gap:6px !important; }
[data-testid="stElementContainer"]{ font-size:12px !important; }
[data-testid="stMetricLabel"]{ font-size:10px !important; }
[data-testid="stMetricValue"]{ font-size:14px !important; font-weight:700 !important; }
[data-testid="stMetricDelta"]{ font-size:10px !important; }

:root{ --kpi-h:112px; }

/* 가로 블록이 자식들을 같은 높이로 */
[data-testid="stHorizontalBlock"]{
  align-items: stretch !important;
}

/* 컬럼 트리 전부 flex로 100% 전파 */
[data-testid="stHorizontalBlock"] > div,
[data-testid="column"] > div,
[data-testid="stVerticalBlock"],
[data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stElementContainer"]{
  display:flex !important;
  flex:1 1 auto !important;
  height:100% !important;
}

/* 최종 박스 높이 고정 */
[data-testid="stMetric"]{
  height:var(--kpi-h) !important;
  min-height:var(--kpi-h) !important;
  max-height:var(--kpi-h) !important;
  display:flex !important;
  flex-direction:column !important;
  justify-content:center !important;
  align-items:center !important;
  margin:0 !important;
  padding:6px 8px !important;
}

/* 여백으로 인한 흔들림 제거 */
[data-testid="column"]{ padding:0 !important; }
[data-testid="stVerticalBlock"]{ margin:0 !important; padding:0 !important; }


"""
st.markdown(f"<style>{BASE_CSS}</style>", unsafe_allow_html=True)

# ---------- State ----------
S = st.session_state
if "mode" not in S: S.mode = "landing"
if "messages" not in S: S.messages = []
if "area" not in S: S.area = AREA_DEFAULT
if "category" not in S: S.category = CATEGORY_DEFAULT

# ---------- Dummy reviews ----------
def _stamp(minutes_ago: int) -> str:
    return (datetime.now() - timedelta(minutes=minutes_ago)).strftime("오늘 %H:%M")

def get_dummy_reviews(area: str, category: str) -> dict[str, list[dict]]:
    visit = [
        {"ts": _stamp(3),  "mode": "방문", "platform": "네이버리뷰", "text": "야키토리 굽기 좋고 소스 과하지 않음."},
        {"ts": _stamp(12), "mode": "방문", "platform": "구글리뷰",   "text": "사케 구성이 다양. 직원 안내 친절."},
        {"ts": _stamp(26), "mode": "방문", "platform": "네이버리뷰", "text": "니쿠자가 달지 않고 균형 좋음."},
    ]
    delivery = [
        {"ts": _stamp(8),  "mode": "배달", "platform": "배달의민족", "text": "가라아게 바삭. 소스는 별도 포장 깔끔."},
        {"ts": _stamp(18), "mode": "배달", "platform": "요기요",     "text": "이카야키 식감 좋고 포장 견고."},
        {"ts": _stamp(44), "mode": "배달", "platform": "쿠팡이츠",   "text": "모듬꼬치 온도 유지 잘 됨."},
    ]
    if visit:
        visit[0]["text"] = f"[{area}/{category}] " + visit[0]["text"]
    return {"visit": visit, "delivery": delivery}

def ticker_items(area: str, category: str) -> list[str]:
    data = get_dummy_reviews(area, category)
    rows = sorted(data["visit"] + data["delivery"], key=lambda x: x["ts"], reverse=True)
    return [f"{r['ts']} · {r['mode']} · {r['platform']} · {r['text']}" for r in rows]

def render_review_ticker_js(area: str, category: str) -> None:
    if st.session_state.get("mode") == "chat":
        return
    items = json.dumps(ticker_items(area, category), ensure_ascii=False)
    component_html(
        f"""
<div class="ticker" id="review-ticker">🗞️ <span id="rtxt"></span></div>
<script>
const items = {items};
let i = 0;
function tick(){{
  const el = document.getElementById('rtxt');
  if(!el) return;
  el.textContent = items[i % items.length];
  i++;
}}
tick();
setInterval(tick, 5000);
</script>
""",
        height=48,
    )

# ---------- Data helpers ----------
def get_dashboard_context(area: str, category: str):
    DEMO_MCTS = {
        ("성수", "이자카야"): "AAA80B422A",
        ("성수", "카페"): "D2E6E383CD",
        ("뚝섬", "이자카야"): "1F7D63C933",
        ("뚝섬", "카페"): "0F646F50F7",
    }
    mct = DEMO_MCTS.get((area, category))
    if not mct:
        return None
    end = datetime.today().replace(day=1)
    start = end - timedelta(days=365)
    return build_dashboard_cards(mct=mct, start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))

def _filter_kpi_context(ctx):
    """
    render_dashboard()에 넘기기 전 불필요 카드 제거.
    title 또는 id 키에 다음 키워드 포함 시 제외:
      - '업종 내 백분위'
      - '업종대비 건수지수'
      - '배달 비중'
    """
    if not ctx:
        return ctx
    keys = ("items", "cards", "metrics", "data")  # 구현체 다양성 대응
    targets = None
    for k in keys:
        if isinstance(ctx.get(k), list):
            targets = ctx[k]
            container_key = k
            break
    if targets is None:
        return ctx

    EXCLUDE_SUBSTR = ["업종 내 백분위", "업종대비 건수지수", "배달 비중"]
    def keep(item):
        t = str(item.get("title") or item.get("name") or "")
        i = str(item.get("id") or "")
        return not any(s in t or s in i for s in EXCLUDE_SUBSTR)

    new_list = [it for it in targets if keep(it)]
    new_ctx = dict(ctx)
    new_ctx[container_key] = new_list
    return new_ctx

def render_reviews_panel(area: str, category: str) -> None:
    data = get_dummy_reviews(area, category)
    visit_html = "".join(
        f"<div class='review-item'>• {r['ts']} · {r['mode']} · {r['platform']} · {r['text']}</div>" for r in data["visit"]
    )
    deli_html = "".join(
        f"<div class='review-item'>• {r['ts']} · {r['mode']} · {r['platform']} · {r['text']}</div>" for r in data["delivery"]
    )
    st.markdown(
        f"""
<div class='reviews-panel'>
  <div class='reviews-title'>오늘 리뷰(샘플)</div>
  <div class='rev-grid'>
    <div>
      <div class='review-col-title'>방문</div>
      {visit_html}
    </div>
    <div>
      <div class='review-col-title'>배달</div>
      {deli_html}
    </div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

# ---------- UI ----------
S = st.session_state
if S.mode == "landing":
    # top
    st.markdown('<div class="toprow"><div class="brand-title-left">{}</div></div>'.format(BRAND), unsafe_allow_html=True)

    # hero
    st.markdown(
        f"""
<div class="hero">
  <div class="kicker">Demo</div>
  <h1><span class="highlight">{S.area}</span>에서 <span class="highlight">{S.category}</span>를 운영하는 당신을 위한 <span class="highlight-brand">세일즈 어드바이저</span></h1>
  <div class="hero-controls" id="hero-controls"></div>
</div>
""",
        unsafe_allow_html=True,
    )
    controls_container = st.container()
    with controls_container:
        cA, cB = st.columns(2)
        with cA:
            st.markdown('<span class="small-label">상권</span>', unsafe_allow_html=True)
            _areas = ["성수", "뚝섬"]
            S.area = st.selectbox("", _areas, index=_areas.index(S.area) if S.area in _areas else 0,
                                  label_visibility="collapsed", key="area_select_small")
        with cB:
            st.markdown('<span class="small-label">업종</span>', unsafe_allow_html=True)
            _cats = ["카페", "이자카야"]
            S.category = st.selectbox("", _cats, index=_cats.index(S.category) if S.category in _cats else 0,
                                      label_visibility="collapsed", key="category_select_small")
    st.markdown(
        """
<script>
const host = document.getElementById('hero-controls');
const block = document.currentScript.previousElementSibling;
if (host && block) host.appendChild(block);
</script>
""",
        unsafe_allow_html=True,
    )

    # 리뷰 티커
    render_review_ticker_js(S.area, S.category)

    # === 챗봇 질문: 보고서 위로 이동 ===
    st.markdown("<div class='report-row'></div>", unsafe_allow_html=True)
    q1, q2 = st.columns([6, 2], gap="small")
    with q1:
        query = st.text_input(" ", placeholder="예: 지난달 리뷰에서 가장 많이 언급된 불만은?",
                              label_visibility="collapsed", key="landing_query")
    with q2:
        go_chat = st.button("챗봇에게 물어보기", use_container_width=True)

    # 보고서 버튼과 설명
    st.markdown("<div class='report-row'></div>", unsafe_allow_html=True)
    rr1, rr2 = st.columns([1.6, 4], gap="small")
    with rr1:
        open_report = st.button("📄 마케팅 보고서", use_container_width=True)
    with rr2:
        st.markdown("<div class='report-desc'>최근 리뷰와 업종 트렌드를 반영한 맞춤 보고서를 확인하세요.</div>", unsafe_allow_html=True)
    if open_report:
        with st.expander("📄 마케팅 보고서", expanded=True):
            # area/category 조합에 따른 DEMO MCT 매핑 유지
            DEMO_MCTS = {
                ("성수", "이자카야"): "AAA80B422A",
                ("성수", "카페"): "D2E6E383CD",
                ("뚝섬", "이자카야"): "1F7D63C933",
                ("뚝섬", "카페"): "0F646F50F7",
            }
            mct = DEMO_MCTS.get((S.area, S.category))
            if mct:
                marketing_report.render_report(mct)
            else:
                st.warning("선택된 상권/업종에 해당하는 가맹점이 없습니다.")

    # KPI 영역
    ctx = get_dashboard_context(S.area, S.category)
    if not ctx:
        st.warning(f"{S.area}/{S.category} 데이터가 없습니다.")
    else:
        st.markdown('<div class="kpi-title">📊 최근 주요 지표</div>', unsafe_allow_html=True)
        st.markdown('<div class="kpi-wrap">', unsafe_allow_html=True)
        filtered_ctx = _filter_kpi_context(ctx)
        render_dashboard(filtered_ctx)
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown("---")

    # 오늘 리뷰(샘플)
    render_reviews_panel(S.area, S.category)

    # 채팅 전환
    if go_chat and (query or "").strip():
        S.messages = [
            {"role": "user", "content": query.strip()},
            {"role": "assistant", "content": "요청을 확인했습니다. 계속 질문하세요."},
        ]
        S.ctx_area = S.area
        S.ctx_category = S.category
        S.mode = "chat"
        st.rerun()

# -------- Chat --------
if S.mode == "chat":
    from ui.chat_view import render_chat
    render_chat()
