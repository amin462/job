# ARCHITECTURE.md — สถาปัตยกรรมระบบ Skill Demand Intelligence (v4)

> ใช้คู่กับ [PLAN.md](PLAN.md) (ขอบเขต/roadmap), [CONTEXT.md](CONTEXT.md) (โดเมน/กติกา), [FRONTEND_SPEC.md](FRONTEND_SPEC.md) และ [TASKS.md](TASKS.md) · ฉบับเก่า (SouthBiz) อยู่ใน `docs/archive/`

---

## 1. Stack

| ชั้น | เลือก | หมายเหตุ |
|---|---|---|
| เว็บ + API | Next.js (App Router, TypeScript) บน **Vercel Hobby** | Server Components อ่านจาก schema `mart` ผ่าน Supabase client |
| UI | Tailwind v4 + shadcn/ui + Apache ECharts + TanStack Table | ดู DESIGN_SYSTEM.md |
| ฐานข้อมูล + Auth | **Supabase Postgres** (free 500 MB) + Supabase Auth + RLS | แยก schema: `staging`, `dw`, `mart`, `public` (app tables) |
| Scraper / ETL / ML | **Python 3.11–3.13** ใน venv (Playwright, httpx, pandas, scikit-learn, XGBoost, LightGBM, CatBoost, PyThaiNLP) | รันบน **เครื่องตัวเองหรือเครื่องของมหาวิทยาลัย** (Task Scheduler/cron) — ไม่รันบน Vercel/Render (Render free ไม่มี cron, RAM 512 MB ไม่พอ Playwright, ไม่มีดิสก์ถาวร) |
| ML serving | โมเดล champion เพียงตัวเดียว รันเป็น **FastAPI `services/ml-api`** (โหลดโมเดล joblib/native ตรงๆ ไม่ต้อง export ONNX) บน **Render free** หรือ **เซิร์ฟเวอร์มหาวิทยาลัย** (ถ้า IT ให้ HTTPS สาธารณะ + เปิดตลอด) · Vercel route `/api/salary/estimate` เป็น proxy (ส่ง header secret, browser ไม่เรียก ml-api ตรง) · **fallback:** `mart.salary_prediction` ที่คำนวณล่วงหน้า เมื่อ API หลับ/ช้ากว่า 8 วินาที | D19 · Render free หลับหลัง 15 นาที (cold start ~1 นาที) → หน้า Salary ส่ง `GET /health` ปลุกตอนเปิดหน้า + ping จาก cron-job.org ทุก 14 นาทีช่วงเดโม/วันสอบ (1 service เปิดตลอดใช้ ~744 จาก 750 ชม./เดือน) |
| AI แชท | Gemini API ผ่าน route `/api/chat` | รับ `pageContext` เท่านั้น ไม่มี Text-to-SQL |
| ตั้งเวลา | Task Scheduler/cron บนเครื่องที่รัน pipeline (re-discovery รายสัปดาห์) + cron-job.org (ping Supabase/ml-api) | **ไม่ใช้ Railway** (หลัง trial 30 วันเหลือ \$1/เดือน, RAM 0.5 GB, ไม่มี cron — ไม่พอ 16 สัปดาห์) |

ข้อจำกัดโควตา: Supabase 500 MB → **ไม่เก็บ HTML ดิบใน DB** (เก็บไฟล์ดิบบนดิสก์/Storage ภายนอก, `spike/raw/` และ `data/raw/` อยู่ใน `.gitignore`), เก็บเฉพาะฟิลด์ที่ parse แล้วและข้อความที่ใช้ดึงทักษะ (ตัดทิ้งหลังดึงทักษะเสร็จได้ ถ้าพื้นที่ไม่พอ)

---

## 2. Data flow

