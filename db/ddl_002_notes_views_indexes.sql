-- 참고용 메모: 뷰 기준의 앱 스키마 요약
-- merchant_overview(encoded_mct, addr, mct_name, brand_code, sigungu, category, biz_area, opened_on, closed_on)
-- merchant_monthly_usage(encoded_mct, month, ope_months_bucket, sales_bucket, trx_bucket, uniq_cus_bucket, aov_bucket, cancel_bucket,
--                        delivery_ratio, peer_industry_sales_ratio, peer_industry_trx_ratio, industry_rank_pct, bizarea_rank_pct,
--                        industry_churn_ratio, bizarea_churn_ratio)
-- merchant_monthly_customers(encoded_mct, month, male_u20_ratio, male_30_ratio, male_40_ratio, male_50_ratio, male_60p_ratio,
--                            female_u20_ratio, female_30_ratio, female_40_ratio, female_50_ratio, female_60p_ratio,
--                            revisit_ratio, new_cus_ratio, residential_use_ratio, workplace_use_ratio, floating_use_ratio)

-- 조인 최적화를 위한 RAW 인덱스 권장(이미 생성됨 확인용)
-- create index if not exists idx_stg_usage_mct_ym on public.stg_merchant_monthly_usage(ENCODED_MCT, TA_YM);
-- create index if not exists idx_stg_cust_mct_ym  on public.stg_merchant_monthly_customers(ENCODED_MCT, TA_YM);

-- 예시 질의: 월별 메트릭 결합
with u as (
  select encoded_mct, month, delivery_ratio
  from public.merchant_monthly_usage
  where encoded_mct = :mct and month between :m0 and :m1
),
c as (
  select encoded_mct, month,
         jsonb_build_object(
           'male', jsonb_build_object('u20', male_u20_ratio,'30', male_30_ratio,'40', male_40_ratio,'50', male_50_ratio,'60p', male_60p_ratio),
           'female', jsonb_build_object('u20', female_u20_ratio,'30', female_30_ratio,'40', female_40_ratio,'50', female_50_ratio,'60p', female_60p_ratio),
           'behavior', jsonb_build_object('revisit', revisit_ratio,'new', new_cus_ratio,'residential', residential_use_ratio,'workplace', workplace_use_ratio,'floating', floating_use_ratio)
         ) as demo
  from public.merchant_monthly_customers
  where encoded_mct = :mct and month between :m0 and :m1
)
select u.month, u.delivery_ratio, coalesce(c.demo, '{}'::jsonb) as demographics
from u left join c using(encoded_mct, month)
order by u.month;

-- CSV 임포트 대상: stg_* 3개. UTF-8, Header 포함, 빈값은 NULL 처리 권장.
