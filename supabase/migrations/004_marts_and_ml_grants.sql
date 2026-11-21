-- =============================================================================
-- Migration 004: ML Tables, All 12 Mart Objects, n>=5 Suppression & Grants
--                (T3.5, T3.6, T3.8, T4.6)
-- Project: Skill Demand Intelligence (E')
-- References: ARCHITECTURE.md §3.4, §3.5, §3.8 | PLAN.md D4, D5, D13, D14, D18
-- =============================================================================

-- 1. ML Experiment Tracking Tables (ARCHITECTURE.md §3.5)
--    Schema `ml` remains revoked from anon & authenticated.

create table if not exists ml.experiment (
  experiment_id   bigserial primary key,
  task            text not null default 'salary_regression',
  dataset_version text,
  n_rows          int,
  created_at      timestamptz default now()
);

create table if not exists ml.model_result (
  result_id     bigserial primary key,
  experiment_id bigint not null references ml.experiment (experiment_id) on delete cascade,
  model_name    text not null,
  fold          int not null,                 -- fold = -1 denotes cross-validation mean summary
  r2            numeric,
  rmse          numeric,
  mae           numeric,
  mape          numeric,
  fit_seconds   numeric,
  params        jsonb,
  is_champion   boolean not null default false
);

create index if not exists idx_ml_model_result_exp on ml.model_result (experiment_id, model_name, fold);

create table if not exists ml.feature_importance (
  experiment_id bigint not null references ml.experiment (experiment_id) on delete cascade,
  model_name    text not null,
  feature       text not null,
  importance    numeric not null
);

create index if not exists idx_ml_feature_imp_exp on ml.feature_importance (experiment_id, model_name);

-- 2. Public Mart Views (Aggregate only, n >= 5 suppression enforced)

-- 2.1 mart.skill_demand_weekly (weighted by sample_weight, active vs new counts)
create or replace view mart.skill_demand_weekly as
with posting_dates as (
  select
    f.posting_key,
    f.sample_weight,
    coalesce(l.region, 'ไม่ระบุ') as region,
    coalesce(l.province_th, 'ไม่ระบุ') as province_th,
    coalesce(l.is_south14, false) as is_south14,
    coalesce(d_first.full_date, d_posted.full_date) as first_seen_date,
    coalesce(d_last.full_date, d_first.full_date, d_posted.full_date) as last_seen_date
  from dw.fact_job_posting f
  left join dw.dim_location l on l.location_key = f.location_key
  left join dw.dim_date d_posted on d_posted.date_key = f.date_posted_key
  left join dw.dim_date d_first on d_first.date_key = f.first_seen_date_key
  left join dw.dim_date d_last on d_last.date_key = f.last_seen_date_key
  where coalesce(d_first.full_date, d_posted.full_date) is not null
),
date_bounds as (
  select
    date_trunc('week', min(first_seen_date))::date as min_week,
    date_trunc('week', max(last_seen_date))::date as max_week
  from posting_dates
),
weeks as (
  select gs::date as week_start
  from date_bounds b
  cross join lateral generate_series(b.min_week, b.max_week, interval '7 days') as gs
  where b.min_week is not null
),
active_postings as (
  select
    w.week_start,
    p.posting_key,
    p.sample_weight,
    p.region,
    p.province_th,
    p.is_south14,
    (date_trunc('week', p.first_seen_date)::date = w.week_start) as is_new
  from weeks w
  join posting_dates p
    on p.first_seen_date <= (w.week_start + 6)
   and p.last_seen_date >= w.week_start
),
scope_totals as (
  select
    week_start,
    case
      when grouping(region) = 1 then 'national'
      when grouping(province_th) = 1 then 'region'
      else 'province'
    end as scope_level,
    case when grouping(region) = 1 then 'ทั้งประเทศ' else region end as region,
    case
      when grouping(region) = 1 then 'ทั้งประเทศ'
      when grouping(province_th) = 1 then 'ทั้งหมดในภาค'
      else province_th
    end as province_th,
    case
      when grouping(province_th) = 0 then is_south14
      when grouping(region) = 0 then (region = 'ใต้')
      else null
    end as is_south14,
    count(distinct posting_key)::int as n_scope_postings,
    sum(sample_weight) as scope_total_weight,
    coalesce(sum(sample_weight) filter (where is_new), 0) as scope_new_weight
  from active_postings
  group by grouping sets (
    (week_start),
    (week_start, region),
    (week_start, region, province_th, is_south14)
  )
),
skill_agg as (
  select
    ap.week_start,
    case
      when grouping(ap.region) = 1 then 'national'
      when grouping(ap.province_th) = 1 then 'region'
      else 'province'
    end as scope_level,
    case when grouping(ap.region) = 1 then 'ทั้งประเทศ' else ap.region end as region,
    case
      when grouping(ap.region) = 1 then 'ทั้งประเทศ'
      when grouping(ap.province_th) = 1 then 'ทั้งหมดในภาค'
      else ap.province_th
    end as province_th,
    s.skill_key,
    s.skill_canonical,
    coalesce(s.skill_slug, trim(both '-' from lower(regexp_replace(s.skill_canonical, '[^a-zA-Z0-9]+', '-', 'g')))) as skill_slug,
    s.skill_name_th,
    s.skill_type,
    s.skill_group,
    count(distinct ap.posting_key)::int as n_postings,
    count(distinct ap.posting_key) filter (where ap.is_new)::int as n_new_postings,
    sum(ap.sample_weight) as raw_w_active,
    coalesce(sum(ap.sample_weight) filter (where ap.is_new), 0) as raw_w_new
  from active_postings ap
  join dw.fact_posting_skill fps on fps.posting_key = ap.posting_key
  join dw.dim_skill s on s.skill_key = fps.skill_key
  group by grouping sets (
    (ap.week_start, s.skill_key, s.skill_canonical, s.skill_slug, s.skill_name_th, s.skill_type, s.skill_group),
    (ap.week_start, ap.region, s.skill_key, s.skill_canonical, s.skill_slug, s.skill_name_th, s.skill_type, s.skill_group),
    (ap.week_start, ap.region, ap.province_th, s.skill_key, s.skill_canonical, s.skill_slug, s.skill_name_th, s.skill_type, s.skill_group)
  )
)
select
  sa.week_start,
  sa.scope_level,
  sa.region,
  sa.province_th,
  st.is_south14,
  sa.skill_key,
  sa.skill_canonical,
  sa.skill_slug,
  sa.skill_name_th,
  sa.skill_type,
  sa.skill_group,
  sa.n_postings,
  sa.n_new_postings,
  st.n_scope_postings,
  case when sa.n_postings >= 5 and st.n_scope_postings >= 5 then round(sa.raw_w_active::numeric, 2) else null end as weighted_active_sum,
  case when sa.n_new_postings >= 5 and st.n_scope_postings >= 5 then round(sa.raw_w_new::numeric, 2) else null end as weighted_new_sum,
  case
    when sa.n_postings >= 5 and st.n_scope_postings >= 5 and st.scope_total_weight > 0
      then round((sa.raw_w_active / st.scope_total_weight)::numeric, 4)
    else null
  end as weighted_share,
  case
    when sa.n_new_postings >= 5 and st.scope_new_weight > 0
      then round((sa.raw_w_new / st.scope_new_weight)::numeric, 4)
    else null
  end as weighted_new_share,
  (sa.n_postings < 5 or st.n_scope_postings < 5) as is_suppressed
from skill_agg sa
join scope_totals st
  on st.week_start = sa.week_start
 and st.scope_level = sa.scope_level
 and st.region = sa.region
 and st.province_th = sa.province_th;

-- 2.2 mart.skill_cooccurrence (Top 15 co-occurring skills per skill, strictly n_postings >= 5)
create or replace view mart.skill_cooccurrence as
with skill_totals as (
  select skill_key, count(distinct posting_key)::int as n_skill_postings
  from dw.fact_posting_skill
  group by skill_key
),
pairs as (
  select
    a.skill_key,
    b.skill_key as co_skill_key,
    count(distinct a.posting_key)::int as n_postings,
    round(sum(f.sample_weight)::numeric, 2) as weighted_co_count
  from dw.fact_posting_skill a
  join dw.fact_posting_skill b
    on a.posting_key = b.posting_key
   and a.skill_key <> b.skill_key
  join dw.fact_job_posting f on f.posting_key = a.posting_key
  group by a.skill_key, b.skill_key
  having count(distinct a.posting_key) >= 5
),
ranked as (
  select
    p.skill_key,
    s1.skill_canonical,
    coalesce(s1.skill_slug, trim(both '-' from lower(regexp_replace(s1.skill_canonical, '[^a-zA-Z0-9]+', '-', 'g')))) as skill_slug,
    s1.skill_name_th,
    s1.skill_group,
    p.co_skill_key,
    s2.skill_canonical as co_skill_canonical,
    coalesce(s2.skill_slug, trim(both '-' from lower(regexp_replace(s2.skill_canonical, '[^a-zA-Z0-9]+', '-', 'g')))) as co_skill_slug,
    s2.skill_name_th as co_skill_name_th,
    s2.skill_group as co_skill_group,
    p.n_postings,
    p.weighted_co_count,
    round((p.n_postings::numeric / nullif(t1.n_skill_postings, 0)), 4) as co_share,
    round((p.n_postings::numeric / nullif(t1.n_skill_postings + t2.n_skill_postings - p.n_postings, 0)), 4) as jaccard_similarity,
    row_number() over (partition by p.skill_key order by p.n_postings desc, p.weighted_co_count desc, p.co_skill_key asc) as rank_order
  from pairs p
  join dw.dim_skill s1 on s1.skill_key = p.skill_key
  join dw.dim_skill s2 on s2.skill_key = p.co_skill_key
  join skill_totals t1 on t1.skill_key = p.skill_key
  join skill_totals t2 on t2.skill_key = p.co_skill_key
)
select
  skill_key,
  skill_canonical,
  skill_slug,
  skill_name_th,
  skill_group,
  co_skill_key,
  co_skill_canonical,
  co_skill_slug,
  co_skill_name_th,
  co_skill_group,
  n_postings,
  weighted_co_count,
  co_share,
  jaccard_similarity,
  rank_order::int
from ranked
where rank_order <= 15;

-- 2.3 mart.occupation_skill_profile (occupation_cluster x skill, weighted + raw share, n >= 5 suppression)
create or replace view mart.occupation_skill_profile as
with occ_meta as (
  select
    occupation_cluster,
    coalesce(min(occupation_slug), trim(both '-' from lower(regexp_replace(occupation_cluster, '[^a-zA-Z0-9]+', '-', 'g')))) as occupation_slug,
    coalesce(max(occupation_name_th), occupation_cluster) as occupation_name_th
  from dw.dim_occupation
  group by occupation_cluster
),
occ_totals as (
  select
    o.occupation_cluster,
    count(distinct f.posting_key)::int as n_occ_postings,
    sum(f.sample_weight) as occ_total_weight
  from dw.fact_job_posting f
  join dw.dim_occupation o on o.occupation_key = f.occupation_key
  group by o.occupation_cluster
),
occ_skills as (
  select
    o.occupation_cluster,
    s.skill_key,
    s.skill_canonical,
    coalesce(s.skill_slug, trim(both '-' from lower(regexp_replace(s.skill_canonical, '[^a-zA-Z0-9]+', '-', 'g')))) as skill_slug,
    s.skill_name_th,
    s.skill_type,
    s.skill_group,
    count(distinct f.posting_key)::int as n_postings,
    sum(f.sample_weight) as skill_weight
  from dw.fact_job_posting f
  join dw.dim_occupation o on o.occupation_key = f.occupation_key
  join dw.fact_posting_skill fps on fps.posting_key = f.posting_key
  join dw.dim_skill s on s.skill_key = fps.skill_key
  group by o.occupation_cluster, s.skill_key, s.skill_canonical, s.skill_slug, s.skill_name_th, s.skill_type, s.skill_group
)
select
  os.occupation_cluster,
  om.occupation_slug,
  om.occupation_name_th,
  os.skill_key,
  os.skill_canonical,
  os.skill_slug,
  os.skill_name_th,
  os.skill_type,
  os.skill_group,
  ot.n_occ_postings,
  os.n_postings,
  case
    when os.n_postings >= 5 and ot.n_occ_postings >= 5 and ot.occ_total_weight > 0
      then round((os.skill_weight / ot.occ_total_weight)::numeric, 4)
    else null
  end as weighted_share,
  case
    when os.n_postings >= 5 and ot.n_occ_postings >= 5
      then round((os.n_postings::numeric / ot.n_occ_postings), 4)
    else null
  end as raw_share,
  row_number() over (
    partition by os.occupation_cluster
    order by os.n_postings desc, os.skill_weight desc, os.skill_key asc
  )::int as rank_in_occupation,
  (os.n_postings < 5 or ot.n_occ_postings < 5) as is_suppressed
from occ_skills os
join occ_totals ot on ot.occupation_cluster = os.occupation_cluster
join occ_meta om on om.occupation_cluster = os.occupation_cluster;

-- 2.4 mart.salary_stats (occupation x province/region x experience band, p25/p50/p75, n >= 5 suppression)
create or replace view mart.salary_stats as
with salaried as (
  select
    f.posting_key,
    f.salary_mid,
    coalesce(o.occupation_cluster, 'ไม่ระบุ') as occupation_cluster,
    coalesce(o.occupation_slug, trim(both '-' from lower(regexp_replace(coalesce(o.occupation_cluster, 'other'), '[^a-zA-Z0-9]+', '-', 'g')))) as occupation_slug,
    coalesce(l.region, 'ไม่ระบุ') as region,
    coalesce(l.province_th, 'ไม่ระบุ') as province_th,
    coalesce(ex.band_th, 'ไม่ระบุ/ไม่จำเป็น') as experience_band
  from dw.fact_job_posting f
  left join dw.dim_occupation o on o.occupation_key = f.occupation_key
  left join dw.dim_location l on l.location_key = f.location_key
  left join dw.dim_experience ex on ex.experience_key = f.experience_key
  where f.has_salary = true
    and f.salary_mid is not null
),
occ_slugs as (
  select occupation_cluster, min(occupation_slug) as occupation_slug
  from salaried
  group by occupation_cluster
),
agg as (
  select
    case
      when grouping(s.occupation_cluster) = 0 and grouping(s.province_th) = 0 and grouping(s.experience_band) = 0 then 'occ_prov_exp'
      when grouping(s.occupation_cluster) = 0 and grouping(s.region) = 0 and grouping(s.experience_band) = 0 then 'occ_reg_exp'
      when grouping(s.occupation_cluster) = 0 and grouping(s.experience_band) = 0 then 'occ_exp'
      when grouping(s.occupation_cluster) = 0 and grouping(s.region) = 0 then 'occ_reg'
      when grouping(s.occupation_cluster) = 0 then 'occ'
      when grouping(s.province_th) = 0 then 'prov'
      when grouping(s.region) = 0 then 'reg'
      else 'national'
    end as scope_type,
    case when grouping(s.occupation_cluster) = 1 then 'ทั้งหมด' else s.occupation_cluster end as occupation_cluster,
    case when grouping(s.region) = 1 then 'ทั้งประเทศ' else s.region end as region,
    case
      when grouping(s.province_th) = 0 then s.province_th
      when grouping(s.region) = 0 then 'ทั้งหมดในภาค'
      else 'ทั้งประเทศ'
    end as province_th,
    case when grouping(s.experience_band) = 1 then 'ทั้งหมด' else s.experience_band end as experience_band,
    count(*)::int as n_postings,
    case when count(*) >= 5 then round(percentile_cont(0.25) within group (order by s.salary_mid)::numeric, 0) else null end as salary_p25,
    case when count(*) >= 5 then round(percentile_cont(0.50) within group (order by s.salary_mid)::numeric, 0) else null end as salary_p50,
    case when count(*) >= 5 then round(percentile_cont(0.75) within group (order by s.salary_mid)::numeric, 0) else null end as salary_p75,
    case when count(*) >= 5 then round(avg(s.salary_mid)::numeric, 0) else null end as salary_mean,
    case when count(*) >= 5 then round(min(s.salary_mid)::numeric, 0) else null end as salary_min_obs,
    case when count(*) >= 5 then round(max(s.salary_mid)::numeric, 0) else null end as salary_max_obs,
    (count(*) < 5) as is_suppressed
  from salaried s
  group by grouping sets (
    (s.occupation_cluster, s.region, s.province_th, s.experience_band),
    (s.occupation_cluster, s.region, s.experience_band),
    (s.occupation_cluster, s.experience_band),
    (s.occupation_cluster, s.region),
    (s.occupation_cluster),
    (s.region, s.province_th),
    (s.region),
    ()
  )
)
select
  a.scope_type,
  a.occupation_cluster,
  coalesce(os.occupation_slug, 'all') as occupation_slug,
  a.region,
  a.province_th,
  a.experience_band,
  a.n_postings,
  a.salary_p25,
  a.salary_p50,
  a.salary_p75,
  a.salary_mean,
  a.salary_min_obs,
  a.salary_max_obs,
  a.is_suppressed
from agg a
left join occ_slugs os on os.occupation_cluster = a.occupation_cluster;

-- 2.5 mart.posting_volume_daily (day x province/region/national for calendar heatmap & volume area)
create or replace view mart.posting_volume_daily as
with base as (
  select
    d.date_key,
    d.full_date,
    d.year,
    d.month,
    d.week,
    date_trunc('week', d.full_date)::date as week_start,
    coalesce(l.region, 'ไม่ระบุ') as region,
    coalesce(l.province_th, 'ไม่ระบุ') as province_th,
    coalesce(l.is_south14, false) as is_south14,
    f.sample_weight,
    f.has_salary
  from dw.fact_job_posting f
  join dw.dim_date d on d.date_key = coalesce(f.date_posted_key, f.first_seen_date_key)
  left join dw.dim_location l on l.location_key = f.location_key
)
select
  date_key,
  full_date,
  year,
  month,
  week,
  week_start,
  case
    when grouping(region) = 1 then 'national'
    when grouping(province_th) = 1 then 'region'
    else 'province'
  end as scope_level,
  case when grouping(region) = 1 then 'ทั้งประเทศ' else region end as region,
  case
    when grouping(region) = 1 then 'ทั้งประเทศ'
    when grouping(province_th) = 1 then 'ทั้งหมดในภาค'
    else province_th
  end as province_th,
  case
    when grouping(province_th) = 0 then is_south14
    when grouping(region) = 0 then (region = 'ใต้')
    else null
  end as is_south14,
  count(*)::int as n_postings,
  count(*) filter (where has_salary)::int as n_with_salary,
  case when count(*) >= 5 then round(sum(sample_weight)::numeric, 2) else null end as weighted_volume,
  case when count(*) >= 5 then round(avg(case when has_salary then 1.0 else 0.0 end)::numeric, 4) else null end as salary_share,
  (count(*) < 5) as is_suppressed
from base
group by grouping sets (
  (date_key, full_date, year, month, week, week_start),
  (date_key, full_date, year, month, week, week_start, region),
  (date_key, full_date, year, month, week, week_start, region, province_th, is_south14)
);

-- 2.6 mart.curriculum_coverage_ref (occupation_cluster x top 30 market skills for Institution alignment)
create or replace view mart.curriculum_coverage_ref as
with top_k as (
  select *
  from mart.occupation_skill_profile
  where rank_in_occupation <= 30
),
sums as (
  select
    occupation_cluster,
    sum(coalesce(weighted_share, 0)) as sum_top_share
  from top_k
  group by occupation_cluster
)
select
  t.occupation_cluster,
  t.occupation_slug,
  t.occupation_name_th,
  t.skill_key,
  t.skill_canonical,
  t.skill_slug,
  t.skill_name_th,
  t.skill_type,
  t.skill_group,
  t.n_occ_postings,
  t.n_postings,
  t.weighted_share,
  case
    when not t.is_suppressed and s.sum_top_share > 0
      then round((t.weighted_share / s.sum_top_share)::numeric, 4)
    else null
  end as importance_weight,
  t.rank_in_occupation as rank_order,
  (t.rank_in_occupation <= 15) as is_core_skill,
  t.is_suppressed
from top_k t
join sums s on s.occupation_cluster = t.occupation_cluster;

-- 2.7 mart.public_summary (1-row safe summary for Landing & Global Context Bar — NO pipeline errors exposed)
create or replace view mart.public_summary as
select
  count(*)::int as n_postings,
  count(*) filter (where f.has_salary)::int as n_with_salary,
  case when count(*) >= 5 then round((100.0 * count(*) filter (where f.has_salary) / nullif(count(*), 0))::numeric, 1) else null end as pct_with_salary,
  count(*) filter (where f.n_skills > 0)::int as n_with_skills,
  case when count(*) >= 5 then round((100.0 * count(*) filter (where f.n_skills > 0) / nullif(count(*), 0))::numeric, 1) else null end as pct_with_skills,
  case when count(*) >= 5 then round(avg(f.n_skills)::numeric, 1) else null end as avg_skills_per_posting,
  count(distinct l.province_th) filter (where l.province_th not in ('หลายจังหวัด', 'ต่างประเทศ'))::int as n_provinces,
  count(distinct o.occupation_cluster)::int as n_occupations,
  (select count(*)::int from dw.dim_skill) as n_skills_catalog,
  min(d_post.full_date) as min_date_posted,
  max(d_post.full_date) as max_date_posted,
  coalesce(
    (select max(finished_at) from staging.scrape_run where status = 'done'),
    (select max(scraped_at) from staging.job_posting_raw),
    max(coalesce(d_last.full_date, d_post.full_date))::timestamptz
  ) as last_updated_at
from dw.fact_job_posting f
left join dw.dim_location l on l.location_key = f.location_key
left join dw.dim_occupation o on o.occupation_key = f.occupation_key
left join dw.dim_date d_post on d_post.date_key = f.date_posted_key
left join dw.dim_date d_last on d_last.date_key = f.last_seen_date_key;

-- 2.8 mart.ml_leaderboard (summary + per-fold rows from ml.*)
create or replace view mart.ml_leaderboard as
select
  e.experiment_id,
  e.task,
  e.dataset_version,
  e.n_rows,
  e.created_at,
  r.result_id,
  r.model_name,
  r.fold,
  (r.fold = -1) as is_summary,
  r.r2,
  r.rmse,
  r.mae,
  r.mape,
  r.fit_seconds,
  r.params,
  r.is_champion
from ml.model_result r
join ml.experiment e on e.experiment_id = r.experiment_id;

-- 2.9 mart.ml_feature_importance (safe view of ml.feature_importance for /ml-lab)
create or replace view mart.ml_feature_importance as
select
  e.experiment_id,
  e.task,
  e.dataset_version,
  fi.model_name,
  fi.feature,
  fi.importance
from ml.feature_importance fi
join ml.experiment e on e.experiment_id = fi.experiment_id;

-- 2.10 mart.salary_prediction (precomputed Champion predictions for /salary fallback)
create table if not exists mart.salary_prediction (
  prediction_id      bigserial primary key,
  experiment_id      bigint references ml.experiment (experiment_id) on delete set null,
  model_name         text not null,
  occupation_cluster text not null,
  province_th        text not null default 'ทั้งประเทศ',
  region             text not null default 'ทั้งประเทศ',
  experience_band    text not null default 'ไม่ระบุ/ไม่จำเป็น',
  education_level    text not null default 'ไม่ระบุ',
  employment_type    text not null default 'FULL_TIME',
  skill_bundle       text not null default 'baseline',
  pred_p25           numeric not null,
  pred_p50           numeric not null,
  pred_p75           numeric not null,
  mae_cv             numeric,
  mape_cv            numeric,
  n_train_support    int not null default 0,
  created_at         timestamptz default now(),
  unique (occupation_cluster, province_th, experience_band, education_level, employment_type, skill_bundle)
);

-- 2.11 mart.top_links (max 5 links per occupation x province AND per occupation national, strictly n >= 5, NO description/qualifications)
create or replace view mart.top_links as
with base as (
  select
    o.occupation_cluster,
    coalesce(o.occupation_slug, trim(both '-' from lower(regexp_replace(o.occupation_cluster, '[^a-zA-Z0-9]+', '-', 'g')))) as occupation_slug,
    coalesce(l.province_th, 'ไม่ระบุ') as province_th,
    coalesce(l.region, 'ไม่ระบุ') as region,
    src.source_name,
    f.source_url,
    left(coalesce(nullif(trim(f.title_short), ''), o.job_title_norm), 120) as title_short,
    d_post.full_date as date_posted,
    f.posting_key
  from dw.fact_job_posting f
  join dw.dim_occupation o on o.occupation_key = f.occupation_key
  join dw.dim_source src on src.source_key = f.source_key
  left join dw.dim_location l on l.location_key = f.location_key
  left join dw.dim_date d_post on d_post.date_key = f.date_posted_key
),
prov_ranked as (
  select
    occupation_cluster,
    occupation_slug,
    province_th,
    region,
    source_name,
    source_url,
    title_short,
    date_posted,
    count(*) over (partition by occupation_cluster, province_th)::int as n_postings,
    row_number() over (partition by occupation_cluster, province_th order by date_posted desc nulls last, posting_key desc)::int as rank_order
  from base
),
nat_ranked as (
  select
    occupation_cluster,
    occupation_slug,
    'ทั้งประเทศ'::text as province_th,
    'ทั้งประเทศ'::text as region,
    source_name,
    source_url,
    title_short,
    date_posted,
    count(*) over (partition by occupation_cluster)::int as n_postings,
    row_number() over (partition by occupation_cluster order by date_posted desc nulls last, posting_key desc)::int as rank_order
  from base
)
select
  occupation_cluster,
  occupation_slug,
  province_th,
  region,
  source_name,
  source_url,
  title_short,
  date_posted,
  n_postings,
  rank_order
from prov_ranked
where n_postings >= 5 and rank_order <= 5
union all
select
  occupation_cluster,
  occupation_slug,
  province_th,
  region,
  source_name,
  source_url,
  title_short,
  date_posted,
  n_postings,
  rank_order
from nat_ranked
where n_postings >= 5 and rank_order <= 5;

-- 3. Admin-only Mart Views (NEVER granted to anon or authenticated)

-- 3.1 mart.pipeline_status
create or replace view mart.pipeline_status as
select
  sr.scrape_run_id,
  sr.source,
  sr.scope,
  sr.started_at,
  sr.finished_at,
  sr.status,
  coalesce(sr.n_discovered, 0) as n_discovered,
  coalesce(sr.n_fetched, 0) as n_fetched,
  coalesce(sr.n_failed, 0) as n_failed,
  (sr.status in ('stopped_403', 'stopped_429', 'stopped_captcha')) as is_blocked_flag,
  case
    when sr.finished_at is not null and sr.started_at is not null
      then round(extract(epoch from (sr.finished_at - sr.started_at))::numeric, 1)
    else null
  end as duration_seconds,
  (select count(*)::int from staging.listing_seen ls where ls.scrape_run_id = sr.scrape_run_id) as n_listings_seen
from staging.scrape_run sr
order by sr.started_at desc, sr.scrape_run_id desc;

-- 3.2 mart.dq_summary
create or replace view mart.dq_summary as
select
  dq.dq_id,
  dq.scrape_run_id,
  sr.source,
  coalesce(nullif(trim(dq.dimension), ''), split_part(dq.check_name, ':', 1)) as dimension,
  dq.check_name,
  dq.table_name,
  dq.n_total,
  dq.n_fail,
  case
    when dq.n_total > 0 then round((100.0 * dq.n_fail / dq.n_total)::numeric, 2)
    else 0::numeric
  end as fail_rate,
  dq.pass,
  dq.details,
  dq.checked_at
from staging.dq_result dq
left join staging.scrape_run sr on sr.scrape_run_id = dq.scrape_run_id
order by dq.checked_at desc, dq.dq_id desc;

-- 4. Security Grants (T3.8, D18)
--    Explicitly revoke everything first, then grant SELECT ONLY on the 11 public mart objects.

revoke all on all tables in schema mart from public, anon, authenticated;

grant select on
  mart.skill_demand_weekly,
  mart.skill_cooccurrence,
  mart.occupation_skill_profile,
  mart.salary_stats,
  mart.posting_volume_daily,
  mart.curriculum_coverage_ref,
  mart.public_summary,
  mart.ml_leaderboard,
  mart.ml_feature_importance,
  mart.salary_prediction,
  mart.top_links
to anon, authenticated;

-- Admin-only marts must NEVER be readable directly by anon or authenticated
revoke all on mart.pipeline_status, mart.dq_summary from public, anon, authenticated;

-- Ensure service_role has access to all mart & ml objects
do $$
begin
  if exists (select 1 from pg_roles where rolname = 'service_role') then
    grant select, insert, update, delete on all tables in schema mart to service_role;
    grant select, insert, update, delete on all tables in schema ml to service_role;
    grant usage, select on all sequences in schema mart to service_role;
    grant usage, select on all sequences in schema ml to service_role;
  end if;
end
$$;