```text
[JobThai]  (JobBKK ภายหลัง)
   │ 1 discovery: หน้ารายการรายจังหวัด/หมวด (Playwright เลื่อนหน้า) → job id
   │ 2 detail: หน้าประกาศ → JSON-LD JobPosting (ตัดข้อมูลผู้ติดต่อ HR ทิ้งตอน parse)
   ▼
[data/raw/*.html]  (ดิสก์ ไม่ commit)            ← เก็บไว้ re-parse ได้
   ▼
[staging.job_posting_raw]  ฟิลด์ที่ parse แล้ว + payload JSON (ไม่มี HR contact) + scrape_run_id
   ▼  clean / normalize (pandas)
      เงินเดือน → min/max/ประเภท, จังหวัด/อำเภอ → รหัสมาตรฐาน, ชื่อตำแหน่ง → normalize,
      วุฒิ/ประสบการณ์ → regex, dedupe (source_job_id + content_hash)
   ▼  skill extraction (dictionary + alias, PyThaiNLP tokenizer)
   ▼  taxonomy mapping (alias → canonical skill, อาชีพ → occupation cluster)
   ▼  validate (data quality checks → staging.dq_result; ผ่านเกณฑ์จึงโหลด)
[dw.*]  star/galaxy: dim_* + fact_job_posting + fact_posting_skill
   ▼  SQL views/materialized views
[mart.*]  ตารางสรุปให้หน้าเว็บอ่าน (aggregate เท่านั้น มี n ขั้นต่ำ)
   ▲                                  │
[ML pipeline] อ่าน dw → benchmark ≥5 โมเดล → บันทึก ml.* → champion → ค่าคาดล่วงหน้า + ml-api (FastAPI)
                                      ▼
                         [Next.js บน Vercel] ◄── Gemini (แชทลอย, pageContext)
```

---

## 3. Schema (Supabase / PostgreSQL)

หลักการจากบทเรียนโครงการเดิม: **แยก schema ตั้งแต่ migration แรก** และ **เปิด RLS ทุกตารางใน `public`** ส่วน `staging`/`dw`/`mart`/`ml` ไม่เปิดผ่าน PostgREST (ไม่ใส่ใน "Exposed schemas") แล้วให้เว็บอ่านผ่าน view/RPC ใน `public` หรือ `mart` ที่เลือกเปิดเฉพาะที่จำเป็น

### 3.1 Schemas และ role

```sql
create schema if not exists staging;
create schema if not exists dw;
create schema if not exists mart;
create schema if not exists ml;
create extension if not exists pg_trgm;

-- ผู้ใช้เว็บ (anon/authenticated) อ่านได้เฉพาะ mart ที่ grant ให้เท่านั้น
revoke all on schema staging, dw, ml from anon, authenticated;
grant usage on schema mart to anon, authenticated;
alter default privileges in schema mart revoke all on tables from anon, authenticated;
```

### 3.2 staging

```sql
create table staging.scrape_run (
  scrape_run_id bigserial primary key,
  source        text not null,                 -- 'jobthai' | 'jobbkk'
  scope         text,                          -- เช่น 'province=90'
  started_at    timestamptz default now(),
  finished_at   timestamptz,
  status        text,                          -- running | done | stopped_403 | stopped_429 | stopped_captcha | error
  n_discovered  int, n_fetched int, n_failed int
);

-- ทุก job id ที่เห็นในหน้ารายการแต่ละรอบ: ใช้คำนวณ first_seen/last_seen และน้ำหนักการสุ่ม (N ของชั้น)
create table staging.listing_seen (
  scrape_run_id bigint references staging.scrape_run,
  source        text not null,
  source_job_id text not null,
  stratum       text not null,                 -- ชั้นการสุ่ม เช่น 'p=10|c=บัญชี'
  seen_date     date not null default current_date,
  primary key (scrape_run_id, source, source_job_id)
);

create table staging.job_posting_raw (
  raw_id          bigserial primary key,
  scrape_run_id   bigint references staging.scrape_run,
  source          text not null,
  source_job_id   text not null,
  source_url      text not null,               -- ใช้เป็นลิงก์ไปต้นฉบับ
  title           text,
  description     text,                        -- ใช้ดึงทักษะ ไม่แสดงบนเว็บ
  qualifications  text,
  salary_text     text,
  salary_min      numeric, salary_max numeric,
  province        text, district text,
  job_category    text, industry text, employment_type text,
  date_posted     date, valid_through date,
  company_name    text,
  payload         jsonb,                       -- JSON-LD ที่ตัดข้อมูลผู้ติดต่อแล้ว
  content_hash    text not null,
  scraped_at      timestamptz default now(),
  unique (source, source_job_id, content_hash)
);

create table staging.dq_result (
  dq_id bigserial primary key,
  scrape_run_id bigint references staging.scrape_run,
  check_name text, table_name text,
  n_total int, n_fail int, pass boolean,
  checked_at timestamptz default now()
);
```

### 3.3 dw (star/galaxy)

Dimensions ใช้ร่วม 2 fact (galaxy) · surrogate key เป็น `bigint identity` ยกเว้น `dim_date` (`yyyymmdd`)

