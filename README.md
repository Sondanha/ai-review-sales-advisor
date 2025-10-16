# AI Review & Sales Advisor

요식업 사장님을 위한 **데이터 기반 마케팅 도우미**.
리뷰(배민·요기요·쿠팡이츠·네이버) + 카드사 월별 데이터(매출/고객/순위)를 통합 분석하여 **챗봇 컨설팅**과 **보고서 자동 생성**을 제공.

<br>

## 핵심 기능

- **챗봇**: LangGraph + Gemini 2.5 Flash. 대화 컨텍스트 유지. DB 실시간 조회.
- **리뷰 리스너**: 일일 리뷰 수집·감정점수(0–100)·키워드/아스펙트 트렌드·액션 제안.
- **월별 인사이트**: 동종업계 상위군 대비 격차 분석. 고객층 변화. 실행전략 Top-N.
- **보고서/PDF**: 보고서 JSON 스냅샷 저장. PDF/CSV 내보내기.

<br>

## 아키텍처

```mermaid
flowchart TD
  U[Streamlit UI] --> A[FastAPI + LangGraph]
  A -->|SQL| DB[(PostgreSQL)]
  A --> LLM[Gemini 2.5 Flash]
  subgraph ETL
    C1[Review Collector] --> DB
    C2[Card CSV Loader] --> DB
  end
  A --> REP[Reporter/PDF Export]
```

<br>

## 기술 스택

- UI: Streamlit
- API: FastAPI
- Orchestration: LangGraph
- LLM: Gemini 2.5 Flash (파인튜닝 없음)
- DB: PostgreSQL (Managed: Neon/Supabase 권장)
- 분석: pandas, scikit-learn(경량 규칙/스코어링)
- 마이그레이션: Alembic

<br>

## 폴더 구조

```graphql
ai-review-sales-advisor/
├─ app/
│  ├─ main.py                 # FastAPI 엔트리 (헬스체크, 챗, 보고서 API)
│  ├─ deps.py                 # DI, DB 세션, 설정
│  ├─ routers/
│  │  ├─ chat.py              # /api/chat (LangGraph 실행)
│  │  ├─ report.py            # 보고서 생성/조회/내보내기
│  │  └─ merchant.py          # 매장 조회, 매핑
│  └─ services/
│     ├─ graph.py             # LangGraph 그래프 정의(노드/엣지)
│     ├─ analyzer.py          # 시계열/격차/z-score/룰 평가
│     ├─ recommender.py       # 액션 추천 룰셋 적용
│     ├─ llm.py               # Gemini 호출 래퍼
│     └─ exporter.py          # PDF/CSV 생성
├─ etl/
│  ├─ reviews_ingest.py       # 리뷰 수집/정규화/감정·키워드
│  └─ card_ingest.py          # 카드사 CSV→DB upsert
├─ db/
│  ├─ models.py               # SQLAlchemy 모델
│  ├─ schema.sql              # 초기 DDL (뷰/MV 포함)
│  └─ migrations/             # Alembic 리비전
├─ ui/
│  ├─ Dashboard.py            # Streamlit 대시보드
│  └─ Chat.py                 # Streamlit 챗 UI
├─ configs/
│  ├─ rules.json              # 액션 추천 룰셋
│  └─ aspects.json            # 아스펙트 사전(맛/양/가격/서비스/포장/속도/위생)
├─ tests/
│  ├─ test_analyzer.py
│  └─ test_routers.py
├─ .env.example
├─ requirements.txt
├─ README.md
└─ run_dev.sh                 # 개발용 실행 스크립트(선택)
```

<br>

## 환경 변수(.env)

```env
ENV=dev
LOG_LEVEL=INFO
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/dbname
GEMINI_API_KEY=your_api_key
```

<br>

## 초기 세팅

```bash
# Python 3.11 권장
python -m pip install -U pip setuptools wheel
pip install -r requirements.txt

# DB 마이그레이션(Alembic)
alembic init db/migrations
# (env.py 에 DATABASE_URL 연결 후)
alembic revision -m "init schema"
alembic upgrade head
# 또는 db/schema.sql을 한 번에 실행
```

<br>

## 실행

### API 서버

```bash
uvicorn app.main:app --reload --port 8000
```

### Streamlit

```bash
streamlit run ui/Dashboard.py
# 또는
streamlit run ui/Chat.py
```

<br>

## LangGraph 워크플로우 개요

- **노드**: Guardrail → IntentRouter → ParamResolver → MemoryLoader →
  DataPlanner → DBFetcher → Analyzer → ActionRecommender → LLMFormatter →
  [Reporter] → [Exporter] → MemorySummarizer → Responder
- **메모리**: rolling 8–12턴 + summary 1개 + facts 캐시(DB 테이블)
- **벡터DB**: 기본 미사용. 필요 시 pgvector 옵션 투입.

Mermaid(세부):

```mermaid
flowchart TD
  A[Guardrail] --> B{IntentRouter}
  B --> C[ParamResolver]
  C --> D[MemoryLoader]
  D --> E[DataPlanner]
  E --> F[DBFetcher]
  F --> G[Analyzer]
  G --> H[ActionRecommender]
  H --> I[LLMFormatter]
  I --> J{Report?}
  J -->|Yes| K[Reporter]
  I --> L{Export?}
  L -->|Yes| M[Exporter]
  I --> N{Summarize?}
  N -->|Yes| O[MemorySummarizer]
  I --> P[Responder]
  K --> P
  M --> P
  O --> P
```

<br>

## 데이터 모델(요약)

- `merchant`(기본정보)
- `merchant_monthly_metrics`(매출/순위/배달비중 등)
- `merchant_monthly_demographics`(성·연령·방문유형)
- `daily_reviews`(raw_text, sentiment, aspects, keyphrases)
- `reports`(report_type, period, payload JSONB)
- `mv_review_daily`(감정·아스펙트 일별 집계 MV)

<br>

## 개발 현황 체크리스트

### Sprint-0: 환경/기초

- [ ] Python 3.11 venv 구성
- [ ] DB 연결(DATABASE_URL)
- [ ] Alembic 기본 설정 및 `init schema`
- [ ] `.env` 적용 테스트

### Sprint-1: 데이터/분석

- [ ] `daily_reviews` ETL v1(수동 CSV OK)
- [ ] 감정 점수화/아스펙트 추출 v1
- [ ] `merchant_monthly_*` 적재
- [ ] `mv_review_daily` 생성 및 검증

### Sprint-2: API/그래프

- [ ] LangGraph 그래프/노드 스켈레톤
- [ ] `/api/chat` 라우터 연결
- [ ] Analyzer/ActionRecommender v1
- [ ] Reporter JSON 스냅샷 저장

### Sprint-3: UI/배포

- [ ] Streamlit 대시보드 카드(리뷰/경고)
- [ ] 챗 UI 스트리밍 응답
- [ ] PDF/CSV 내보내기
- [ ] Managed Postgres(Neon/Supabase) 연결

### QA/데모

- [ ] 시나리오 3종 테스트(“오늘 리뷰 요약”, “월간 보고서”, “PDF 내보내”)
- [ ] 오류/결측 대체 응답 점검
- [ ] 데모 데이터 리셋 스크립트

<br>

## 커밋 가이드

- 태그 + 요약: (미정)
- 범주: (미정)

<br>

## 라이선스

프로토타입. 내부 검토 후 결정.

<br>

## 참고

- 무료 DB 권장: Neon(1순위) / Supabase(2순위).
- VS Code 기본 인터프리터: Python 3.11 고정.
