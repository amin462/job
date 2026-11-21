# Supabase Migrations — Skill Demand Intelligence (E′)

> Reference: [ARCHITECTURE.md §3](../ARCHITECTURE.md), [PLAN.md (D10, D18)](../PLAN.md), [TASKS.md (T1.1, T3.1–T3.9, T4.6, T6.1–T6.3)](../TASKS.md)

## 1. Migration Order & Scope

| File | Tasks | Summary |
|---|---|---|
| `001_schemas_and_staging.sql` | T1.1 | Creates `staging`, `dw`, `mart`, `ml` schemas, enables `pg_trgm`, revokes `staging`/`dw`/`ml` from `anon`/`authenticated`, grants `USAGE` on `mart` (with default table privileges revoked), and creates `staging.scrape_run`, `staging.listing_seen`, `staging.job_posting_raw` (zero HR contact PII), and `staging.dq_result`. |
| `002_dw_dimensions_and_seed.sql` | T3.1 | Creates all 10 DW dimension tables (`dim_date`, `dim_source`, `dim_location`, `dim_company`, `dim_occupation`, `dim_skill`, `skill_alias` + GIN trigram index, `dim_education`, `dim_experience`, `dim_employment_type`) and seeds `dim_source` (`jobthai`, `jobbkk` only), `dim_education`, `dim_experience`, `dim_employment_type`, `dim_date` (`2025-01-01`..`2027-12-31`), and `dim_location` (all 77 Thai provinces + `หลายจังหวัด` + `ต่างประเทศ`, regions, and exact `is_south14` flags). |
| `003_dw_facts.sql` | T3.2, T3.9 | Creates `dw.fact_job_posting` (with `salary_open_max`, `salary_unit_orig`, generated `has_salary`, `first_seen_date_key`, `last_seen_date_key`, `sample_stratum`, `sample_weight`), `dw.fact_posting_skill`, `dw.fact_labor_monthly`, and DW query indexes. |
| `004_marts_and_ml_grants.sql` | T3.5, T3.6, T3.8, T4.6 | Creates `ml.experiment`, `ml.model_result`, `ml.feature_importance`, all 12 `mart` objects (+ `mart.ml_feature_importance`), enforces `n_postings >= 5` suppression on public marts, and grants `SELECT` to `anon, authenticated` ONLY on the public marts (strictly withholding `mart.pipeline_status` and `mart.dq_summary`). |
| `005_public_app_and_rls.sql` | T6.1, T6.3 | Creates the 6 `public.app_*` tables with RLS enabled on every table, `public.is_admin()`, split `insert`/`update` RLS policies blocking self-promotion to `admin`, the `handle_new_user` signup trigger, safe public dimension RPCs, strictly gated admin RPCs (`pg_trgm similarity >= 0.4` taxonomy queue without AI), and `attach_demo_persona` (`service_role` only). |

## 2. Schema Isolation & Security Model

- **`staging` / `dw` / `ml`:** Completely inaccessible to `anon` and `authenticated` roles. Only ETL/ML scripts via `DATABASE_URL` (`postgres`) or `service_role` can read/write these schemas.
- **`mart`:** Exposed read-only on a per-object allowlist:
  - **Public (`anon`, `authenticated`):** `skill_demand_weekly`, `skill_cooccurrence`, `occupation_skill_profile`, `salary_stats`, `posting_volume_daily`, `curriculum_coverage_ref`, `public_summary`, `ml_leaderboard`, `ml_feature_importance`, `salary_prediction`, `top_links`.
  - **Admin-only (`service_role` / `get_admin_*` RPCs):** `mart.pipeline_status`, `mart.dq_summary`.
- **`public` (`app_*`):** All 6 tables have Row Level Security (`ENABLE ROW LEVEL SECURITY`) enforced:
  - Users can view/edit only their own rows (`auth.uid()`).
  - `profile_insert` and `profile_update` policies enforce `role in ('student', 'institution')`, preventing any user from elevating themselves to `admin`.
  - `handle_new_user` trigger defaults to `'student'` and rejects `'admin'` in signup metadata.
