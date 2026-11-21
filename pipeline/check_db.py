"""T0.2 — สคริปต์ตรวจสอบการเชื่อมต่อฐานข้อมูล PostgreSQL (Supabase) และความพร้อมของ Schema

วิธีใช้:
    .\\venv\\Scripts\\python.exe -I -X utf8 pipeline/check_db.py
    หรือ:
    py -I -X utf8 pipeline/check_db.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

REQUIRED_SCHEMAS = ("staging", "dw", "mart", "ml", "public")
EXPECTED_LOCATION_MIN_ROWS = 79  # 77 จังหวัด + 'หลายจังหวัด' + 'ต่างประเทศ'
EXPECTED_DATE_MIN_ROWS = 1095    # 2025-01-01 ถึง 2027-12-31


def _load_env() -> Path | None:
    """โหลดค่าสภาพแวดล้อมจาก .env ในโฟลเดอร์รากหรือ pipeline/.env ถ้ามี"""
    repo_root = Path(__file__).resolve().parent.parent
    for candidate in (repo_root / ".env", repo_root / "pipeline" / ".env", repo_root / ".env.local"):
        if candidate.exists():
            load_dotenv(dotenv_path=candidate, override=False)
            return candidate
    load_dotenv(override=False)
    return None


def _is_placeholder_url(url: str) -> bool:
    placeholders = ("your-project-id", "your-password", "<project-id>", "<password>")
    lowered = url.lower()
    return any(p in lowered for p in placeholders)


def _mask_dsn(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.hostname or "?"
    port = parsed.port or 5432
    db = parsed.path.lstrip("/") or "postgres"
    user = parsed.username or "?"
    return f"{parsed.scheme}://{user}:***@{host}:{port}/{db}"


def check_database() -> int:
    env_file = _load_env()
    database_url = os.environ.get("DATABASE_URL", "").strip()

    if not database_url or _is_placeholder_url(database_url):
        print("❌ ยังไม่ได้ตั้งค่า DATABASE_URL (หรือยังเป็นค่าตัวอย่างจาก .env.example)")
        if env_file:
            print(f"   พบไฟล์ env ที่: {env_file}")
        print("\nขั้นตอนแก้ไข (T0.2):")
        print("  1. สร้างโปรเจกต์บน Supabase (https://supabase.com)")
        print("  2. คัดลอกไฟล์แม่แบบ: Copy-Item .env.example .env")
        print("  3. นำ Connection String จาก Supabase → Project Settings → Database → URI")
        print("     มาใส่ในตัวแปร DATABASE_URL=... ในไฟล์ .env")
        print("  4. รันไฟล์ SQL migrations ในโฟลเดอร์ supabase/migrations/ (001 ถึง 005)")
        print("  5. รันคำสั่งนี้อีกครั้งเพื่อตรวจสอบความพร้อม")
        return 1

    try:
        import psycopg
    except ImportError:
        print("❌ ไม่พบไลบรารี psycopg กรุณาติดตั้งด้วย:")
        print("   .\\.venv\\Scripts\\python.exe -m pip install -r pipeline/requirements.txt")
        return 1

    print(f"🔌 กำลังเชื่อมต่อฐานข้อมูล: {_mask_dsn(database_url)}")

    try:
        with psycopg.connect(database_url, connect_timeout=10) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                version_row = cur.fetchone()
                version_str = version_row[0].split(",")[0] if version_row else "PostgreSQL"
                print(f"✅ เชื่อมต่อสำเร็จ ({version_str})")

                # 1. ตรวจสอบ schemas ทั้ง 5 ตัว
                cur.execute(
                    "SELECT schema_name FROM information_schema.schemata WHERE schema_name = ANY(%s);",
                    (list(REQUIRED_SCHEMAS),),
                )
                found_schemas = {row[0] for row in cur.fetchall()}
                missing_schemas = [s for s in REQUIRED_SCHEMAS if s not in found_schemas]
                if missing_schemas:
                    print(f"❌ ขาด schema: {', '.join(missing_schemas)} (กรุณารัน migration 001_schemas_and_staging.sql)")
                else:
                    print(f"✅ พบ schema ครบทั้ง 5 ตัว: {', '.join(REQUIRED_SCHEMAS)}")

                # 2. ตรวจสอบ extension pg_trgm
                cur.execute("SELECT extversion FROM pg_extension WHERE extname = 'pg_trgm';")
                trgm_row = cur.fetchone()
                if trgm_row:
                    print(f"✅ เปิดใช้งาน extension pg_trgm แล้ว (v{trgm_row[0]})")
                else:
                    print("❌ ยังไม่ได้เปิด extension pg_trgm (กรุณารัน migration 001_schemas_and_staging.sql)")

                # 3. ตรวจสอบตารางและการ seed ข้อมูลตั้งต้น (dim_location, dim_date)
                seed_checks = [
                    ("dw.dim_location", EXPECTED_LOCATION_MIN_ROWS, "002_dw_dimensions_and_seed.sql"),
                    ("dw.dim_date", EXPECTED_DATE_MIN_ROWS, "002_dw_dimensions_and_seed.sql"),
                    ("dw.dim_source", 2, "002_dw_dimensions_and_seed.sql"),
                    ("dw.dim_education", 5, "002_dw_dimensions_and_seed.sql"),
                    ("dw.dim_experience", 5, "002_dw_dimensions_and_seed.sql"),
                ]
                seed_ok = True
                for table_name, min_rows, migration_hint in seed_checks:
                    cur.execute("SELECT to_regclass(%s);", (table_name,))
                    exists = cur.fetchone()[0]
                    if not exists:
                        print(f"❌ ยังไม่พบตาราง {table_name} (รัน {migration_hint})")
                        seed_ok = False
                        continue
                    cur.execute(f"SELECT COUNT(*) FROM {table_name};")
                    count = cur.fetchone()[0]
                    if count >= min_rows:
                        print(f"✅ {table_name}: {count:,} แถว (เกณฑ์ >= {min_rows:,})")
                    else:
                        print(f"⚠️  {table_name}: {count:,} แถว (คาดหวัง >= {min_rows:,} จาก {migration_hint})")
                        seed_ok = False

                # 4. ตรวจสอบตาราง staging/fact/app เบื้องต้น (แจ้งเตือนถ้ายังไม่รัน migration ถัดไป)
                optional_tables = [
                    "staging.scrape_run",
                    "staging.listing_seen",
                    "staging.job_posting_raw",
                    "dw.fact_job_posting",
                    "mart.public_summary",
                    "public.app_profile",
                ]
                missing_tables = []
                for tbl in optional_tables:
                    cur.execute("SELECT to_regclass(%s);", (tbl,))
                    if cur.fetchone()[0] is None:
                        missing_tables.append(tbl)
                if missing_tables:
                    print(f"ℹ️  ตารางที่ยังไม่ได้สร้าง: {', '.join(missing_tables)} (รัน migrations 001–005 ให้ครบ)")
                else:
                    print("✅ พบตารางหลักใน staging / dw / mart / public ครบถ้วน")

                if missing_schemas or not trgm_row or not seed_ok:
                    print("\n⚠️  การเชื่อมต่อผ่าน แต่โครงสร้างฐานข้อมูลยังไม่ครบ กรุณารันไฟล์ใน supabase/migrations/ ตามลำดับ 001 -> 005")
                    return 2

                print("\n🎉 ฐานข้อมูลพร้อมใช้งานสำหรับ Pipeline และ Web App แล้ว")
                return 0

    except psycopg.Error as exc:
        print(f"❌ ไม่สามารถเชื่อมต่อฐานข้อมูลได้: {exc}")
        print("   ตรวจสอบว่า: 1) รหัสผ่านใน DATABASE_URL ถูกต้อง  2) โปรเจกต์ Supabase ไม่ได้ pause  3) เครือข่ายอนุญาตพอร์ต 5432/6543")
        return 1


if __name__ == "__main__":
    sys.exit(check_database())