```sql
create table dw.dim_date (
  date_key int primary key, full_date date not null,
  year int, quarter int, month int, week int, day_of_week int, is_weekend boolean
);

create table dw.dim_source (
  source_key smallint primary key generated always as identity,
  source_name text unique not null, base_url text, tos_note text
);

create table dw.dim_location (
  location_key int primary key generated always as identity,
  province_code text, province_th text, province_en text,
  district_th text, region text,               -- ภาค (เหนือ/อีสาน/กลาง/ตะวันออก/ตะวันตก/ใต้)
  is_south14 boolean,                          -- 14 จังหวัดภาคใต้
  unique (province_th, district_th)
);

create table dw.dim_company (
  company_key bigint primary key generated always as identity,
  company_name_norm text unique not null,      -- ใช้เป็น group ใน GroupKFold
  industry text, size_band text
);

create table dw.dim_occupation (               -- dim_job_title / occupation cluster
  occupation_key int primary key generated always as identity,
  occupation_cluster text not null,            -- เช่น 'Data & Analytics' 'Accounting & Finance'
  job_title_norm text not null,
  onet_ref text,                               -- อ้างอิง O*NET (ถ้ามี)
  unique (occupation_cluster, job_title_norm)
);

create table dw.dim_skill (
  skill_key int primary key generated always as identity,
  skill_canonical text unique not null,        -- 'Microsoft Excel'
  skill_name_th text, skill_type text,         -- tool | technical | soft | language | licence
  skill_group text,                            -- กลุ่มสำหรับ dashboard
  onet_ref text, esco_ref text
);

create table dw.skill_alias (                  -- ตารางหลักของ taxonomy
  alias_id bigint primary key generated always as identity,
  skill_key int references dw.dim_skill,
  alias text not null,                         -- 'excel' 'เอ็กเซล' 'โปรแกรม excel'
  lang text, match_type text default 'exact',  -- exact | regex | token
  status text default 'approved',              -- approved | pending | rejected
  unique (alias)
);

create table dw.dim_education   (education_key smallint primary key generated always as identity, level_th text unique, level_rank smallint);
create table dw.dim_experience  (experience_key smallint primary key generated always as identity, band_th text unique, min_years numeric, max_years numeric);
create table dw.dim_employment_type (employment_type_key smallint primary key generated always as identity, type_th text unique);

-- Fact 1: grain = 1 ประกาศ (1 source_job_id ต่อ 1 snapshot ล่าสุด)
create table dw.fact_job_posting (
  posting_key     bigint primary key generated always as identity,
  source_key      smallint references dw.dim_source,
  source_job_id   text not null,
  source_url      text not null,
  date_posted_key int references dw.dim_date,
  valid_through_key int references dw.dim_date,
  location_key    int references dw.dim_location,
  company_key     bigint references dw.dim_company,
  occupation_key  int references dw.dim_occupation,
  education_key   smallint references dw.dim_education,
  experience_key  smallint references dw.dim_experience,
  employment_type_key smallint references dw.dim_employment_type,
  salary_min      numeric, salary_max numeric, salary_mid numeric,   -- NULL = ไม่ระบุ/ตามตกลง
  has_salary      boolean generated always as (salary_mid is not null) stored,
  n_skills        smallint,
  first_seen_date_key int references dw.dim_date, -- วันที่พบครั้งแรกในหน้ารายการ
  last_seen_date_key  int references dw.dim_date, -- วันที่ยังพบล่าสุด (อัปเดตทุกรอบ re-discovery รายสัปดาห์)
  sample_stratum  text,                         -- ชั้นการสุ่ม (จังหวัด × หมวด)
  sample_weight   numeric not null default 1,   -- N_ชั้น / n_ชั้นที่ดึงจริง ใช้ถ่วงสัดส่วนใน mart
  scrape_run_id   bigint,
  unique (source_key, source_job_id)
);

-- Fact 2: grain = 1 ประกาศ × 1 ทักษะ
create table dw.fact_posting_skill (
  posting_key bigint references dw.fact_job_posting on delete cascade,
  skill_key   int references dw.dim_skill,
  match_alias_id bigint references dw.skill_alias,
  primary key (posting_key, skill_key)
);

-- Fact 3 (optional): ตัวเลขรวมระดับประเทศรายเดือนจากภาครัฐ (บริบท)
create table dw.fact_labor_monthly (
  date_key int references dw.dim_date, metric text, value numeric, source text,
  primary key (date_key, metric)
);

create index on dw.fact_job_posting (location_key);
create index on dw.fact_job_posting (occupation_key);
create index on dw.fact_posting_skill (skill_key);
create index on dw.skill_alias using gin (alias gin_trgm_ops);
```

### 3.4 mart (ตารางสรุปที่เว็บอ่าน — aggregate เท่านั้น)