- **ToS & PDPA Guarantees:**
  - `staging.job_posting_raw` and `dw.fact_job_posting` have **no HR contact columns** (`telephone`, `email`, `contactPoint`).
  - `mart.top_links` exposes only `title_short` (`<= 120` chars), `source_name`, and `source_url` (max 5 links per `occupation_cluster × province_th`, `n_postings >= 5`), never `description` or `qualifications`.
  - `dw.fact_job_posting` contains **no `gender` or `age` columns** (fairness rule D6).

## 3. Applying Migrations

Using Supabase CLI or `psql` against `$DATABASE_URL`:

```bash
# Option A: Apply sequentially with psql
for f in supabase/migrations/*.sql; do
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$f"
done

# Option B: With Supabase CLI linked project
npx supabase db push
```

> **PostgREST Note:** In the Supabase Dashboard (`Settings -> API -> Exposed schemas`), ensure `mart` is added alongside `public` so Next.js Server Components / Supabase client can query `supabase.schema('mart').from(...)`, while keeping `staging`, `dw`, and `ml` **excluded**.

## 4. Verification Queries (Grants, Seeds & RLS)

### 4.1 Verify Seeded Counts
```sql
select count(*) as n_locations,
       count(*) filter (where is_south14) as n_south14
from dw.dim_location;
-- Expected: n_locations = 79 (77 provinces + 'หลายจังหวัด' + 'ต่างประเทศ'), n_south14 = 14

select count(*) as n_dates, min(full_date), max(full_date) from dw.dim_date;
-- Expected: n_dates = 1095 (2025-01-01 to 2027-12-31)

select source_name from dw.dim_source order by source_key;
-- Expected: jobthai, jobbkk ONLY
```

### 4.2 Verify Schema & Mart Privileges for `anon` / `authenticated`
```sql
-- Must return FALSE for anon and authenticated on staging, dw, ml
select
  has_schema_privilege('anon', 'staging', 'USAGE') as anon_staging,
  has_schema_privilege('anon', 'dw', 'USAGE')      as anon_dw,
  has_schema_privilege('anon', 'ml', 'USAGE')      as anon_ml,
  has_schema_privilege('anon', 'mart', 'USAGE')    as anon_mart;

-- Must return FALSE for anon and authenticated on admin-only marts
select
  has_table_privilege('anon', 'mart.pipeline_status', 'SELECT')          as anon_pipeline,
  has_table_privilege('authenticated', 'mart.pipeline_status', 'SELECT') as auth_pipeline,
  has_table_privilege('anon', 'mart.dq_summary', 'SELECT')               as anon_dq,
  has_table_privilege('authenticated', 'mart.dq_summary', 'SELECT')      as auth_dq,
  has_table_privilege('anon', 'mart.public_summary', 'SELECT')           as anon_public_summary;
```

### 4.3 Verify RLS Enforcement & Privilege-Escalation Prevention
```sql
begin;
  -- Simulate authenticated user A trying to insert role = 'admin'
  set local role authenticated;
  select set_config('request.jwt.claim.role', 'authenticated', true);
  select set_config('request.jwt.claim.sub', '11111111-1111-1111-1111-111111111111', true);

  -- Should FAIL with RLS violation (42501):
  insert into public.app_profile (user_id, role)
  values ('11111111-1111-1111-1111-111111111111', 'admin');
rollback;

begin;
  -- Non-admin calling admin RPC should FAIL with 42501 ('forbidden: admin role required')
  set local role authenticated;
  select set_config('request.jwt.claim.role', 'authenticated', true);
  select set_config('request.jwt.claim.sub', '11111111-1111-1111-1111-111111111111', true);
  select * from public.get_admin_pipeline_status();
rollback;
```
