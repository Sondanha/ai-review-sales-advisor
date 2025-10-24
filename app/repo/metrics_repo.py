from typing import Any, Dict, List, Optional
from sqlalchemy import text
from app.deps import get_session

# 공통: 버킷 문자열 → 대표값(중앙값) 변환
# 예시: '2_10-25%' → 0.175, '25-50' → 37.5, '90%초과' → 0.95 (편의치)
_BUCKET_VALUE_SQL = """
-- 가장 오른쪽 토큰만 사용(예: '2_10-25%' → '10-25%')
with x as (
  select
    regexp_replace(:raw, '.*_', '') as t
),
y as (
  select t,
         case
           when t ~ '^[0-9]+$' then (t)::numeric
           when t ~ '^[0-9]+[^0-9]+[0-9]+%$' then (
             ((regexp_match(t,'([0-9]+)'))[1])::numeric + (regexp_match(t,'([0-9]+)$'))[1]::numeric
           )/2/100.0
           when t ~ '^[0-9]+[^0-9]+[0-9]+$' then (
             ((regexp_match(t,'([0-9]+)'))[1])::numeric + (regexp_match(t,'([0-9]+)$'))[1]::numeric
           )/2
           when t like '90%%' then 0.95      -- (%초과 구간 대표값)
           when t like '10%%이하' then 0.05   -- (이하 구간 대표값)
           else null
         end as v
  from x
)
select v from y
"""

# 기간별 시계열 + 비교지표
_SQL_TIMESERIES = text("""
with u as (
  select
    to_date(ta_ym,'YYYYMM')::date as month,
    regexp_replace(rc_m1_saa, '.*_', '')     as sales_bucket_raw,
    regexp_replace(rc_m1_to_ue_ct, '.*_', '') as visits_bucket_raw,
    greatest(dlv_saa_rat::numeric, 0)        as delivery_ratio,
    nullif(m1_sme_ry_saa_rat, -999999.9)     as peer_ind_sales_idx,   -- 동종업종 매출지수(=100 평균)
    nullif(m1_sme_ry_cnt_rat, -999999.9)     as peer_ind_cnt_idx,     -- 동종업종 건수지수
    nullif(m12_sme_ry_saa_pce_rt, -999999.9) as ind_rank_pct,         -- 업종 내 백분위(낮을수록 상위)
    nullif(m12_sme_bzn_saa_pce_rt, -999999.9) as area_rank_pct        -- 상권 내 백분위
  from public.stg_merchant_monthly_usage
  where encoded_mct = :m
    and to_date(ta_ym,'YYYYMM') between :m0 and :m1
),
val as (
  select
    month,
    -- 버킷 중앙값 계산
    case
      when sales_bucket_raw ~ '%' then (
        (
          ((regexp_match(sales_bucket_raw,'([0-9]+)'))[1])::numeric +
          (regexp_match(sales_bucket_raw,'([0-9]+)'))[array_length(regexp_match(sales_bucket_raw,'([0-9]+)'),1)]::numeric
        )/2
      )/100.0
      when sales_bucket_raw ~ '^[0-9]+[^0-9]+[0-9]+$' then (
        ((regexp_match(sales_bucket_raw,'([0-9]+)'))[1])::numeric +
        (regexp_match(sales_bucket_raw,'([0-9]+)'))[array_length(regexp_match(sales_bucket_raw,'([0-9]+)'),1)]::numeric
      )/2
      when sales_bucket_raw ~ '^[0-9]+$' then (sales_bucket_raw)::numeric
      when sales_bucket_raw like '90%%' then 0.95
      when sales_bucket_raw like '10%%이하' then 0.05
      else null
    end as sales_value,
    case
      when visits_bucket_raw ~ '%' then (
        (
          ((regexp_match(visits_bucket_raw,'([0-9]+)'))[1])::numeric +
          (regexp_match(visits_bucket_raw,'([0-9]+)'))[array_length(regexp_match(visits_bucket_raw,'([0-9]+)'),1)]::numeric
        )/2
      )/100.0
      when visits_bucket_raw ~ '^[0-9]+[^0-9]+[0-9]+$' then (
        ((regexp_match(visits_bucket_raw,'([0-9]+)'))[1])::numeric +
        (regexp_match(visits_bucket_raw,'([0-9]+)'))[array_length(regexp_match(visits_bucket_raw,'([0-9]+)'),1)]::numeric
      )/2
      when visits_bucket_raw ~ '^[0-9]+$' then (visits_bucket_raw)::numeric
      when visits_bucket_raw like '90%%' then 0.95
      when visits_bucket_raw like '10%%이하' then 0.05
      else null
    end as visits_value,
    delivery_ratio,
    peer_ind_sales_idx,
    peer_ind_cnt_idx,
    ind_rank_pct,
    area_rank_pct
  from u
),
c as (
  select
    to_date(c.ta_ym,'YYYYMM')::date as month,
    nullif(m12_mal_1020_rat, -999999.9) as mal_1020,
    nullif(m12_mal_30_rat , -999999.9) as mal_30,
    nullif(m12_mal_40_rat , -999999.9) as mal_40,
    nullif(m12_mal_50_rat , -999999.9) as mal_50,
    nullif(m12_mal_60_rat , -999999.9) as mal_60,
    nullif(m12_fme_1020_rat, -999999.9) as fme_1020,
    nullif(m12_fme_30_rat , -999999.9) as fme_30,
    nullif(m12_fme_40_rat , -999999.9) as fme_40,
    nullif(m12_fme_50_rat , -999999.9) as fme_50,
    nullif(m12_fme_60_rat , -999999.9) as fme_60,
    nullif(mct_ue_cln_reu_rat, -999999.9) as revisit_ratio,
    nullif(mct_ue_cln_new_rat, -999999.9) as new_ratio,
    nullif(rc_m1_shc_rsd_ue_cln_rat, -999999.9) as resident_ratio,
    nullif(rc_m1_shc_wp_ue_cln_rat , -999999.9) as worker_ratio,
    nullif(rc_m1_shc_flp_ue_cln_rat, -999999.9) as floating_ratio
  from public.stg_merchant_monthly_customers c
  where c.encoded_mct = :m
    and to_date(c.ta_ym,'YYYYMM') between :m0 and :m1
)
select
  v.month,
  v.sales_value        as sales,      -- 0~1(%) 혹은 절대값 버킷 대표값
  v.visits_value       as visits,
  v.delivery_ratio,
  v.peer_ind_sales_idx,
  v.peer_ind_cnt_idx,
  v.ind_rank_pct,
  v.area_rank_pct,
  jsonb_build_object(
    'male',  (c.mal_1020 + c.mal_30 + c.mal_40 + c.mal_50 + c.mal_60),
    'female',(c.fme_1020 + c.fme_30 + c.fme_40 + c.fme_50 + c.fme_60),
    'age',   jsonb_build_object(
               'm_1020', c.mal_1020, 'm_30', c.mal_30, 'm_40', c.mal_40, 'm_50', c.mal_50, 'm_60', c.mal_60,
               'f_1020', c.fme_1020, 'f_30', c.fme_30, 'f_40', c.fme_40, 'f_50', c.fme_50, 'f_60', c.fme_60
             ),
    'visit', jsonb_build_object(
               'new', c.new_ratio, 'revisit', c.revisit_ratio
             ),
    'affinity', jsonb_build_object(
               'resident', c.resident_ratio, 'worker', c.worker_ratio, 'floating', c.floating_ratio
             )
  ) as demographics
from val v
left join c on c.month = v.month
order by v.month;
""")