ทุกตารางมี `n_postings` (จำนวนจริงที่ดึงมา) และเว็บซ่อนค่าเมื่อ n < 5 (กัน re-identify และกันค่าเพี้ยน) · **สัดส่วน/ร้อยละระดับภาคหรือประเทศคำนวณแบบถ่วงน้ำหนักด้วย `sample_weight`** (เช่น `Σw·1[มีทักษะ] / Σw`) เพื่อแก้ความเอียงจากการสุ่มแบบแบ่งชั้น · แนวโน้มใช้ **รายสัปดาห์** เพราะช่วงเก็บข้อมูลมีแค่ราว 3–4 เดือน

| ตาราง | grain | ใช้ในหน้า |
|---|---|---|
| `mart.skill_demand_weekly` | ทักษะ × สัปดาห์ × ภาค/จังหวัด: ประกาศ active (first_seen ≤ สัปดาห์ ≤ last_seen), ประกาศใหม่ (first_seen), สัดส่วนถ่วงน้ำหนัก | Market Explorer, Skill detail |
| `mart.skill_cooccurrence` | คู่ทักษะ (top N) | Skill detail |
| `mart.occupation_skill_profile` | occupation × ทักษะ (สัดส่วนประกาศที่ขอ) | Skill-gap, Occupation detail |
| `mart.salary_stats` | occupation × จังหวัด/ภาค × experience band (p25/p50/p75, n) | Salary Explorer |
| `mart.posting_volume_daily` | วัน × จังหวัด | Calendar heatmap |
| `mart.curriculum_coverage_ref` | occupation cluster × ทักษะที่ตลาดต้องการ (top K) | Institution |
| `mart.public_summary` | 1 แถว: จำนวนประกาศที่วิเคราะห์, % ระบุเงินเดือน, % map ทักษะได้, อัปเดตล่าสุด | Landing, Context Bar (สาธารณะ) |
| `mart.pipeline_status` / `mart.dq_summary` | รอบ scrape / เช็กคุณภาพ | Admin เท่านั้น (ไม่ grant ให้ anon) |
| `mart.salary_prediction` | ค่าคาดจาก champion ต่อชุด feature มาตรฐาน | Salary Estimator (fallback) |
| `mart.top_links` | occupation × จังหวัด → `source_url` ไม่เกิน 5 ลิงก์ | ลิงก์ไปประกาศต้นฉบับ (เก็บเฉพาะ URL + ชื่อตำแหน่ง ไม่แสดงเนื้อหา) |

### 3.5 ml

```sql
create table ml.experiment (
  experiment_id bigserial primary key, task text,       -- 'salary_regression'
  dataset_version text, n_rows int, created_at timestamptz default now()
);
create table ml.model_result (
  result_id bigserial primary key, experiment_id bigint references ml.experiment,
  model_name text, fold int,                            -- fold = -1 หมายถึงค่าเฉลี่ย
  r2 numeric, rmse numeric, mae numeric, mape numeric,
  fit_seconds numeric, params jsonb, is_champion boolean default false
);
create table ml.feature_importance (experiment_id bigint, model_name text, feature text, importance numeric);
```
เว็บ (ML Lab) อ่านผ่าน view `mart.ml_leaderboard` ที่สรุปจาก `ml.*`

### 3.6 public (app tables — เปิด RLS ทั้งหมด)

