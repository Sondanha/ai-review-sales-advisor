-- RAW 수집 테이블: CSV 헤더와 1:1 매칭
create table if not exists public.stg_merchant_overview (
  ENCODED_MCT         text    not null primary key,
  MCT_BSE_AR          text    not null,
  MCT_NM              text    not null,
  MCT_BRD_NUM         text,
  MCT_SIGUNGU_NM      text    not null,
  HPSN_MCT_ZCD_NM     text    not null,
  HPSN_MCT_BZN_CD_NM  text,
  ARE_D               text    not null,   -- YYYY-MM-DD 문자열
  MCT_ME_D            text                -- YYYY-MM-DD 문자열 또는 빈값
);

create index if not exists idx_stg_overview_sigungu on public.stg_merchant_overview(MCT_SIGUNGU_NM);
create index if not exists idx_stg_overview_category on public.stg_merchant_overview(HPSN_MCT_ZCD_NM);

create table if not exists public.stg_merchant_monthly_usage (
  ENCODED_MCT                text    not null,
  TA_YM                      text    not null, -- YYYYMM
  MCT_OPE_MS_CN              text    not null,
  RC_M1_SAA                  text    not null,
  RC_M1_TO_UE_CT             text    not null,
  RC_M1_UE_CUS_CN            text    not null,
  RC_M1_AV_NP_AT             text    not null,
  APV_CE_RAT                 text,            -- 구간값(문자)
  DLV_SAA_RAT                numeric not null,
  M1_SME_RY_SAA_RAT          numeric not null,
  M1_SME_RY_CNT_RAT          numeric not null,
  M12_SME_RY_SAA_PCE_RT      numeric not null,
  M12_SME_BZN_SAA_PCE_RT     numeric not null,
  M12_SME_RY_ME_MCT_RAT      numeric not null,
  M12_SME_BZN_ME_MCT_RAT     numeric not null,
  primary key (ENCODED_MCT, TA_YM),
  foreign key (ENCODED_MCT) references public.stg_merchant_overview(ENCODED_MCT)
);

create index if not exists idx_stg_usage_mct_ym on public.stg_merchant_monthly_usage(ENCODED_MCT, TA_YM);

create table if not exists public.stg_merchant_monthly_customers (
  ENCODED_MCT                   text    not null,
  TA_YM                         text    not null, -- YYYYMM
  M12_MAL_1020_RAT              numeric not null,
  M12_MAL_30_RAT                numeric not null,
  M12_MAL_40_RAT                numeric not null,
  M12_MAL_50_RAT                numeric not null,
  M12_MAL_60_RAT                numeric not null,
  M12_FME_1020_RAT              numeric not null,
  M12_FME_30_RAT                numeric not null,
  M12_FME_40_RAT                numeric not null,
  M12_FME_50_RAT                numeric not null,
  M12_FME_60_RAT                numeric not null,
  MCT_UE_CLN_REU_RAT            numeric not null,
  MCT_UE_CLN_NEW_RAT            numeric not null,
  RC_M1_SHC_RSD_UE_CLN_RAT      numeric not null,
  RC_M1_SHC_WP_UE_CLN_RAT       numeric not null,
  RC_M1_SHC_FLP_UE_CLN_RAT      numeric not null,
  primary key (ENCODED_MCT, TA_YM),
  foreign key (ENCODED_MCT) references public.stg_merchant_overview(ENCODED_MCT)
);

create index if not exists idx_stg_cust_mct_ym on public.stg_merchant_monthly_customers(ENCODED_MCT, TA_YM);

-- 정규화 뷰: 앱에서 참조
create or replace view public.merchant_overview as
select
  ENCODED_MCT                                   as encoded_mct,
  MCT_BSE_AR                                    as addr,
  MCT_NM                                        as mct_name,
  MCT_BRD_NUM                                   as brand_code,
  MCT_SIGUNGU_NM                                as sigungu,
  HPSN_MCT_ZCD_NM                               as category,
  HPSN_MCT_BZN_CD_NM                            as biz_area,
  to_date(ARE_D, 'YYYY-MM-DD')                  as opened_on,
  to_date(nullif(MCT_ME_D,''), 'YYYY-MM-DD')    as closed_on
from public.stg_merchant_overview;

create or replace view public.merchant_monthly_usage as
select
  u.ENCODED_MCT                                  as encoded_mct,
  to_date(u.TA_YM, 'YYYYMM')                     as month,
  u.MCT_OPE_MS_CN                                as ope_months_bucket,
  u.RC_M1_SAA                                    as sales_bucket,
  u.RC_M1_TO_UE_CT                               as trx_bucket,
  u.RC_M1_UE_CUS_CN                              as uniq_cus_bucket,
  u.RC_M1_AV_NP_AT                               as aov_bucket,
  u.APV_CE_RAT                                   as cancel_bucket,
  nullif(u.DLV_SAA_RAT,              -999999.9)  as delivery_ratio,
  nullif(u.M1_SME_RY_SAA_RAT,        -999999.9)  as peer_industry_sales_ratio,
  nullif(u.M1_SME_RY_CNT_RAT,        -999999.9)  as peer_industry_trx_ratio,
  nullif(u.M12_SME_RY_SAA_PCE_RT,    -999999.9)  as industry_rank_pct,
  nullif(u.M12_SME_BZN_SAA_PCE_RT,   -999999.9)  as bizarea_rank_pct,
  nullif(u.M12_SME_RY_ME_MCT_RAT,    -999999.9)  as industry_churn_ratio,
  nullif(u.M12_SME_BZN_ME_MCT_RAT,   -999999.9)  as bizarea_churn_ratio
from public.stg_merchant_monthly_usage u;

create or replace view public.merchant_monthly_customers as
select
  c.ENCODED_MCT                                as encoded_mct,
  to_date(c.TA_YM, 'YYYYMM')                   as month,
  nullif(c.M12_MAL_1020_RAT,      -999999.9)   as male_u20_ratio,
  nullif(c.M12_MAL_30_RAT,        -999999.9)   as male_30_ratio,
  nullif(c.M12_MAL_40_RAT,        -999999.9)   as male_40_ratio,
  nullif(c.M12_MAL_50_RAT,        -999999.9)   as male_50_ratio,
  nullif(c.M12_MAL_60_RAT,        -999999.9)   as male_60p_ratio,
  nullif(c.M12_FME_1020_RAT,      -999999.9)   as female_u20_ratio,
  nullif(c.M12_FME_30_RAT,        -999999.9)   as female_30_ratio,
  nullif(c.M12_FME_40_RAT,        -999999.9)   as female_40_ratio,
  nullif(c.M12_FME_50_RAT,        -999999.9)   as female_50_ratio,
  nullif(c.M12_FME_60_RAT,        -999999.9)   as female_60p_ratio,
  nullif(c.MCT_UE_CLN_REU_RAT,    -999999.9)   as revisit_ratio,
  nullif(c.MCT_UE_CLN_NEW_RAT,    -999999.9)   as new_cus_ratio,
  nullif(c.RC_M1_SHC_RSD_UE_CLN_RAT, -999999.9) as residential_use_ratio,
  nullif(c.RC_M1_SHC_WP_UE_CLN_RAT,  -999999.9) as workplace_use_ratio,
  nullif(c.RC_M1_SHC_FLP_UE_CLN_RAT, -999999.9) as floating_use_ratio
from public.stg_merchant_monthly_customers c;
