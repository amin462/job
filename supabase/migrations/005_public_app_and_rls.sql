-- =============================================================================
-- Migration 005: Public App Tables, RLS Policies, Auth Trigger & Safe RPCs
--                (T6.1, T6.3)
-- Project: Skill Demand Intelligence (E')
-- References: ARCHITECTURE.md §3.6 | PLAN.md D10, D18 | FRONTEND_SPEC.md §2, §3
-- =============================================================================

-- 1. Public App Tables (All protected by Row Level Security)

create table if not exists public.app_profile (
  user_id                   uuid primary key references auth.users (id) on delete cascade,
  role                      text not null default 'student' check (role in ('student', 'institution', 'admin')),
  display_name              text,
  province_th               text,
  target_occupation_cluster text,
  preferred_language        text not null default 'th' check (preferred_language in ('th', 'en')),
  created_at                timestamptz default now(),
  updated_at                timestamptz default now()
);

create table if not exists public.app_user_skill (
  user_id   uuid not null references auth.users (id) on delete cascade,
  skill_key int not null, -- Logical ref to dw.dim_skill (cross-schema FK omitted intentionally)
  level     smallint not null default 1 check (level between 1 and 3),
  primary key (user_id, skill_key)
);

create table if not exists public.app_curriculum (
  curriculum_id             bigint primary key generated always as identity,
  owner_id                  uuid not null references auth.users (id) on delete cascade,
  name                      text not null,
  target_occupation_cluster text,
  created_at                timestamptz default now()
);

create table if not exists public.app_curriculum_skill (
  curriculum_id bigint not null references public.app_curriculum (curriculum_id) on delete cascade,
  skill_key     int not null,
  course_name   text not null default '',
  primary key (curriculum_id, skill_key, course_name)
);

create table if not exists public.app_chat_log (
  chat_id    bigserial primary key,
  user_id    uuid references auth.users (id) on delete set null,
  page       text,
  question   text,
  answered   boolean,
  created_at timestamptz default now()
);

create table if not exists public.app_alias_suggestion (
  id             bigserial primary key,
  proposed_by    uuid references auth.users (id) on delete set null,
  alias          text not null,
  skill_key      int,
  status         text not null default 'pending' check (status in ('pending', 'approved', 'rejected')),
  freq           int not null default 1,
  sample_context text, -- Admin-only short snippet <= 120 chars; never exposed publicly
  reviewed_by    uuid references auth.users (id) on delete set null,
  reviewed_at    timestamptz,
  created_at     timestamptz default now()
);

-- 2. Enable RLS on ALL public.app_* tables
alter table public.app_profile          enable row level security;
alter table public.app_user_skill       enable row level security;
alter table public.app_curriculum       enable row level security;
alter table public.app_curriculum_skill enable row level security;
alter table public.app_chat_log         enable row level security;
alter table public.app_alias_suggestion enable row level security;

-- 3. Table Privileges (least privilege)
revoke all on
  public.app_profile,
  public.app_user_skill,
  public.app_curriculum,
  public.app_curriculum_skill,
  public.app_chat_log,
  public.app_alias_suggestion
from public, anon, authenticated;

grant select, insert, update, delete on
  public.app_profile,
  public.app_user_skill,
  public.app_curriculum,
  public.app_curriculum_skill,
  public.app_alias_suggestion
to authenticated;

grant insert on public.app_chat_log to anon, authenticated;
grant select on public.app_chat_log to authenticated; -- Filtered by chat_admin_read RLS policy

grant usage, select on sequence
  public.app_curriculum_curriculum_id_seq,
  public.app_alias_suggestion_id_seq
to authenticated;

grant usage, select on sequence public.app_chat_log_chat_id_seq to anon, authenticated;

do $$
begin
  if exists (select 1 from pg_roles where rolname = 'service_role') then
    grant all on
      public.app_profile,
      public.app_user_skill,
      public.app_curriculum,
      public.app_curriculum_skill,
      public.app_chat_log,
      public.app_alias_suggestion
    to service_role;
    grant usage, select on all sequences in schema public to service_role;
  end if;
end
$$;

-- 4. Admin Helper Function (SECURITY DEFINER to avoid recursive RLS lookup)
create or replace function public.is_admin()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.app_profile
    where user_id = auth.uid()
      and role = 'admin'
  );
