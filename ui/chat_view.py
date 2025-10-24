# ui/chat_view.py
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import time
import re
import streamlit as st
from streamlit.components.v1 import html as component_html

# (옵션) 응답 엔진 — 존재해도 규칙 기반을 우선 사용
try:
    from app.chat_core import build_chat_core_from_env
    CORE = build_chat_core_from_env()
except Exception:
    CORE = None

# ---------- 설정 ----------
DELAY_SEC = 5  

# ---------- CSS ----------
CHAT_CSS = r"""
.toprow, .brand-title-left, .ticker, #review-ticker, .reviews-panel, .hero { display:none !important; }
div[data-testid="stVerticalBlock"] div:has(> div#review-ticker) { display:none !important; }
section.main > div.block-container { padding-top: 0 !important; }

:root{
  --bg:#FFFFFF; --ink:#1B1F2A; --muted:#5B6475; --panel:#F7F8FB; --border:#E0E4EE;
  --bubble:#141A2A; --bubble-user:#0F1424; --ink-on:#E6EAF2;
}
@media (prefers-color-scheme: dark){
  :root{
    --bg:#0F1220; --ink:#E6EAF2; --muted:#9AA4B2; --panel:#141A2A; --border:rgba(255,255,255,.12);
    --bubble:#1A2235; --bubble-user:#0F1424; --ink-on:#E6EAF2;
  }
}
html, body, [data-testid="stAppViewContainer"]{ background:var(--bg); color:var(--ink); }
.chat-wrap { width:min(980px, 100%); margin: 8px auto 0 auto; }

.header-wrap{
  position: sticky; top: 0; z-index: 999; background: var(--bg);
  padding: 6px 6px 8px 6px; border-bottom: 1px solid var(--border); backdrop-filter: blur(4px);
}
.tags { display:flex; gap:6px; flex-wrap:wrap; align-items:center; margin-bottom:6px; }
.tag  { font-size:13px; padding:4px 10px; border:1px solid var(--border); border-radius:999px; background:var(--panel); }

.action-row { display:flex; gap:6px; flex-wrap:wrap; }
.small-btn button { font-size:13.5px !important; padding:3px 10px !important; border-radius:999px !important; height:auto !important; }

.msgs { padding:8px 2px 0 2px; }
.msg { display:flex; margin:8px 0; }
.bubble {
  max-width: 78%;
  padding:10px 12px; border-radius:14px; border:1px solid var(--border);
  box-shadow:0 2px 8px rgba(15,23,42,.08);
  font-size:14.5px; line-height:1.5; white-space:pre-wrap;
}
.msg.user { justify-content:flex-end; }
.msg.user .bubble { background:var(--bubble-user); color:var(--ink-on); }
.msg.assistant { justify-content:flex-start; }
.msg.assistant .bubble { background:var(--bubble); color:var(--ink-on); }

.footer { position:sticky; bottom:0; padding:8px 0 2px 0; background:linear-gradient(180deg, rgba(0,0,0,0), rgba(0,0,0,.02)); }
"""

