"""Automated Supabase security, schema-grant, and RLS verification suite (T3.8, T6.4).

Verifies:
1. Schema isolation: `anon` / `authenticated` cannot access `staging`, `dw`, `ml`,
   nor admin-only marts (`mart.pipeline_status`, `mart.dq_summary`).
2. Public mart & RPC access: `mart.public_summary` and `public.get_dim_skills` are
   granted to `anon`/`authenticated` (and checks whether PostgREST has `mart` exposed).
3. Live Auth + RLS matrix (with ephemeral test users cleaned up in `finally`):
   - Signup trigger ignores `role='admin'` in user_metadata.
   - Users cannot self-elevate to `role='admin'` via INSERT or UPDATE on `app_profile`.
   - User A cannot read/modify User B's `app_profile` or `app_user_skill`.
   - Non-admin users cannot call admin RPCs (`get_admin_pipeline_status`, `get_admin_dq_summary`).
   - Admin users can call admin RPCs.

Usage:
    .venv\\Scripts\\python.exe -X utf8 -m pipeline.check_permissions
"""
from __future__ import annotations

import os
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import psycopg
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


def _load_env() -> None:
    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)


def _get_required_keys() -> tuple[str, str, str, str]:
    url = (os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL") or "").strip().rstrip("/")
    pub = (os.getenv("SUPABASE_PUBLISHABLE_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY") or "").strip()
    sec = (os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    dsn = (os.getenv("DATABASE_URL") or "").strip()
    if not all([url, pub, sec, dsn]):
        raise RuntimeError("Missing required Supabase env vars (SUPABASE_URL, publishable/anon key, secret/service_role key, DATABASE_URL).")
    return url, pub, sec, dsn


def check_postgres_privileges(dsn: str) -> list[CheckResult]:
    """Verify schema/table privileges and SET LOCAL ROLE behavior directly in Postgres."""
    results: list[CheckResult] = []
    with psycopg.connect(dsn, connect_timeout=15) as conn:
        with conn.cursor() as cur:
            # 1. Schema privileges for anon & authenticated
            for role in ("anon", "authenticated"):
                for schema in ("staging", "dw", "ml"):
                    cur.execute("SELECT has_schema_privilege(%s, %s, 'USAGE')", (role, schema))
                    allowed = bool(cur.fetchone()[0])
                    results.append(
                        CheckResult(
                            f"pg_schema_denied:{role}:{schema}",
                            not allowed,
                            f"has_schema_privilege={allowed} (expected False)",
                        )
                    )
                cur.execute("SELECT has_schema_privilege(%s, 'mart', 'USAGE')", (role,))
                mart_ok = bool(cur.fetchone()[0])
                results.append(
                    CheckResult(
                        f"pg_schema_allowed:{role}:mart",
                        mart_ok,
                        f"has_schema_privilege={mart_ok} (expected True)",
                    )
                )

            # 2. Table/view privileges inside mart
            for role in ("anon", "authenticated"):
                for admin_view in ("mart.pipeline_status", "mart.dq_summary"):
                    cur.execute("SELECT has_table_privilege(%s, %s, 'SELECT')", (role, admin_view))
                    allowed = bool(cur.fetchone()[0])
                    results.append(
                        CheckResult(
                            f"pg_table_denied:{role}:{admin_view}",
                            not allowed,
                            f"has_table_privilege={allowed} (expected False)",
                        )
                    )
                cur.execute("SELECT has_table_privilege(%s, 'mart.public_summary', 'SELECT')", (role,))
                pub_ok = bool(cur.fetchone()[0])
                results.append(
                    CheckResult(
                        f"pg_table_allowed:{role}:mart.public_summary",
                        pub_ok,
                        f"has_table_privilege={pub_ok} (expected True)",
                    )
                )

        # 3. Execute actual SELECT as anon inside rolled-back transaction
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute("BEGIN")
            cur.execute("SET LOCAL ROLE anon")
            try:
                cur.execute("SELECT n_postings FROM mart.public_summary")
                _ = cur.fetchone()
                results.append(CheckResult("pg_exec_anon_public_summary", True, "SELECT mart.public_summary succeeded as anon"))
            except psycopg.Error as exc:
                results.append(CheckResult("pg_exec_anon_public_summary", False, f"unexpected error: {exc}"))
            finally:
                conn.rollback()

        for blocked_obj in ("dw.fact_job_posting", "staging.job_posting_raw", "ml.experiment", "mart.pipeline_status", "mart.dq_summary"):
            with conn.cursor() as cur:
                cur.execute("BEGIN")
                cur.execute("SET LOCAL ROLE anon")
                try:
                    cur.execute(f"SELECT 1 FROM {blocked_obj} LIMIT 1")
                    results.append(CheckResult(f"pg_exec_anon_denied:{blocked_obj}", False, "query succeeded unexpectedly"))
                except psycopg.errors.InsufficientPrivilege:
                    results.append(CheckResult(f"pg_exec_anon_denied:{blocked_obj}", True, "blocked with InsufficientPrivilege (42501)"))
                finally:
                    conn.rollback()

    return results


def _create_temp_user(client: httpx.Client, url: str, sec: str, email: str, password: str, metadata: dict[str, Any] | None = None) -> str:
    resp = client.post(
        f"{url}/auth/v1/admin/users",
        headers={"apikey": sec, "Authorization": f"Bearer {sec}"},
        json={
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": metadata or {},
        },
        timeout=15,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Failed creating temp user ({resp.status_code}): {resp.text}")
    return str(resp.json()["id"])


def _login_user(client: httpx.Client, url: str, pub: str, email: str, password: str) -> str:
    resp = client.post(
        f"{url}/auth/v1/token?grant_type=password",
        headers={"apikey": pub},
        json={"email": email, "password": password},
        timeout=15,
    )
    if resp.status_code != 200 or "access_token" not in resp.json():
        raise RuntimeError(f"Failed logging in temp user ({resp.status_code}): {resp.text}")
    return str(resp.json()["access_token"])


def _delete_temp_user(client: httpx.Client, url: str, sec: str, user_id: str) -> None:
    client.delete(
        f"{url}/auth/v1/admin/users/{user_id}",
        headers={"apikey": sec, "Authorization": f"Bearer {sec}"},
        timeout=15,
    )


def check_rest_and_rls(url: str, pub: str, sec: str) -> tuple[list[CheckResult], bool]:
    """Run live PostgREST + Auth + RLS tests. Returns (results, mart_schema_exposed)."""
    results: list[CheckResult] = []
    mart_exposed = False
    created_ids: list[str] = []

    with httpx.Client() as client:
        # 1. Anonymous REST checks (publishable key only)
        for schema, table in (
            ("staging", "job_posting_raw"),
            ("dw", "fact_job_posting"),
            ("ml", "experiment"),
            ("mart", "pipeline_status"),
            ("mart", "dq_summary"),
        ):
            r = client.get(
                f"{url}/rest/v1/{table}?select=*&limit=1",
                headers={"apikey": pub, "Accept-Profile": schema},
                timeout=15,
            )
            results.append(
                CheckResult(
                    f"rest_anon_denied:{schema}.{table}",
                    r.status_code in (401, 403, 404, 406),
                    f"HTTP {r.status_code}",
                )
            )

        r_pub_sum = client.get(
            f"{url}/rest/v1/public_summary?select=*&limit=1",
            headers={"apikey": pub, "Accept-Profile": "mart"},
            timeout=15,
        )
        if r_pub_sum.status_code == 200:
            mart_exposed = True
            results.append(CheckResult("rest_anon_mart_public_summary", True, "HTTP 200 (mart exposed in PostgREST)"))
        elif r_pub_sum.status_code == 406 and "PGRST106" in r_pub_sum.text:
            mart_exposed = False
            results.append(
                CheckResult(
                    "rest_anon_mart_public_summary",
                    True,
                    "HTTP 406 PGRST106 (mart not yet added to Dashboard Exposed schemas — expected until T0.2 👤 step)",
                )
            )
        else:
            results.append(
                CheckResult(
                    "rest_anon_mart_public_summary",
                    False,
                    f"Unexpected HTTP {r_pub_sum.status_code}: {r_pub_sum.text[:160]}",
                )
            )

        r_anon_profile = client.get(
            f"{url}/rest/v1/app_profile?select=*&limit=1",
            headers={"apikey": pub},
            timeout=15,
        )
        results.append(
            CheckResult(
                "rest_anon_denied:public.app_profile",
                r_anon_profile.status_code in (401, 403),
                f"HTTP {r_anon_profile.status_code}",
            )
        )

        r_anon_rpc_admin = client.post(
            f"{url}/rest/v1/rpc/get_admin_pipeline_status",
            headers={"apikey": pub},
            json={},
            timeout=15,
        )
        results.append(
            CheckResult(
                "rest_anon_denied:rpc.get_admin_pipeline_status",
                r_anon_rpc_admin.status_code in (401, 403),
                f"HTTP {r_anon_rpc_admin.status_code}",
            )
        )

        r_anon_rpc_skills = client.post(
            f"{url}/rest/v1/rpc/get_dim_skills",
            headers={"apikey": pub},
            json={},
            timeout=15,
        )
        results.append(
            CheckResult(
                "rest_anon_allowed:rpc.get_dim_skills",
                r_anon_rpc_skills.status_code == 200,
                f"HTTP {r_anon_rpc_skills.status_code}",
            )
        )

        # 2. Live Auth + RLS matrix with temporary users
        suffix = uuid.uuid4().hex[:8]
        pw = f"RlsCheck!{suffix}#2026"
        email_a = f"rls-a-{suffix}@example.com"
        email_b = f"rls-b-{suffix}@example.com"
        email_adm = f"rls-adm-{suffix}@example.com"

        try:
            uid_a = _create_temp_user(client, url, sec, email_a, pw, metadata={"role": "admin", "display_name": "Test User A"})
            created_ids.append(uid_a)
            uid_b = _create_temp_user(client, url, sec, email_b, pw, metadata={"role": "institution", "display_name": "Test User B"})
            created_ids.append(uid_b)
            uid_adm = _create_temp_user(client, url, sec, email_adm, pw, metadata={"display_name": "Test Admin"})
            created_ids.append(uid_adm)

            # Promote uid_adm via secret key (service_role)
            r_adm_set = client.patch(
                f"{url}/rest/v1/app_profile?user_id=eq.{uid_adm}",
                headers={"apikey": sec, "Authorization": f"Bearer {sec}", "Prefer": "return=representation"},
                json={"role": "admin"},
                timeout=15,
            )
            results.append(
                CheckResult(
                    "rls_service_role_can_assign_admin",
                    r_adm_set.status_code == 200 and r_adm_set.json()[0]["role"] == "admin",
                    f"HTTP {r_adm_set.status_code}",
                )
            )

            tok_a = _login_user(client, url, pub, email_a, pw)
            tok_b = _login_user(client, url, pub, email_b, pw)
            tok_adm = _login_user(client, url, pub, email_adm, pw)

            hdr_a = {"apikey": pub, "Authorization": f"Bearer {tok_a}"}
            hdr_b = {"apikey": pub, "Authorization": f"Bearer {tok_b}"}
            hdr_adm = {"apikey": pub, "Authorization": f"Bearer {tok_adm}"}

            # Trigger must ignore user_metadata.role = 'admin' and default to 'student'
            r_prof_a = client.get(f"{url}/rest/v1/app_profile?user_id=eq.{uid_a}&select=role,display_name", headers=hdr_a, timeout=15)
            prof_a = r_prof_a.json() if r_prof_a.status_code == 200 else []
            results.append(
                CheckResult(
                    "rls_trigger_ignores_admin_metadata",
                    r_prof_a.status_code == 200 and len(prof_a) == 1 and prof_a[0]["role"] == "student",
                    f"role={prof_a[0]['role'] if prof_a else None}",
                )
            )

            # User A tries UPDATE own role -> 'admin' (must fail 403 / 42501)
            r_esc_upd = client.patch(
                f"{url}/rest/v1/app_profile?user_id=eq.{uid_a}",
                headers={**hdr_a, "Prefer": "return=representation"},
                json={"role": "admin"},
                timeout=15,
            )
            results.append(
                CheckResult(
                    "rls_block_self_update_role_admin",
                    r_esc_upd.status_code == 403,
                    f"HTTP {r_esc_upd.status_code}",
                )
            )

            # User A deletes own profile then tries INSERT with role='admin' (must fail 403 / 42501)
            r_del_a = client.delete(f"{url}/rest/v1/app_profile?user_id=eq.{uid_a}", headers=hdr_a, timeout=15)
            r_esc_ins = client.post(
                f"{url}/rest/v1/app_profile",
                headers={**hdr_a, "Prefer": "return=representation"},
                json={"user_id": uid_a, "role": "admin", "display_name": "Evil"},
                timeout=15,
            )
            results.append(
                CheckResult(
                    "rls_block_self_insert_role_admin",
                    r_del_a.status_code in (200, 204) and r_esc_ins.status_code == 403,
                    f"del={r_del_a.status_code}, insert_admin={r_esc_ins.status_code}",
                )
            )

            # User A inserts valid role='student' profile
            r_reins = client.post(
                f"{url}/rest/v1/app_profile",
                headers={**hdr_a, "Prefer": "return=representation"},
                json={"user_id": uid_a, "role": "student", "display_name": "Valid Student A"},
                timeout=15,
            )
            results.append(
                CheckResult(
                    "rls_allow_self_insert_student",
                    r_reins.status_code == 201,
                    f"HTTP {r_reins.status_code}",
                )
            )

            # User A writes own skill; User B must NOT see User A's skill or profile
            r_sk_a = client.post(
                f"{url}/rest/v1/app_user_skill",
                headers={**hdr_a, "Prefer": "return=representation"},
                json={"user_id": uid_a, "skill_key": 1, "level": 2},
                timeout=15,
            )
            r_b_read_a_skills = client.get(
                f"{url}/rest/v1/app_user_skill?user_id=eq.{uid_a}",
                headers=hdr_b,
                timeout=15,
            )
            r_b_read_a_prof = client.get(
                f"{url}/rest/v1/app_profile?user_id=eq.{uid_a}",
                headers=hdr_b,
                timeout=15,
            )
            r_b_upd_a_prof = client.patch(
                f"{url}/rest/v1/app_profile?user_id=eq.{uid_a}",
                headers={**hdr_b, "Prefer": "return=representation"},
                json={"display_name": "Hacked"},
                timeout=15,
            )
            results.append(
                CheckResult(
                    "rls_isolate_user_a_from_user_b",
                    (
                        r_sk_a.status_code == 201
                        and r_b_read_a_skills.status_code == 200
                        and r_b_read_a_skills.json() == []
                        and r_b_read_a_prof.status_code == 200
                        and r_b_read_a_prof.json() == []
                        and r_b_upd_a_prof.status_code in (200, 403, 404)
                        and (r_b_upd_a_prof.json() == [] if r_b_upd_a_prof.status_code == 200 else True)
                    ),
                    f"sk_a={r_sk_a.status_code}, b_skills={r_b_read_a_skills.json()}, b_prof={r_b_read_a_prof.json()}",
                )
            )

            # Non-admin RPC blocked vs Admin RPC allowed
            r_a_rpc = client.post(f"{url}/rest/v1/rpc/get_admin_pipeline_status", headers=hdr_a, json={}, timeout=15)
            r_a_dq = client.post(f"{url}/rest/v1/rpc/get_admin_dq_summary", headers=hdr_a, json={}, timeout=15)
            r_adm_rpc = client.post(f"{url}/rest/v1/rpc/get_admin_pipeline_status", headers=hdr_adm, json={}, timeout=15)
            r_adm_dq = client.post(f"{url}/rest/v1/rpc/get_admin_dq_summary", headers=hdr_adm, json={}, timeout=15)
            results.append(
                CheckResult(
                    "rls_admin_rpc_denied_for_student",
                    r_a_rpc.status_code == 403 and r_a_dq.status_code == 403,
                    f"pipeline={r_a_rpc.status_code}, dq={r_a_dq.status_code}",
                )
            )
            results.append(
                CheckResult(
                    "rls_admin_rpc_allowed_for_admin",
                    r_adm_rpc.status_code == 200 and r_adm_dq.status_code == 200,
                    f"pipeline={r_adm_rpc.status_code}, dq={r_adm_dq.status_code}",
                )
            )
        finally:
            for uid in created_ids:
                _delete_temp_user(client, url, sec, uid)

    return results, mart_exposed


def run_all_checks() -> int:
    _load_env()
    url, pub, sec, dsn = _get_required_keys()

    pg_results = check_postgres_privileges(dsn)
    rest_results, mart_exposed = check_rest_and_rls(url, pub, sec)
    all_results = pg_results + rest_results

    failed = [r for r in all_results if not r.passed]
    for r in all_results:
        icon = "PASS" if r.passed else "FAIL"
        print(f"[{icon}] {r.name}: {r.detail}")

    print(f"\nSummary: {len(all_results) - len(failed)}/{len(all_results)} passed | mart_exposed_in_rest={mart_exposed}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(run_all_checks())
