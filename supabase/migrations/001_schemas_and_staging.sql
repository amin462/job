-- =============================================================================
-- Migration 001: Schemas, Extensions, Privileges, and Staging Tables (T1.1)
-- Project: Skill Demand Intelligence (E')
-- References: ARCHITECTURE.md §3.1, §3.2, §9 | AGENTS.md §1
-- =============================================================================

-- 1. Create isolated schemas
create schema if not exists staging;
create schema if not exists dw;
create schema if not exists mart;
create schema if not exists ml;

-- 2. Enable pg_trgm for rule-based alias similarity matching (no LLM/AI)
create extension if not exists pg_trgm;

-- 3. Schema-level access control (Defense-in-Depth)
--    anon and authenticated NEVER touch staging, dw, or ml directly.
revoke all on schema staging, dw, ml from public, anon, authenticated;
grant usage on schema mart to anon, authenticated;
alter default privileges in schema mart revoke all on tables from public, anon, authenticated;

--    Allow backend service_role to operate across schemas when using Supabase keys
do $$
begin
  if exists (select 1 from pg_roles where rolname = 'service_role') then
    grant all on schema staging, dw, mart, ml to service_role;
    alter default privileges in schema staging grant all on tables to service_role;
    alter default privileges in schema staging grant all on sequences to service_role;
    alter default privileges in schema dw grant all on tables to service_role;
    alter default privileges in schema dw grant all on sequences to service_role;
    alter default privileges in schema mart grant all on tables to service_role;
    alter default privileges in schema mart grant all on sequences to service_role;
    alter default privileges in schema ml grant all on tables to service_role;
    alter default privileges in schema ml grant all on sequences to service_role;
  end if;
end
$$;

-- 4. Staging Tables (ARCHITECTURE.md §3.2)
--    PDPA rule: NO HR contact columns (telephone, email, contactPoint, LINE) anywhere.
--    ToS rule: Allowed sources are strictly 'jobthai' and 'jobbkk'.

create table if not exists staging.scrape_run (
  scrape_run_id bigserial primary key,
  source        text not null check (source in ('jobthai', 'jobbkk')),
  scope         text,
  started_at    timestamptz default now(),
  finished_at   timestamptz,
  status        text check (status in ('running', 'done', 'stopped_403', 'stopped_429', 'stopped_captcha', 'error')),
  n_discovered  int default 0,
  n_fetched     int default 0,
  n_failed      int default 0
);

-- Every job ID observed in listing discovery pages: used for N_h stratum totals and first_seen/last_seen tracking
create table if not exists staging.listing_seen (
  scrape_run_id bigint not null references staging.scrape_run (scrape_run_id) on delete cascade,
  source        text not null check (source in ('jobthai', 'jobbkk')),
  source_job_id text not null,
  stratum       text not null,
  seen_date     date not null default current_date,
  primary key (scrape_run_id, source, source_job_id)
);

create index if not exists idx_listing_seen_job on staging.listing_seen (source, source_job_id, seen_date);
create index if not exists idx_listing_seen_stratum on staging.listing_seen (stratum, seen_date);

-- Parsed postings without HR contact PII
create table if not exists staging.job_posting_raw (
  raw_id          bigserial primary key,
  scrape_run_id   bigint references staging.scrape_run (scrape_run_id) on delete set null,
  source          text not null check (source in ('jobthai', 'jobbkk')),
  source_job_id   text not null,
  source_url      text not null,
  title           text,
  description     text,          -- Used only by ETL skill extraction; never exposed publicly
  qualifications  text,          -- Used only by ETL; never exposed publicly
  salary_text     text,
  salary_min      numeric,
  salary_max      numeric,
  province        text,
  district        text,
  job_category    text,
  industry        text,
  employment_type text,
  date_posted     date,
  valid_through   date,
  company_name    text,
  payload         jsonb,         -- JSON-LD stripped of all HR contact fields
  content_hash    text not null,
  scraped_at      timestamptz default now(),
  unique (source, source_job_id, content_hash)
);

create index if not exists idx_job_posting_raw_run on staging.job_posting_raw (scrape_run_id);
create index if not exists idx_job_posting_raw_source_id on staging.job_posting_raw (source, source_job_id);

-- Data Quality check log per pipeline/scrape run
create table if not exists staging.dq_result (
  dq_id         bigserial primary key,
  scrape_run_id bigint references staging.scrape_run (scrape_run_id) on delete set null,
  dimension     text,
  check_name    text not null,
  table_name    text not null,
  n_total       int not null default 0,
  n_fail        int not null default 0,
  pass          boolean not null,
  details       text,
  checked_at    timestamptz default now()
);

create index if not exists idx_dq_result_run on staging.dq_result (scrape_run_id, checked_at desc);