# ---------- DEMO 스토리라인 답변 ----------
_DEMO_TEXT = {
    "summary": (
        "최근 몇 달간 매출 흐름은 안정적이에요. 큰 등락 없이 꾸준히 유지되고 있다는 건 고정 고객이 잘 잡혀 있다는 뜻입니다.\n"
        "상권 내 순위도 상위 10% 안에 들어 있고, 동종 업종 평균 대비 매출지수는 약 180~200 수준이에요.\n"
        "즉, 업종 평균보다 훨씬 높은 효율을 유지하면서도 고객 기반이 탄탄한 ‘안정 성장형’ 매장으로 볼 수 있습니다."
    ),
    "sales": (
        "매출 추이를 보면 월별 변동폭이 크지 않습니다. 급등락이 없다는 건 가격·메뉴·운영 리듬이 안정화되었음을 의미합니다.\n"
        "이럴 때는 주력 시간대에 소규모 타임딜을 얹어 ‘체감 성장’을 만드는 쪽이 효율적입니다."
    ),
    "rank": (
        "상권 내 순위는 연초 약 15%에서 최근 10% 내외로 개선되었습니다. 순위 지표는 낮을수록 상위입니다.\n"
        "현재 포지션을 유지하려면 주중 저녁 시간대의 체류가치(세트·좌석 경험·모바일 주문 편의)를 더 강화하는 것이 좋습니다."
    ),
    "peer": (
        "업종 평균 대비 매출지수는 대부분 150~200 구간이며 최근 210 수준까지 관측됩니다. 업계 평균(100)을 꾸준히 상회합니다.\n"
        "이는 객단가·회전율·구성비가 균형적임을 시사합니다. 신메뉴를 넣을 때도 평균 단가를 해치지 않는 구성이 중요합니다."
    ),
    "demo": (
        "우리 매장의 주요 고객층은 20대 초반 여성과 남성 고객이며 30대가 그 뒤를 잇습니다.\n"
        "이 연령대는 시각 경험과 인증에 민감합니다. 인스타 리그램 이벤트, 리뷰 인증 즉시 쿠폰, 포토존·짧은 영상 포맷이 잘 맞습니다."
    ),
    "comp": (
        "같은 상권 상위 매장들은 신메뉴·공간 사진을 자주 올리고, 후기 댓글에 빠르게 응답합니다.\n"
        "‘살아 있는 피드’가 브랜드 신뢰를 높여 신규 유입과 재방문을 동시에 끌어올립니다. 필요하면 고객 후기 리그램도 활용해 보세요."
    ),
    "action": (
        "재방문률이 30% 이하라면 첫 방문 다음 행동을 설계해야 합니다.\n"
        "① 스탬프 4+1 등 단기 보상\n② 리뷰 작성 즉시 다음 방문 할인쿠폰\n③ 방문 10~14일 후 리마인드 메시지\n"
        "혜택 자체보다 ‘적시에 자연스럽게 다시 떠오르게 하는 것’이 핵심입니다."
    ),
    "report": (
        "요약 보고서\n- 매출: 변동 적고 안정 유지\n- 순위: 상위 10%권 유지·개선\n- 업종 지수: 180~210으로 평균 상회\n"
        "- 고객층: 20대 중심\n- 제안: SNS 쿠폰형 참여 캠페인, 평일 저녁 타임딜, 14일 내 리마인드로 리텐션 강화"
    ),
    # 업종/과제 스토리라인용 추가 키
    "cafe_marketing": (
        "카페 업종 고객 특성 기반 채널·홍보안입니다.\n"
        "- 채널: 인스타그램·틱톡(짧은 영상), 네이버 플레이스(지도 진입), 카카오톡 채널(쿠폰 배포)\n"
        "- 메시지: 신메뉴 비주얼, 좌석·조명·음향 등 ‘머물 이유’ 강조, 인증샷 포인트\n"
        "- 포맷: 리그램/태그 이벤트, 스토리 하이라이트로 메뉴·공간·후기 분리, 주말/평일 타임별 스토리 업로드"
    ),
    "revisit_ideas": (
        "재방문률 30% 이하 개선 아이디어입니다.\n"
        "1) 첫 방문 영수증 쿠폰(7~14일 기한) 2) 적립 4+1·8+2 이원화 3) 스토어 내 미션(후기·사진 업로드) 즉시 보상\n"
        "4) 저매출 요일 타임 바우처 5) 구매 후 10~14일 리마인드 DM/알림톡. 측정은 쿠폰 코드·재구매 간격 기준으로 확인하세요."
    ),
    "fnb_diagnosis": (
        "요식 업종 공통 문제 진단과 개선 아이디어입니다.\n"
        "- 문제: 피크 의존도 높음, 객단가 낮음, 신규 유입 경로 단일화, 후기 관리 부족\n"
        "- 개선: 회전율 저해 요소 제거(동선·결제), 세트/업셀 제시문 표준화, ‘지도→방문’ 전환 캠페인, 후기 응답 SLA 24h\n"
        "운영·상품·홍보를 동시에 미세조정해야 체감 성과가 납니다."
    ),
    "fallback": (
        "원하시는 항목을 알려주세요. 예) 요약, 매출 추이, 상권 순위, 업종 평균 대비, 고객층, 경쟁점, 실행전략, 보고서 정리 등"
    ),
}

# ---------- 규칙 라우팅 ----------
_INTENTS = [
    (r"(요약|개요|요점|한줄|정리)", "summary"),
    (r"(매출|추이|그래프|월별)", "sales"),
    (r"(순위|랭크|상권)", "rank"),
    (r"(업종|평균|지수|동종|peer)", "peer"),
    (r"(고객|연령|성별|타겟|층)", "demo"),
    (r"(경쟁|상위|벤치마킹|비교)", "comp"),
    (r"(전략|제안|액션|프로모션|이벤트|쿠폰|리텐션)", "action"),
    (r"(보고서|리포트)", "report"),
    # 스토리라인 특화
    (r"(카페|coffee).*(채널|홍보|마케팅)", "cafe_marketing"),
    (r"(재방문|재구매|리텐션).*(아이디어|방법|전략|올리|향상)", "revisit_ideas"),
    (r"(요식|식당|외식).*(문제|진단|개선|아이디어)", "fnb_diagnosis"),
]

def _route_answer(user_text: str, area: str, category: str) -> str:
    t = (user_text or "").strip()
    low = t.lower()
    for pat, intent in _INTENTS:
        if re.search(pat, t) or re.search(pat, low):
            ans = _DEMO_TEXT.get(intent, _DEMO_TEXT["fallback"])
            return f"[{area}/{category}]\n{ans}"
    # 추가 자연어 패턴
    if "어떤 마케팅" in t or "전략" in t:
        return f"[{area}/{category}]\n{_DEMO_TEXT['cafe_marketing']}"
    if "재방문" in t or "다시 오" in t:
        return f"[{area}/{category}]\n{_DEMO_TEXT['revisit_ideas']}"
    if "문제점" in t or "진단" in t:
        return f"[{area}/{category}]\n{_DEMO_TEXT['fnb_diagnosis']}"
    return f"[{area}/{category}]\n{_DEMO_TEXT['summary']}"