```sql
create table public.app_profile (
  user_id uuid primary key references auth.users on delete cascade,
  role text not null check (role in ('student','institution','admin')),
  display_name text, province_th text, target_occupation_cluster text,
  created_at timestamptz default now()
);
create table public.app_user_skill (
  user_id uuid references auth.users on delete cascade,
  skill_key int not null,                     -- อ้าง dw.dim_skill (ไม่ใส่ FK ข้าม schema ที่ปิดไว้)
  level smallint check (level between 1 and 3),
  primary key (user_id, skill_key)
);
create table public.app_curriculum (
  curriculum_id bigint primary key generated always as identity,
  owner_id uuid references auth.users on delete cascade,
  name text not null, target_occupation_cluster text, created_at timestamptz default now()
);
create table public.app_curriculum_skill (
  curriculum_id bigint references public.app_curriculum on delete cascade,
  skill_key int not null, course_name text,
  primary key (curriculum_id, skill_key, course_name)
);
create table public.app_chat_log (
  chat_id bigserial primary key, user_id uuid references auth.users on delete set null,
  page text, question text, answered boolean, created_at timestamptz default now()
);
create table public.app_alias_suggestion (    -- คิวให้ admin ตรวจ alias ใหม่ (ถ้าให้ผู้ใช้เสนอ)
  id bigserial primary key, proposed_by uuid references auth.users, alias text, skill_key int,
  status text default 'pending'
);

alter table public.app_profile            enable row level security;
alter table public.app_user_skill         enable row level security;
alter table public.app_curriculum         enable row level security;
alter table public.app_curriculum_skill   enable row level security;
alter table public.app_chat_log           enable row level security;
alter table public.app_alias_suggestion   enable row level security;

create or replace function public.is_admin() returns boolean
language sql stable security definer set search_path = public as
$$ select exists (select 1 from public.app_profile where user_id = auth.uid() and role = 'admin') $$;

-- กันยกระดับสิทธิ์: ผู้ใช้สร้าง/แก้โปรไฟล์ตัวเองได้ แต่ตั้ง role = 'admin' เองไม่ได้
create policy profile_select on public.app_profile for select using (user_id = auth.uid() or public.is_admin());
create policy profile_insert on public.app_profile for insert with check (user_id = auth.uid() and role in ('student','institution'));
create policy profile_update on public.app_profile for update using (user_id = auth.uid())
  with check (user_id = auth.uid() and role in ('student','institution'));
create policy profile_admin  on public.app_profile for all using (public.is_admin()) with check (public.is_admin());
-- หมายเหตุ: ไม่ใช้ `revoke update (role)` เพราะ Supabase grant ระดับตารางให้ authenticated อยู่แล้ว (revoke รายคอลัมน์ไม่มีผล)
-- policy แบบ permissive ถูก OR กัน → ผู้ใช้ทั่วไปติด with check (role ∈ student/institution), admin ผ่าน profile_admin
-- บัญชี admin (รวม persona เดโม) สร้างด้วย service role ใน seed ไม่ผ่านหน้าเว็บ
create policy uskill_self    on public.app_user_skill for all using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy curric_owner   on public.app_curriculum for all using (owner_id = auth.uid()) with check (owner_id = auth.uid());
create policy cskill_owner   on public.app_curriculum_skill for all
  using (exists (select 1 from public.app_curriculum c where c.curriculum_id = app_curriculum_skill.curriculum_id and c.owner_id = auth.uid()))
  with check (exists (select 1 from public.app_curriculum c where c.curriculum_id = app_curriculum_skill.curriculum_id and c.owner_id = auth.uid()));
create policy chat_insert    on public.app_chat_log for insert with check (user_id = auth.uid() or user_id is null);
create policy chat_admin_read on public.app_chat_log for select using (public.is_admin());
create policy alias_sugg     on public.app_alias_suggestion for all using (public.is_admin() or proposed_by = auth.uid()) with check (proposed_by = auth.uid() or public.is_admin());
```

ข้อมูลตลาด (`mart.*`) เปิดอ่านแบบ read-only ให้ `anon, authenticated` เป็นรายตารางด้วย `grant select` + view ที่ `security_invoker`; ตาราง `app_*` ทั้งหมดอยู่หลัง RLS · Demo persona ใช้บัญชีจริงที่ seed ไว้ (ปุ่ม "เข้าใช้คลิกเดียว" เรียก server action ที่ sign-in ด้วย credential เก็บใน env ฝั่ง server)

---

## 4. Scraper

| เรื่อง | การออกแบบ |
|---|---|
| โครงสร้าง | `scraper/` แยก `discovery` (หา job id จากหน้ารายการ) / `fetch` (โหลดหน้าประกาศ) / `parse` (JSON-LD → dict) ต่อยอดจาก `spike/scripts/parse_jobposting.py` และ `fetch_sample.py` |
| Discovery | Playwright เปิด `?province=XX` (และต่อไปรายหมวด) แล้วเลื่อนหน้า เก็บ id ที่เห็น; จังหวัดเล็กจบในหน้าเดียว, กรุงเทพฯ แบ่งตามหมวด/อุตสาหกรรมเพื่อลดเพดานการเลื่อน |
| Fetch | httpx ทีละ 1 request, **เว้น ≥ 5 วินาที** (+ jitter), User-Agent ระบุตัวตนโครงงาน, timeout/retry จำกัด |
| หยุดทันที | ได้ 403 / 429 / พบ CAPTCHA → บันทึก `scrape_run.status` แล้วหยุดทั้งรอบ **ห้ามหลบเลี่ยง ห้ามเปลี่ยน IP** |
| Resume | บันทึกความคืบหน้าราย job id; ไม่ดึงซ้ำถ้ามีไฟล์ดิบแล้ว (incremental) |
| PDPA | ตัด phone/email/ชื่อผู้ติดต่อ HR ที่ขั้น parse ก่อนเขียนไฟล์ใดๆ ลง staging |
| อัตรา | 1 request / ~6 วินาที ≈ 600 ประกาศ/ชั่วโมง → ตัวอย่างวิเคราะห์ 5,000–10,000 ประกาศใช้ราว 8–17 ชั่วโมง กระจายหลายคืน (ไม่ใช่ทั้ง 48,438 ในครั้งเดียว) |
| ความเปราะบาง | selector/ path อยู่ไฟล์ `config.py` ไฟล์เดียว, parse จาก JSON-LD ไม่พึ่ง HTML |