$$;

grant execute on function public.is_admin() to anon, authenticated, service_role;

-- 5. RLS Policies (ARCHITECTURE.md §3.6)

-- 5.1 app_profile: split insert/update so users CANNOT elevate themselves to 'admin'
drop policy if exists profile_select      on public.app_profile;
drop policy if exists profile_insert      on public.app_profile;
drop policy if exists profile_update      on public.app_profile;
drop policy if exists profile_delete_self on public.app_profile;
drop policy if exists profile_admin       on public.app_profile;

create policy profile_select on public.app_profile
  for select
  using (user_id = auth.uid() or public.is_admin());

create policy profile_insert on public.app_profile
  for insert
  with check (user_id = auth.uid() and role in ('student', 'institution'));

create policy profile_update on public.app_profile
  for update
  using (user_id = auth.uid())
  with check (user_id = auth.uid() and role in ('student', 'institution'));

create policy profile_delete_self on public.app_profile
  for delete
  using (user_id = auth.uid());

create policy profile_admin on public.app_profile
  for all
  using (public.is_admin())
  with check (public.is_admin());

-- 5.2 app_user_skill
drop policy if exists uskill_self on public.app_user_skill;
create policy uskill_self on public.app_user_skill
  for all
  using (user_id = auth.uid())
  with check (user_id = auth.uid());

-- 5.3 app_curriculum
drop policy if exists curric_owner on public.app_curriculum;
create policy curric_owner on public.app_curriculum
  for all
  using (owner_id = auth.uid())
  with check (owner_id = auth.uid());

-- 5.4 app_curriculum_skill
drop policy if exists cskill_owner on public.app_curriculum_skill;
create policy cskill_owner on public.app_curriculum_skill
  for all
  using (
    exists (
      select 1
      from public.app_curriculum c
      where c.curriculum_id = app_curriculum_skill.curriculum_id
        and c.owner_id = auth.uid()
    )
  )
  with check (
    exists (
      select 1
      from public.app_curriculum c
      where c.curriculum_id = app_curriculum_skill.curriculum_id
        and c.owner_id = auth.uid()
    )
  );

-- 5.5 app_chat_log
drop policy if exists chat_insert     on public.app_chat_log;
drop policy if exists chat_admin_read on public.app_chat_log;

create policy chat_insert on public.app_chat_log
  for insert
  with check (user_id = auth.uid() or user_id is null);

create policy chat_admin_read on public.app_chat_log
  for select
  using (public.is_admin());

-- 5.6 app_alias_suggestion (users can propose pending only; admins can review/approve/reject)
drop policy if exists alias_sugg              on public.app_alias_suggestion;
drop policy if exists alias_sugg_select       on public.app_alias_suggestion;
drop policy if exists alias_sugg_insert       on public.app_alias_suggestion;
drop policy if exists alias_sugg_admin_update on public.app_alias_suggestion;
drop policy if exists alias_sugg_delete       on public.app_alias_suggestion;

create policy alias_sugg_select on public.app_alias_suggestion
  for select
  using (public.is_admin() or proposed_by = auth.uid());

create policy alias_sugg_insert on public.app_alias_suggestion
  for insert
  with check (
    public.is_admin()
    or (proposed_by = auth.uid() and status = 'pending')
  );

create policy alias_sugg_admin_update on public.app_alias_suggestion
  for update
  using (public.is_admin())
  with check (public.is_admin());

create policy alias_sugg_delete on public.app_alias_suggestion
  for delete
  using (
    public.is_admin()
    or (proposed_by = auth.uid() and status = 'pending')
  );

-- 6. Auth Signup Trigger (defaults to 'student'; NEVER accepts 'admin' from user metadata)
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_requested_role text;
  v_safe_role      text;
  v_display_name   text;
