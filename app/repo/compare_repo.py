from sqlalchemy import text
from app.deps import get_session

SQL_COMPETITORS = text("""
with base as (
  select
    o.encoded_mct,
    o.mct_nm,
    o.hpsn_mct_bzn_cd_nm as bizarea,
    o.hpsn_mct_zcd_nm as industry,
    u.m1_sme_ry_saa_rat as ind_sales_idx,
    u.m12_sme_ry_saa_pce_rt as ind_rank_pct,
    u.m12_sme_bzn_saa_pce_rt as area_rank_pct
  from stg_merchant_overview o
  join stg_merchant_monthly_usage u using(encoded_mct)
  where to_date(u.ta_ym,'YYYYMM') = (
      select max(to_date(ta_ym,'YYYYMM')) from stg_merchant_monthly_usage
  )
),
target as (
  select bizarea, industry from base where encoded_mct = :mct
)
select b.encoded_mct, b.mct_nm, b.ind_sales_idx, b.ind_rank_pct, b.area_rank_pct
from base b join target t
  on b.bizarea = t.bizarea and b.industry = t.industry
where b.ind_sales_idx > 100
order by b.ind_sales_idx desc
limit 3;
""")

def fetch_top_competitors(mct: str):
    with get_session() as s:
        rows = s.execute(SQL_COMPETITORS, {"mct": mct}).mappings().all()
    return [dict(r) for r in rows]