เป้าหมายขนาดข้อมูล: **สุ่มแบบแบ่งชั้น (stratified) ตามจังหวัด × หมวดงาน** ให้ได้ตัวอย่างหลักพันถึงหลักหมื่นประกาศ เพียงพอต่อ ML เงินเดือน แล้วรายงานตรงๆ ว่าเป็นตัวอย่าง ไม่ใช่ census ของตลาด

**การสุ่มและน้ำหนัก:**
1. discovery เก็บ job id ทุกตัวที่เห็นลง `staging.listing_seen` (ได้ N ของแต่ละชั้น)
2. จัดสรรตามสัดส่วน (proportional allocation) `n_h ≈ n × N_h / N` และกำหนดขั้นต่ำชั้นละ 5 ประกาศ (ชั้นที่มีน้อยกว่าเก็บทั้งหมด) เพื่อให้จังหวัดเล็กยังมีข้อมูล
3. `sample_weight = N_h / n_h` (ชั้นใหญ่ ≈ เท่ากันทุกตัว; ชั้นเล็กที่ถูกเก็บเกินสัดส่วนจะได้น้ำหนัก < ค่าเฉลี่ย) → mart ใช้ค่าถ่วง, ML ใช้แถวจริงไม่ถ่วง (ระบุในเล่ม)
4. **re-discovery รายสัปดาห์** (เปิดเฉพาะหน้ารายการ ไม่โหลดหน้าประกาศซ้ำ) เพื่ออัปเดต `last_seen` และหาประกาศใหม่

---

## 5. ETL และ Taxonomy

### 5.1 ขั้นตอน (Python, idempotent, รันซ้ำได้)
1. `extract` → `staging.job_posting_raw`
2. `clean` — แปลงเงินเดือนตามกฎ: ช่วง "15,000-20,000" → min/max/mid = กลางช่วง · มีแค่ขั้นต่ำ "15,000 ขึ้นไป" → min = 15,000, max = NULL, mid = min (ติดธง `salary_open_max`) · รายวัน × 26 วัน, รายชั่วโมง × 8 × 26 (ติดธงหน่วยเดิม) · "ตามตกลง/ตามโครงสร้างบริษัท" → NULL · นอกช่วง 5,000–500,000 หลังแปลง → NULL + บันทึกเป็น DQ fail · จังหวัด/อำเภอ → `dim_location`, ชื่อบริษัท normalize (ตัดคำนำ "บริษัท ... จำกัด") → `dim_company`, วุฒิ/ประสบการณ์จาก regex → `dim_education`/`dim_experience`, dedupe
3. `extract_skills` — normalize ข้อความ (lowercase, ตัดสัญลักษณ์) → ตัดคำด้วย PyThaiNLP (`newmm`) → จับ alias จาก dictionary (ภาษาอังกฤษใช้ word boundary, ไทยใช้ token/ substring ที่ตรวจแล้ว)
4. `map_taxonomy` — alias → canonical skill, ชื่อตำแหน่ง → occupation cluster (กฎคีย์เวิร์ด + ตารางแมป; ผู้ตรวจคนเดียวทำ 100–200 ตำแหน่งยอดนิยมก่อน)
5. `validate` — รันชุด DQ checks (หัวข้อ 7) ลง `staging.dq_result`; ไม่ผ่านเกณฑ์ → ไม่โหลดเข้า `dw`
6. `load_dw` — upsert dims → fact
7. `build_marts` — refresh materialized views / ตาราง `mart.*`

### 5.2 Taxonomy ของโครงงาน
- ใช้ O*NET 31.0 (CC BY 4.0) และ ESCO เป็น **แหล่งอ้างอิงชื่อมาตรฐาน** (`onet_ref`, `esco_ref`) ไม่ใช่แหล่งจับคู่โดยตรง (ชื่อแบบเป๊ะตรงกับประกาศไทยเพียง 5/21 ประกาศ และ ESCO ไม่มีภาษาไทย)
- เริ่ม 100–200 ทักษะ (ฮาร์ดสกิล/เครื่องมือ/ภาษา/ใบอนุญาต/ซอฟต์สกิลที่จับได้ชัด) พร้อม alias ไทย/อังกฤษ/คำสะกดผิดที่พบจริง ขยายจาก **คิว alias pending** (คำที่ถี่แต่ยังไม่ map) ที่ admin อนุมัติ ไม่ให้ LLM label · ทักษะที่ "เสนอ" ในคิวมาจาก **กฎเท่านั้น** (ความคล้ายของสตริงด้วย `pg_trgm similarity` ≥ 0.4 กับ alias ที่มีอยู่)
- ทักษะกำกวม (เช่น "ขาย", "Word") ใช้ `match_type = regex/token` + บริบท และวัด precision แยกต่อทักษะ