begin
  v_requested_role := lower(coalesce(new.raw_user_meta_data ->> 'role', ''));
  if v_requested_role in ('student', 'institution') then
    v_safe_role := v_requested_role;
  else
    v_safe_role := 'student';
  end if;

  v_display_name := coalesce(
    nullif(trim(new.raw_user_meta_data ->> 'display_name'), ''),
    split_part(coalesce(new.email, 'user'), '@', 1)
  );

  insert into public.app_profile (user_id, role, display_name)
  values (new.id, v_safe_role, v_display_name)
  on conflict (user_id) do nothing;

  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- 7. Safe Public RPCs (expose controlled dimension metadata without opening dw schema)

create or replace function public.get_dim_skills()
returns table (
  skill_key       int,
  skill_canonical text,
  skill_slug      text,
  skill_name_th   text,
  skill_type      text,
  skill_group     text,
  onet_ref        text,
  esco_ref        text,
  aliases         text[]
)
language sql
stable
security definer
set search_path = public, dw
as $$
  select
    s.skill_key,
    s.skill_canonical,
    coalesce(s.skill_slug, trim(both '-' from lower(regexp_replace(s.skill_canonical, '[^a-zA-Z0-9]+', '-', 'g')))) as skill_slug,
    s.skill_name_th,
    s.skill_type,
    s.skill_group,
    s.onet_ref,
    s.esco_ref,
    coalesce(
      array_agg(distinct a.alias order by a.alias) filter (where a.status = 'approved' and a.alias is not null),
      array[]::text[]
    ) as aliases
  from dw.dim_skill s
  left join dw.skill_alias a on a.skill_key = s.skill_key and a.status = 'approved'
  group by s.skill_key, s.skill_canonical, s.skill_slug, s.skill_name_th, s.skill_type, s.skill_group, s.onet_ref, s.esco_ref
  order by s.skill_canonical;
$$;

grant execute on function public.get_dim_skills() to anon, authenticated, service_role;

create or replace function public.get_dim_occupations()
returns table (
  occupation_cluster text,
  occupation_slug    text,
  occupation_name_th text,
  onet_ref           text,
  n_titles           bigint
)
language sql
stable
security definer
set search_path = public, dw
as $$
  select
    o.occupation_cluster,
    coalesce(min(o.occupation_slug), trim(both '-' from lower(regexp_replace(o.occupation_cluster, '[^a-zA-Z0-9]+', '-', 'g')))) as occupation_slug,
    coalesce(max(o.occupation_name_th), o.occupation_cluster) as occupation_name_th,
    max(o.onet_ref) as onet_ref,
    count(*)::bigint as n_titles
  from dw.dim_occupation o
  group by o.occupation_cluster
  order by o.occupation_cluster;
$$;

grant execute on function public.get_dim_occupations() to anon, authenticated, service_role;

create or replace function public.get_dim_locations()
returns table (
  location_key  int,
  province_code text,
  province_th   text,
  province_en   text,
  region        text,
  is_south14    boolean
)
language sql
stable
security definer
set search_path = public, dw
as $$
  select
    l.location_key,
    l.province_code,
    l.province_th,
    l.province_en,
    l.region,
    l.is_south14
  from dw.dim_location l
  where l.district_th = ''
  order by l.province_code, l.province_th;
$$;

grant execute on function public.get_dim_locations() to anon, authenticated, service_role;

-- 8. Admin-Only RPCs (strictly gated by public.is_admin() or service_role)

create or replace function public.get_admin_pipeline_status()
returns table (
  scrape_run_id    bigint,
  source           text,
  scope            text,
  started_at       timestamptz,
  finished_at      timestamptz,
  status           text,
  n_discovered     int,
  n_fetched        int,
  n_failed         int,
  is_blocked_flag  boolean,
  duration_seconds numeric,
  n_listings_seen  int
)
language plpgsql
stable
security definer
set search_path = public, mart
as $$
begin
  if not (
    public.is_admin()
    or coalesce(
         nullif(current_setting('request.jwt.claim.role', true), ''),
         nullif((current_setting('request.jwt.claims', true)::jsonb ->> 'role'), '')
       ) = 'service_role'
  ) then
    raise exception 'forbidden: admin role required' using errcode = '42501';
  end if;

  return query
  select
    ps.scrape_run_id,
    ps.source,
    ps.scope,
    ps.started_at,
    ps.finished_at,
    ps.status,
    ps.n_discovered,
    ps.n_fetched,
    ps.n_failed,
    ps.is_blocked_flag,
    ps.duration_seconds,
    ps.n_listings_seen
  from mart.pipeline_status ps;
