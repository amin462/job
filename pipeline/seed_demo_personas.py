"""Idempotently seed and verify the 4 Demo Persona accounts in Supabase Auth (T6.2, T6.3).

Reads `DEMO_*_EMAIL` and `DEMO_*_PASSWORD` from `.env`, creates or updates
the 4 Auth accounts via Supabase Admin API (`SUPABASE_SECRET_KEY`), invokes
`public.attach_demo_persona` (`service_role` only) to populate `app_profile`,
`app_user_skill`, and `app_curriculum` / `app_curriculum_skill`, and verifies
password sign-in + RLS-scoped profile reads for every persona.

NEVER prints passwords, emails, or API keys.

Usage:
    .venv\\Scripts\\python.exe -X utf8 -m pipeline.seed_demo_personas
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent

PERSONA_SPECS: tuple[tuple[str, str, str, str], ...] = (
    ("student_data", "DEMO_STUDENT_DATA_EMAIL", "DEMO_STUDENT_DATA_PASSWORD", "student"),
    ("student_acc", "DEMO_STUDENT_ACC_EMAIL", "DEMO_STUDENT_ACC_PASSWORD", "student"),
    ("institution", "DEMO_INSTITUTION_EMAIL", "DEMO_INSTITUTION_PASSWORD", "institution"),
    ("admin", "DEMO_ADMIN_EMAIL", "DEMO_ADMIN_PASSWORD", "admin"),
)


def _load_env() -> None:
    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)


def _get_supabase_config() -> tuple[str, str, str]:
    url = (os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL") or "").strip().rstrip("/")
    pub = (os.getenv("SUPABASE_PUBLISHABLE_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY") or "").strip()
    sec = (os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not url or not pub or not sec:
        raise RuntimeError("Missing Supabase URL / publishable key / secret key in environment.")
    return url, pub, sec


def _list_auth_users_by_email(client: httpx.Client, url: str, sec: str) -> dict[str, str]:
    users_by_email: dict[str, str] = {}
    page = 1
    while True:
        resp = client.get(
            f"{url}/auth/v1/admin/users",
            headers={"apikey": sec, "Authorization": f"Bearer {sec}"},
            params={"page": page, "per_page": 200},
            timeout=15,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Failed listing auth users: HTTP {resp.status_code}")
        users = resp.json().get("users") or []
        if not users:
            break
        for u in users:
            email = str(u.get("email") or "").strip().lower()
            if email:
                users_by_email[email] = str(u["id"])
        if len(users) < 200:
            break
        page += 1
    return users_by_email


def _ensure_auth_user(
    client: httpx.Client,
    url: str,
    sec: str,
    existing_by_email: dict[str, str],
    email: str,
    password: str,
) -> tuple[str, str]:
    key = email.strip().lower()
    if key in existing_by_email:
        uid = existing_by_email[key]
        resp = client.put(
            f"{url}/auth/v1/admin/users/{uid}",
            headers={"apikey": sec, "Authorization": f"Bearer {sec}"},
            json={"password": password, "email_confirm": True},
            timeout=15,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Failed updating demo auth user: HTTP {resp.status_code}")
        return uid, "updated"

    resp = client.post(
        f"{url}/auth/v1/admin/users",
        headers={"apikey": sec, "Authorization": f"Bearer {sec}"},
        json={"email": email, "password": password, "email_confirm": True},
        timeout=15,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Failed creating demo auth user: HTTP {resp.status_code}")
    uid = str(resp.json()["id"])
    existing_by_email[key] = uid
    return uid, "created"


def _attach_persona(client: httpx.Client, url: str, sec: str, user_id: str, persona: str) -> dict[str, Any]:
    resp = client.post(
        f"{url}/rest/v1/rpc/attach_demo_persona",
        headers={"apikey": sec, "Authorization": f"Bearer {sec}"},
        json={"p_user_id": user_id, "p_persona": persona},
        timeout=15,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"attach_demo_persona failed for {persona}: HTTP {resp.status_code} {resp.text[:160]}")
    return resp.json()


def _verify_persona_login(
    client: httpx.Client,
    url: str,
    pub: str,
    user_id: str,
    email: str,
    password: str,
    expected_role: str,
) -> dict[str, Any]:
    r_login = client.post(
        f"{url}/auth/v1/token?grant_type=password",
        headers={"apikey": pub},
        json={"email": email, "password": password},
        timeout=15,
    )
    if r_login.status_code != 200 or "access_token" not in r_login.json():
        raise RuntimeError(f"Demo login verification failed: HTTP {r_login.status_code}")
    tok = r_login.json()["access_token"]
    hdr = {"apikey": pub, "Authorization": f"Bearer {tok}"}

    r_prof = client.get(
        f"{url}/rest/v1/app_profile?user_id=eq.{user_id}&select=role,display_name,province_th,target_occupation_cluster",
        headers=hdr,
        timeout=15,
    )
    if r_prof.status_code != 200 or not r_prof.json():
        raise RuntimeError(f"Failed reading app_profile after login: HTTP {r_prof.status_code}")
    prof = r_prof.json()[0]
    if prof["role"] != expected_role:
        raise RuntimeError(f"Expected role={expected_role}, got {prof['role']}")

    r_sk = client.get(
        f"{url}/rest/v1/app_user_skill?user_id=eq.{user_id}&select=skill_key,level",
        headers=hdr,
        timeout=15,
    )
    r_cur = client.get(
        f"{url}/rest/v1/app_curriculum?owner_id=eq.{user_id}&select=curriculum_id,name",
        headers=hdr,
        timeout=15,
    )
    return {
        "role": prof["role"],
        "display_name": prof["display_name"],
        "n_skills": len(r_sk.json()) if r_sk.status_code == 200 else 0,
        "n_curricula": len(r_cur.json()) if r_cur.status_code == 200 else 0,
    }


def seed_all_demo_personas() -> int:
    _load_env()
    url, pub, sec = _get_supabase_config()

    creds: list[tuple[str, str, str, str]] = []
    for persona, email_var, pw_var, expected_role in PERSONA_SPECS:
        email = (os.getenv(email_var) or "").strip()
        password = (os.getenv(pw_var) or "").strip()
        if not email or not password or password == "change-me":
            raise RuntimeError(f"Missing or placeholder credential in {email_var}/{pw_var}")
        creds.append((persona, email, password, expected_role))

    with httpx.Client() as client:
        existing = _list_auth_users_by_email(client, url, sec)
        for persona, email, password, expected_role in creds:
            uid, action = _ensure_auth_user(client, url, sec, existing, email, password)
            _attach_persona(client, url, sec, uid, persona)
            verified = _verify_persona_login(client, url, pub, uid, email, password, expected_role)
            print(
                f"[OK] persona={persona} action={action} role={verified['role']} "
                f"n_skills={verified['n_skills']} n_curricula={verified['n_curricula']}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(seed_all_demo_personas())