# 최신 스냅샷 + 개요(업종/상권)
_SQL_SNAPSHOT = text("""
with mm as (
  select max(to_date(ta_ym,'YYYYMM')::date) as last_month
  from public.stg_merchant_monthly_usage
  where encoded_mct = :m
),
ov as (
  select
    o.encoded_mct,
    o.hpsn_mct_zcd_nm as industry,
    o.hpsn_mct_bzn_cd_nm as bizarea,
    o.mct_nm as name
  from public.stg_merchant_overview o
  where o.encoded_mct = :m
),
ts as (
  select * from public.stg_merchant_monthly_usage u
  where u.encoded_mct = :m and to_date(u.ta_ym,'YYYYMM')::date = (select last_month from mm)
)
select
  (select last_month from mm) as month,
  (select name from ov) as name,
  (select industry from ov) as industry,
  (select bizarea from ov) as bizarea,
  regexp_replace(ts.rc_m1_saa,'.*_','') as sales_bucket,
  regexp_replace(ts.rc_m1_to_ue_ct,'.*_','') as visits_bucket,
  greatest(ts.dlv_saa_rat::numeric,0) as delivery_ratio,
  nullif(ts.m1_sme_ry_saa_rat,-999999.9) as peer_ind_sales_idx,
  nullif(ts.m1_sme_ry_cnt_rat,-999999.9) as peer_ind_cnt_idx,
  nullif(ts.m12_sme_ry_saa_pce_rt,-999999.9) as ind_rank_pct,
  nullif(ts.m12_sme_bzn_saa_pce_rt,-999999.9) as area_rank_pct
from ts
""")

def fetch_timeseries(mct: str, m0: str, m1: str) -> List[Dict[str, Any]]:
    with get_session() as s:
        rows = s.execute(_SQL_TIMESERIES, {"m": mct, "m0": m0, "m1": m1}).mappings().all()
    return [dict(r) for r in rows]

def fetch_snapshot(mct: str) -> Optional[Dict[str, Any]]:
    with get_session() as s:
        row = s.execute(_SQL_SNAPSHOT, {"m": mct}).mappings().first()
    return dict(row) if row else None