end;
$$;

revoke all on function public.get_admin_pipeline_status() from public, anon;
grant execute on function public.get_admin_pipeline_status() to authenticated, service_role;

create or replace function public.get_admin_dq_summary()
returns table (
  dq_id         bigint,
  scrape_run_id bigint,
  source        text,
  dimension     text,
  check_name    text,
  table_name    text,
  n_total       int,
  n_fail        int,
  fail_rate     numeric,
  pass          boolean,
  details       text,
  checked_at    timestamptz
)
language plpgsql
stable
security definer
set search_path = public, mart
as $$
begin
  if not (
    public.is_admin()
    or coalesce(
         nullif(current_setting('request.jwt.claim.role', true), ''),
         nullif((current_setting('request.jwt.claims', true)::jsonb ->> 'role'), '')
       ) = 'service_role'
  ) then
    raise exception 'forbidden: admin role required' using errcode = '42501';
  end if;

  return query
  select
    d.dq_id,
    d.scrape_run_id,
    d.source,
    d.dimension,
    d.check_name,
    d.table_name,
    d.n_total,
    d.n_fail,
    d.fail_rate,
    d.pass,
    d.details,
    d.checked_at
  from mart.dq_summary d;
end;
$$;

revoke all on function public.get_admin_dq_summary() from public, anon;
grant execute on function public.get_admin_dq_summary() to authenticated, service_role;

-- Rule-based taxonomy queue using pg_trgm similarity >= 0.4 ONLY (NO AI/LLM)
create or replace function public.get_admin_taxonomy_queue()
returns table (
  suggestion_id             bigint,
  pending_alias             text,
  freq                      int,
  sample_context            text,
  requested_skill_key       int,
  status                    text,
  created_at                timestamptz,
  suggested_skill_key       int,
  suggested_skill_canonical text,
  suggested_skill_name_th   text,
  suggested_matched_alias   text,
  similarity_score          numeric
)
language plpgsql
stable
security definer
set search_path = public, dw, extensions
as $$
begin
  if not (
    public.is_admin()
    or coalesce(
         nullif(current_setting('request.jwt.claim.role', true), ''),
         nullif((current_setting('request.jwt.claims', true)::jsonb ->> 'role'), '')
       ) = 'service_role'
  ) then
    raise exception 'forbidden: admin role required' using errcode = '42501';
  end if;

  return query
  select
    q.id as suggestion_id,
    q.alias as pending_alias,
    q.freq,
    left(q.sample_context, 120) as sample_context,
    q.skill_key as requested_skill_key,
    q.status,
    q.created_at,
    best.skill_key as suggested_skill_key,
    best.skill_canonical as suggested_skill_canonical,
    best.skill_name_th as suggested_skill_name_th,
    best.matched_alias as suggested_matched_alias,
    best.sim_score as similarity_score
  from public.app_alias_suggestion q
  left join lateral (
    select
      s.skill_key,
      s.skill_canonical,
      s.skill_name_th,
      a.alias as matched_alias,
      round(similarity(lower(a.alias), lower(q.alias))::numeric, 3) as sim_score
    from dw.skill_alias a
    join dw.dim_skill s on s.skill_key = a.skill_key
    where a.status = 'approved'
      and similarity(lower(a.alias), lower(q.alias)) >= 0.4
    order by similarity(lower(a.alias), lower(q.alias)) desc, a.alias_id asc
    limit 1
  ) best on true
  where q.status = 'pending'
  order by q.freq desc, q.id asc;
end;
$$;

revoke all on function public.get_admin_taxonomy_queue() from public, anon;
grant execute on function public.get_admin_taxonomy_queue() to authenticated, service_role;