---

## 6. ML pipeline และการนำ champion ไปใช้

```text
dw.fact_job_posting (has_salary = true) ─► feature build (ไม่มี gender/age)
   features: occupation cluster, จังหวัด/ภาค, experience band, education level,
             employment type, จำนวนทักษะ, multi-hot ทักษะ top-K, อุตสาหกรรม
   target: log(salary_mid)  (รายงานผลกลับเป็นบาท)
   ▼
 GroupKFold(5, group = company_key)   # กันบริษัทเดียวกันรั่วข้าม fold
   tuning (nested): random search ≤ 20 รอบ ด้วย GroupKFold(3) ชั้นในบน train ของแต่ละ fold
                    → fold นอกใช้วัดผลอย่างเดียว ไม่ถูกใช้เลือก hyperparameter
   baseline = ค่ามัธยฐานของ (occupation cluster × ภาค)
   Ridge · RandomForest · XGBoost · LightGBM · CatBoost
   วัด R², RMSE, MAE, MAPE ต่อ fold + ค่าเฉลี่ย ± SD  → ml.model_result
   ▼
 เลือก champion (RMSE เฉลี่ยต่ำสุด, ต้องดีกว่า baseline ชัดเจน, เสถียรข้าม fold)
   ▼
 retrain champion บนข้อมูลทั้งหมด → export
   ├─ `models/salary_champion.joblib` (หรือไฟล์ native ของ CatBoost/LightGBM) + `feature_spec.json` → FastAPI `services/ml-api` (Render free / เซิร์ฟเวอร์มหาวิทยาลัย: GET /health, POST /predict, POST /predict/batch) ← Vercel `/api/salary/estimate` เป็น proxy (header `X-ML-Key`, timeout 8 วินาที)
   └─ ค่าคาดชุด feature มาตรฐาน → `mart.salary_prediction` (fallback)
 โมเดลอื่นอีก 4 ตัว + baseline ใช้ในหน้า ML Lab เท่านั้น ไม่ถูกเรียกในระบบจริง
```
- ผลลัพธ์แสดงเป็น **ช่วง** (p25–p75 ของค่าคาด จาก residual quantile) พร้อมข้อความ "ประมาณการจากประกาศที่ระบุเงินเดือน ไม่ใช่เงินเดือนจริง"
- ข้อจำกัดต้องเขียนในเล่ม: ประกาศที่ระบุเงินเดือนอาจเอนไปทางงานระดับต้น/ตำแหน่งที่เปิดเผยเงินเดือน (selection bias)

---

## 7. Data quality checks (บันทึกใน `staging.dq_result`)

| ด้าน | ตัวอย่าง check |
|---|---|
| Completeness | % ประกาศที่มี title / จังหวัด / หมวดงาน / เงินเดือนตัวเลข / ทักษะ ≥ 1 |
| Validity | `salary_min ≤ salary_max`, เงินเดือนอยู่ 5,000–500,000, จังหวัดอยู่ในรายชื่อ 77 จังหวัด, วันที่ไม่เป็นอนาคต |
| Uniqueness | % ซ้ำของ (source, source_job_id), ประกาศเนื้อหาเหมือนกันต่างรหัส |
| Consistency | หมวดงานกับ occupation cluster ไม่ขัดกัน, ชื่อบริษัท normalize แล้วชนกันกี่ราย |
| Freshness | อายุของประกาศล่าสุด, ประกาศหมดอายุแล้วที่ยังอยู่ใน mart |
| Taxonomy | % ประกาศที่ map ทักษะได้ ≥ 1, % คำถี่ที่ยังไม่ map, precision ที่ตรวจมือ 200 ประกาศ |
| Compliance | ไม่มีคอลัมน์ HR contact, ไม่มี gender/age ในชุด feature |
| Sampling | ทุกแถวใน fact มี `sample_stratum` + `sample_weight`, Σw ต่อชั้น ≈ N_ชั้น ใน `listing_seen` |

---

## 8. แชท Gemini (page-context)

`POST /api/chat`