# ---------- helpers ----------
def _append(role: str, content: str):
    st.session_state.messages.append({"role": role, "content": content})

def _stream_answer(prompt: str):
    area = st.session_state.get("ctx_area") or st.session_state.get("area") or "지역"
    category = st.session_state.get("ctx_category") or st.session_state.get("category") or "업종"
    text = _route_answer(prompt, area, category)
    # 답변 시작 전 지연
    time.sleep(DELAY_SEC)
    for ch in text:
        time.sleep(0.01)
        yield ch

# ---------- main ----------
def render_chat():
    S = st.session_state
    if "messages" not in S: S.messages = []
    if "show_report" not in S: S.show_report = False

    st.markdown(f"<style>{CHAT_CSS}</style>", unsafe_allow_html=True)

    area = S.get("ctx_area") or S.get("area") or "지역"
    category = S.get("ctx_category") or S.get("category") or "업종"

    # 헤더
    st.markdown('<div class="chat-wrap header-wrap">', unsafe_allow_html=True)
    st.markdown(
        f"""
<div class="tags">
  <span class="tag">상권: {area}</span>
  <span class="tag">업종: {category}</span>
</div>
""", unsafe_allow_html=True)

    st.markdown('<div class="action-row small-btn">', unsafe_allow_html=True)
    bc1, bc2, bc3 = st.columns([1,1,1])
    with bc1:
        if st.button("🏠 홈으로", use_container_width=True, key="btn_home"):
            S.mode = "landing"; S.show_report = False; st.rerun()
    with bc2:
        if st.button("📄 마케팅 보고서", use_container_width=True, key="btn_report"):
            S.show_report = True
    with bc3:
        if st.button("🗑 대화 초기화", use_container_width=True, key="btn_clear"):
            S.messages = []; S.show_report = False; st.rerun()
    st.markdown('</div></div>', unsafe_allow_html=True)

    # 잔존 블록 제거
    component_html("""
    <script>
    (function(){
      const root = document.querySelector('section.main > div.block-container');
      if(!root) return;
      const header = root.querySelector('.header-wrap');
      const anchor = header ? (header.closest('[data-testid="stVerticalBlock"],[data-testid="stElementContainer"]') || header) : null;
      if (!anchor) return;
      let sib = anchor.previousElementSibling;
      while (sib) { const prev = sib.previousElementSibling; sib.remove(); sib = prev; }
      const killers = ['.toprow','#review-ticker','.reviews-panel','.hero','.brand-title-left','.ticker'];
      killers.forEach(sel => {
        root.querySelectorAll(sel).forEach(el => {
          const wrap = el.closest('[data-testid="stVerticalBlock"],[data-testid="stElementContainer"]');
          if (wrap) wrap.remove(); else el.remove();
        });
      });
      const isVisual = el => el.matches('img,svg,video,iframe,canvas,button,input,textarea,[role="img"]');
      const isEmptyBlock = el => {
        if (!el) return false;
        const txt = el.innerText ? el.innerText.trim() : '';
        const hasVisual = el.querySelector(isVisual) !== null;
        const h = el.getBoundingClientRect().height;
        return txt === '' && !hasVisual && h < 8;
      };
      root.querySelectorAll('[data-testid="stElementContainer"],[data-testid="stVerticalBlock"],[data-testid="stHorizontalBlock"]').forEach(el=>{
        if (isEmptyBlock(el)) el.remove();
      });
      root.style.paddingTop = '0px';
    })();
    </script>
    """, height=0)

    # 보고서 미리보기
    if S.show_report:
        with st.expander("마케팅 보고서(미리보기)", expanded=True):
            st.write(_DEMO_TEXT["report"])

    # 메시지 렌더
    st.markdown('<div class="chat-wrap msgs">', unsafe_allow_html=True)
    for m in S.messages:
        cls = "user" if m["role"] == "user" else "assistant"
        st.markdown(f"""<div class="msg {cls}"><div class="bubble">{m['content']}</div></div>""",
                    unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # 입력창
    prompt = st.chat_input("", key="chat_input")
    if prompt and prompt.strip():
        user_text = prompt.strip()
        _append("user", user_text)

        placeholder = st.empty()
        acc = ""
        for token in _stream_answer(user_text):
            acc += token
            placeholder.markdown(
                f"""<div class="chat-wrap msgs"><div class="msg assistant"><div class="bubble">{acc}</div></div></div>""",
                unsafe_allow_html=True,
            )
        _append("assistant", acc)
        st.rerun()