create or replace function public.admin_review_alias(
  p_suggestion_id       bigint,
  p_action              text,
  p_target_skill_key    int default null,
  p_new_skill_canonical text default null,
  p_new_skill_name_th   text default null,
  p_new_skill_type      text default 'technical',
  p_new_skill_group     text default null,
  p_match_type          text default 'exact',
  p_lang                text default null
)
returns jsonb
language plpgsql
security definer
set search_path = public, dw
as $$
declare
  v_sugg      public.app_alias_suggestion%rowtype;
  v_skill_key int;
  v_slug      text;
begin
  if not (
    public.is_admin()
    or coalesce(
         nullif(current_setting('request.jwt.claim.role', true), ''),
         nullif((current_setting('request.jwt.claims', true)::jsonb ->> 'role'), '')
       ) = 'service_role'
  ) then
    raise exception 'forbidden: admin role required' using errcode = '42501';
  end if;

  if p_action not in ('approve', 'reject', 'map') then
    raise exception 'invalid action: must be approve, reject, or map';
  end if;

  select * into v_sugg
  from public.app_alias_suggestion
  where id = p_suggestion_id
  for update;

  if not found then
    raise exception 'suggestion % not found', p_suggestion_id;
  end if;

  if p_action = 'reject' then
    update public.app_alias_suggestion
    set status      = 'rejected',
        reviewed_by = auth.uid(),
        reviewed_at = now()
    where id = p_suggestion_id;

    return jsonb_build_object(
      'ok', true,
      'suggestion_id', p_suggestion_id,
      'status', 'rejected',
      'alias', v_sugg.alias
    );
  end if;

  -- approve or map
  v_skill_key := coalesce(p_target_skill_key, v_sugg.skill_key);

  if v_skill_key is null then
    if nullif(trim(coalesce(p_new_skill_canonical, '')), '') is null then
      raise exception 'target_skill_key or new_skill_canonical is required to approve/map';
    end if;

    v_slug := trim(both '-' from lower(regexp_replace(trim(p_new_skill_canonical), '[^a-zA-Z0-9]+', '-', 'g')));
    if v_slug = '' then
      v_slug := 'skill-' || substr(md5(trim(p_new_skill_canonical)), 1, 8);
    end if;

    insert into dw.dim_skill (skill_canonical, skill_slug, skill_name_th, skill_type, skill_group)
    values (
      trim(p_new_skill_canonical),
      v_slug,
      coalesce(nullif(trim(p_new_skill_name_th), ''), trim(p_new_skill_canonical)),
      coalesce(nullif(trim(p_new_skill_type), ''), 'technical'),
      coalesce(nullif(trim(p_new_skill_group), ''), 'Other')
    )
    on conflict (skill_canonical) do update set
      skill_name_th = coalesce(excluded.skill_name_th, dw.dim_skill.skill_name_th)
    returning skill_key into v_skill_key;
  end if;

  insert into dw.skill_alias (skill_key, alias, lang, match_type, status)
  values (
    v_skill_key,
    lower(trim(v_sugg.alias)),
    p_lang,
    coalesce(nullif(trim(p_match_type), ''), 'exact'),
    'approved'
  )
  on conflict (alias) do update set
    skill_key  = excluded.skill_key,
    match_type = excluded.match_type,
    status     = 'approved';

  update public.app_alias_suggestion
  set status      = 'approved',
      skill_key   = v_skill_key,
      reviewed_by = auth.uid(),
      reviewed_at = now()
  where id = p_suggestion_id;

  return jsonb_build_object(
    'ok', true,
    'suggestion_id', p_suggestion_id,
    'status', 'approved',
    'skill_key', v_skill_key,
    'alias', lower(trim(v_sugg.alias))
  );
end;
$$;

revoke all on function public.admin_review_alias(bigint, text, int, text, text, text, text, text, text) from public, anon;
grant execute on function public.admin_review_alias(bigint, text, int, text, text, text, text, text, text) to authenticated, service_role;

-- 9. Demo Persona Data Seeder Helper (T6.3 — callable ONLY by service_role / postgres)
--    Creates persona profiles, sample skills, and sample curriculum after Auth users are created.
create or replace function public.attach_demo_persona(
  p_user_id uuid,
  p_persona text
)
returns jsonb
language plpgsql
security definer
set search_path = public, dw
as $$
declare
  v_curric_id bigint;
