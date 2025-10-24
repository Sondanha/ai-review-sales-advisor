import streamlit as st
from typing import Dict, Any, List

def render_cards(card_items: List[Dict[str, Any]]) -> None:
    if not card_items:
        st.info("데이터 없음")
        return
    n = len(card_items)
    cols = st.columns(min(4, n))
    for i, item in enumerate(card_items):
        with cols[i % len(cols)]:
            with st.container(border=True):
                st.caption(item.get("title",""))
                st.metric(
                    label="KPI",  
                    value=item.get("value","-"),
                    delta=item.get("delta",""),
                    help=item.get("tooltip","")
                )
                
                if item.get("badge"):
                    st.write(item["badge"])

def render_dashboard(context: Dict[str, Any]) -> None:
    m = context.get("merchant", {})
    st.subheader(f"{m.get('name','')} · {m.get('industry','')}/{m.get('bizarea','')}")
    render_cards(context.get("cards", []))
    with st.expander("LLM 참고용 시계열 원자료"):
        st.json(context.get("timeseries", []))