```json
{
  "question": "ทำไมทักษะ SQL ถึงสูงกว่า Python",
  "pageContext": {
    "page": "market-explorer",
    "filters": {"province": "ทั้งประเทศ", "occupation": "Data & Analytics", "period": "2569-06..2569-11"},
    "kpis": [{"label": "ประกาศที่วิเคราะห์", "value": 5230}],
    "charts": [{"id": "skill-rank", "title": "ทักษะที่ถูกขอมากที่สุด", "rows": [["SQL", 0.41], ["Python", 0.33]]}],
    "tableTop": [],
    "asOf": "2569-11-18",
    "dataNotes": ["ตัวอย่างจาก JobThai", "ค่าที่ n < 5 ถูกซ่อน"]
  }
}
```
- Server: ตรวจ session/โควตา → ตัด `pageContext` ให้ไม่เกิน ~6,000 token (กราฟละ ≤ 20 แถว, ตาราง top 20) → เรียก Gemini ด้วย system prompt: ตอบไทย, ใช้เฉพาะข้อมูลใน `pageContext`, อ้างชื่อการ์ด, **ห้ามคำนวณหรือแต่งตัวเลขใหม่**, ไม่ตอบเรื่องบุคคล, ถ้าไม่มีข้อมูลให้แนะนำหน้าที่เกี่ยวข้อง
- ไม่ส่ง PII/ข้อความประกาศดิบ; ส่งเฉพาะตัวเลขรวมที่หน้านั้นแสดงอยู่แล้ว
- Rate limit: ผู้ใช้ล็อกอิน 20 คำถาม/วัน, ผู้เยี่ยมชม 5 คำถาม/วัน/IP (เก็บใน Postgres หรือ Vercel KV ถ้าใช้); ตอบ 429 พร้อมข้อความสุภาพ
- Response: `{answer, citedCards[], suggestedPages[]}`; บันทึกคำถามลง `app_chat_log` (ไม่เก็บ pageContext เต็ม)
- ไม่มี Text-to-SQL, ไม่มี LLM ติด label/ดึงทักษะ

---

## 9. Security / Compliance (สรุป — รายละเอียดใน CONTEXT.md)
- RLS ทุกตาราง `public`; ไม่เปิด `staging/dw/ml` ผ่าน API; service-role key อยู่ฝั่ง server/ETL เท่านั้น (`.env*` ใน `.gitignore`)
- เว็บแสดงเฉพาะ aggregate + ลิงก์ต้นฉบับ; ไม่มี endpoint คืนเนื้อหาประกาศ
- ไม่ใส่ gender/age ใน feature; เก็บ `scrape_run` เป็นหลักฐานว่า scrape ตามกติกา

---

## 10. โครงสร้าง repo

```text
southbi/
├─ apps/web/                 Next.js (app/, components/, lib/, messages/th.json en.json)
│   ├─ app/(public)/ (landing, login)   app/(student)/   app/(institution)/   app/(admin)/   app/ml-lab/
│   ├─ app/api/chat/route.ts   app/api/salary/estimate/route.ts
│   └─ components/charts/ (ECharts wrappers + theme)   components/chat/
├─ pipeline/                 Python
│   ├─ scraper/ (discovery.py fetch.py parse.py config.py)
│   ├─ etl/ (clean.py extract_skills.py map_taxonomy.py validate.py load_dw.py build_marts.py)
│   ├─ ml/ (features.py benchmark.py champion.py export_model.py)
│   └─ tests/
├─ taxonomy/ (skills.csv, aliases.csv, occupations.csv)
├─ supabase/migrations/      SQL (schema, RLS, marts, seed)
├─ data/raw/                 ไม่ commit
├─ spike/                    ผลทดลอง (raw/ ไม่ commit)
├─ services/ml-api/          FastAPI (main.py, requirements.txt, Dockerfile/render.yaml) — โหลด models/ และ feature_spec.json
├─ models/                   salary_champion.joblib + feature_spec.json (ไฟล์เล็ก, ไม่มีข้อมูลประกาศ)
├─ eval/                     labeling-guideline.md, skills_gold.csv (id + ทักษะ, ไม่มีข้อความประกาศ)
├─ docs/ (data-spike, DEPLOY.md, PROGRESS.md, chapters/, letters/, archive, test-report)
└─ README.md AGENTS.md GEMINI.md INDEX.md PLAN.md CONTEXT.md ARCHITECTURE.md DESIGN_SYSTEM.md FRONTEND_SPEC.md TASKS.md HANDOFF_GEMINI.md .env.example
```

ดูขั้นตอน deploy ทั้งหมดที่ [docs/DEPLOY.md](docs/DEPLOY.md)