begin
  if p_persona not in ('student_data', 'student_acc', 'institution', 'admin') then
    raise exception 'unknown persona: %', p_persona;
  end if;

  if p_persona = 'student_data' then
    insert into public.app_profile (user_id, role, display_name, province_th, target_occupation_cluster)
    values (p_user_id, 'student', 'นักศึกษาสาย Data (Demo)', 'สงขลา', 'Data & Analytics')
    on conflict (user_id) do update set
      role = 'student',
      display_name = excluded.display_name,
      province_th = excluded.province_th,
      target_occupation_cluster = excluded.target_occupation_cluster;

    insert into public.app_user_skill (user_id, skill_key, level)
    select p_user_id, s.skill_key, 2
    from dw.dim_skill s
    where s.skill_canonical in ('Microsoft Excel', 'SQL', 'Python', 'Communication')
    on conflict (user_id, skill_key) do nothing;

  elsif p_persona = 'student_acc' then
    insert into public.app_profile (user_id, role, display_name, province_th, target_occupation_cluster)
    values (p_user_id, 'student', 'นักศึกษาสายบัญชี (Demo)', 'กรุงเทพมหานคร', 'Accounting & Finance')
    on conflict (user_id) do update set
      role = 'student',
      display_name = excluded.display_name,
      province_th = excluded.province_th,
      target_occupation_cluster = excluded.target_occupation_cluster;

    insert into public.app_user_skill (user_id, skill_key, level)
    select p_user_id, s.skill_key, 2
    from dw.dim_skill s
    where s.skill_canonical in ('Accounting', 'Tax', 'Microsoft Excel', 'Microsoft Word')
    on conflict (user_id, skill_key) do nothing;

  elsif p_persona = 'institution' then
    insert into public.app_profile (user_id, role, display_name, province_th, target_occupation_cluster)
    values (p_user_id, 'institution', 'อาจารย์ผู้ดูแลหลักสูตร (Demo)', 'สงขลา', 'Data & Analytics')
    on conflict (user_id) do update set
      role = 'institution',
      display_name = excluded.display_name,
      province_th = excluded.province_th,
      target_occupation_cluster = excluded.target_occupation_cluster;

    select curriculum_id into v_curric_id
    from public.app_curriculum
    where owner_id = p_user_id
      and name = 'หลักสูตรคอมพิวเตอร์ธุรกิจ / Data Analytics (ตัวอย่าง)'
    limit 1;

    if v_curric_id is null then
      insert into public.app_curriculum (owner_id, name, target_occupation_cluster)
      values (p_user_id, 'หลักสูตรคอมพิวเตอร์ธุรกิจ / Data Analytics (ตัวอย่าง)', 'Data & Analytics')
      returning curriculum_id into v_curric_id;
    end if;

    insert into public.app_curriculum_skill (curriculum_id, skill_key, course_name)
    select
      v_curric_id,
      s.skill_key,
      case
        when s.skill_canonical in ('SQL', 'Database Management') then 'การจัดการฐานข้อมูล'
        when s.skill_canonical in ('Python', 'Power BI') then 'การวิเคราะห์ข้อมูลทางธุรกิจ'
        else 'คอมพิวเตอร์และเครื่องมือสำนักงาน'
      end
    from dw.dim_skill s
    where s.skill_canonical in ('Microsoft Excel', 'SQL', 'Python', 'Power BI', 'Communication')
    on conflict (curriculum_id, skill_key, course_name) do nothing;

  elsif p_persona = 'admin' then
    insert into public.app_profile (user_id, role, display_name, province_th)
    values (p_user_id, 'admin', 'ผู้ดูแลระบบ (Demo Admin)', 'สงขลา')
    on conflict (user_id) do update set
      role = 'admin',
      display_name = excluded.display_name,
      province_th = excluded.province_th;
  end if;

  return jsonb_build_object('ok', true, 'user_id', p_user_id, 'persona', p_persona);
end;
$$;

revoke all on function public.attach_demo_persona(uuid, text) from public, anon, authenticated;
grant execute on function public.attach_demo_persona(uuid, text) to service_role;
