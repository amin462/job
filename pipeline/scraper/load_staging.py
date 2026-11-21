"""Staging loader and dual Postgres/SQLite storage layer (T1.5).

Loads parsed JobPosting records into `staging.job_posting_raw` with strict
deduplication on `(source, source_job_id, content_hash)` and zero HR contact PII.
Supports Supabase/Postgres via `DATABASE_URL` as well as offline SQLite/JSONL.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from pipeline.scraper.config import validate_source
from pipeline.scraper.parse import HR_CONTACT_KEYS, parse_file

_SQLITE_DDL = """
CREATE TABLE IF NOT EXISTS scrape_run (
    scrape_run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source        TEXT NOT NULL CHECK (source IN ('jobthai', 'jobbkk')),
    scope         TEXT,
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    status        TEXT CHECK (status IN ('running', 'done', 'stopped_403', 'stopped_429', 'stopped_captcha', 'error')),
    n_discovered  INTEGER DEFAULT 0,
    n_fetched     INTEGER DEFAULT 0,
    n_failed      INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS listing_seen (
    scrape_run_id INTEGER NOT NULL REFERENCES scrape_run (scrape_run_id) ON DELETE CASCADE,
    source        TEXT NOT NULL CHECK (source IN ('jobthai', 'jobbkk')),
    source_job_id TEXT NOT NULL,
    stratum       TEXT NOT NULL,
    seen_date     TEXT NOT NULL,
    PRIMARY KEY (scrape_run_id, source, source_job_id)
);

CREATE INDEX IF NOT EXISTS idx_listing_seen_job
    ON listing_seen (source, source_job_id, seen_date);

CREATE TABLE IF NOT EXISTS job_posting_raw (
    raw_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    scrape_run_id   INTEGER REFERENCES scrape_run (scrape_run_id) ON DELETE SET NULL,
    source          TEXT NOT NULL CHECK (source IN ('jobthai', 'jobbkk')),
    source_job_id   TEXT NOT NULL,
    source_url      TEXT NOT NULL,
    title           TEXT,
    description     TEXT,
    qualifications  TEXT,
    salary_text     TEXT,
    salary_min      REAL,
    salary_max      REAL,
    province        TEXT,
    district        TEXT,
    job_category    TEXT,
    industry        TEXT,
    employment_type TEXT,
    date_posted     TEXT,
    valid_through   TEXT,
    company_name    TEXT,
    payload         TEXT,
    content_hash    TEXT NOT NULL,
    scraped_at      TEXT NOT NULL,
    UNIQUE (source, source_job_id, content_hash)
);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_usable_database_url(url: str | None) -> bool:
    if not url:
        return False
    lowered = url.strip().lower()
    if not lowered.startswith(("postgres://", "postgresql://")):
        return False
    if "your-project-id" in lowered or "your-password" in lowered:
        return False
    return True


def _assert_no_hr_keys(obj: Any) -> None:
    """Fail-closed check ensuring no HR contact keys survive before staging write."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).strip().lower() in HR_CONTACT_KEYS:
                raise ValueError(f"Refusing to stage record containing HR contact key: {k!r}")
            _assert_no_hr_keys(v)
    elif isinstance(obj, list):
        for item in obj:
            _assert_no_hr_keys(item)


class StagingStore:
    """Unified staging persistence supporting Postgres (`DATABASE_URL`) and local SQLite."""

    def __init__(
        self,
        *,
        database_url: str | None = None,
        sqlite_path: str | Path | None = None,
    ) -> None:
        self.backend: str
        self._pg_conn: Any = None
        self._sqlite_conn: sqlite3.Connection | None = None

        if sqlite_path is not None:
            self.backend = "sqlite"
            db_str = str(sqlite_path)
            if db_str != ":memory:":
                Path(db_str).parent.mkdir(parents=True, exist_ok=True)
            self._sqlite_conn = sqlite3.connect(db_str)
            self._sqlite_conn.row_factory = sqlite3.Row
            self._sqlite_conn.execute("PRAGMA foreign_keys = ON;")
            self._sqlite_conn.executescript(_SQLITE_DDL)
            self._sqlite_conn.commit()
            return

        resolved_pg = database_url if database_url is not None else os.getenv("DATABASE_URL")
        if _is_usable_database_url(resolved_pg):
            import psycopg

            self.backend = "postgres"
            self._pg_conn = psycopg.connect(resolved_pg)
            return

        default_sqlite = Path("data/processed/staging.db")
        default_sqlite.parent.mkdir(parents=True, exist_ok=True)
        self.backend = "sqlite"
        self._sqlite_conn = sqlite3.connect(str(default_sqlite))
        self._sqlite_conn.row_factory = sqlite3.Row
        self._sqlite_conn.execute("PRAGMA foreign_keys = ON;")
        self._sqlite_conn.executescript(_SQLITE_DDL)
        self._sqlite_conn.commit()

    def __enter__(self) -> StagingStore:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    def close(self) -> None:
        if self._sqlite_conn is not None:
            self._sqlite_conn.close()
            self._sqlite_conn = None
        if self._pg_conn is not None:
            self._pg_conn.close()
            self._pg_conn = None

    def create_scrape_run(self, source: str, scope: str = "") -> int:
        source_norm = validate_source(source)
        if self.backend == "postgres":
            with self._pg_conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO staging.scrape_run (source, scope, status)
                    VALUES (%s, %s, 'running')
                    RETURNING scrape_run_id
                    """,
                    (source_norm, scope),
                )
                run_id = int(cur.fetchone()[0])
            self._pg_conn.commit()
            return run_id

        assert self._sqlite_conn is not None
        cur = self._sqlite_conn.execute(
            """
            INSERT INTO scrape_run (source, scope, started_at, status)
            VALUES (?, ?, ?, 'running')
            """,
            (source_norm, scope, _now_iso()),
        )
        self._sqlite_conn.commit()
        return int(cur.lastrowid)

    def find_scrape_run(self, source: str, scope: str) -> int | None:
        """Return the newest scrape_run_id with this source+scope, or None."""
        source_norm = validate_source(source)
        if self.backend == "postgres":
            with self._pg_conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT scrape_run_id FROM staging.scrape_run
                    WHERE source = %s AND scope = %s
                    ORDER BY scrape_run_id DESC LIMIT 1
                    """,
                    (source_norm, scope),
                )
                row = cur.fetchone()
            return int(row[0]) if row else None

        assert self._sqlite_conn is not None
        row = self._sqlite_conn.execute(
            """
            SELECT scrape_run_id FROM scrape_run
            WHERE source = ? AND scope = ?
            ORDER BY scrape_run_id DESC LIMIT 1
            """,
            (source_norm, scope),
        ).fetchone()
        return int(row[0]) if row else None

    def get_or_create_scrape_run(self, source: str, scope: str) -> int:
        """Reuse the run with this source+scope so re-imports stay idempotent."""
        found = self.find_scrape_run(source, scope)
        if found is not None:
            return found
        return self.create_scrape_run(source, scope=scope)

    def update_scrape_run(
        self,
        scrape_run_id: int,
        *,
        status: str | None = None,
        n_discovered: int | None = None,
        n_fetched: int | None = None,
        n_failed: int | None = None,
        finished: bool = False,
    ) -> None:
        fields: list[str] = []
        values: list[Any] = []
        if status is not None:
            fields.append("status")
            values.append(status)
        if n_discovered is not None:
            fields.append("n_discovered")
            values.append(int(n_discovered))
        if n_fetched is not None:
            fields.append("n_fetched")
            values.append(int(n_fetched))
        if n_failed is not None:
            fields.append("n_failed")
            values.append(int(n_failed))
        if finished:
            fields.append("finished_at")
            values.append(_now_iso())

        if not fields:
            return

        if self.backend == "postgres":
            set_sql = ", ".join(f"{f} = %s" for f in fields)
            values.append(scrape_run_id)
            with self._pg_conn.cursor() as cur:
                cur.execute(
                    f"UPDATE staging.scrape_run SET {set_sql} WHERE scrape_run_id = %s",
                    tuple(values),
                )
            self._pg_conn.commit()
            return

        assert self._sqlite_conn is not None
        set_sql = ", ".join(f"{f} = ?" for f in fields)
        values.append(scrape_run_id)
        self._sqlite_conn.execute(
            f"UPDATE scrape_run SET {set_sql} WHERE scrape_run_id = ?",
            tuple(values),
        )
        self._sqlite_conn.commit()

    def get_scrape_run(self, scrape_run_id: int) -> dict[str, Any] | None:
        if self.backend == "postgres":
            with self._pg_conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT scrape_run_id, source, scope, started_at, finished_at,
                           status, n_discovered, n_fetched, n_failed
                    FROM staging.scrape_run
                    WHERE scrape_run_id = %s
                    """,
                    (scrape_run_id,),
                )
                row = cur.fetchone()
            if not row:
                return None
            cols = [
                "scrape_run_id",
                "source",
                "scope",
                "started_at",
                "finished_at",
                "status",
                "n_discovered",
                "n_fetched",
                "n_failed",
            ]
            return dict(zip(cols, row))

        assert self._sqlite_conn is not None
        row = self._sqlite_conn.execute(
            "SELECT * FROM scrape_run WHERE scrape_run_id = ?",
            (scrape_run_id,),
        ).fetchone()
        return dict(row) if row else None

    def insert_listing_seen(
        self,
        scrape_run_id: int,
        records: Sequence[dict[str, Any]],
        *,
        update_existing: bool = False,
    ) -> int:
        """Insert listing sightings; returns the number of new rows.

        With `update_existing=True` a row already in this run gets the new
        `seen_date`/`stratum` (used by import_sqlite to move `last_seen` forward).
        """
        if not records:
            return 0
        rows_to_insert = []
        for r in records:
            src = validate_source(str(r["source"]))
            rows_to_insert.append(
                (
                    int(scrape_run_id),
                    src,
                    str(r["source_job_id"]),
                    str(r["stratum"]),
                    str(r["seen_date"]),
                )
            )

        on_conflict = (
            "DO UPDATE SET seen_date = excluded.seen_date, stratum = excluded.stratum"
            if update_existing
            else "DO NOTHING"
        )

        if self.backend == "postgres":
            with self._pg_conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM staging.listing_seen WHERE scrape_run_id = %s",
                    (int(scrape_run_id),),
                )
                before_pg = int(cur.fetchone()[0])
                cur.executemany(
                    f"""
                    INSERT INTO staging.listing_seen
                        (scrape_run_id, source, source_job_id, stratum, seen_date)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (scrape_run_id, source, source_job_id) {on_conflict}
                    """,
                    rows_to_insert,
                )
                cur.execute(
                    "SELECT COUNT(*) FROM staging.listing_seen WHERE scrape_run_id = %s",
                    (int(scrape_run_id),),
                )
                after_pg = int(cur.fetchone()[0])
            self._pg_conn.commit()
            return after_pg - before_pg

        assert self._sqlite_conn is not None
        before = self._sqlite_conn.execute("SELECT COUNT(*) FROM listing_seen").fetchone()[0]
        self._sqlite_conn.executemany(
            f"""
            INSERT INTO listing_seen
                (scrape_run_id, source, source_job_id, stratum, seen_date)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (scrape_run_id, source, source_job_id) {on_conflict}
            """,
            rows_to_insert,
        )
        self._sqlite_conn.commit()
        after = self._sqlite_conn.execute("SELECT COUNT(*) FROM listing_seen").fetchone()[0]
        return int(after - before)

    def get_listing_seen_summary(
        self, source: str = "jobthai"
    ) -> dict[str, dict[str, Any]]:
        source_norm = validate_source(source)
        sql_body = """
            SELECT source_job_id,
                   MIN(seen_date) AS first_seen,
                   MAX(seen_date) AS last_seen,
                   MAX(stratum) AS stratum,
                   COUNT(*) AS n_seen_runs
            FROM {table}
            WHERE source = {ph}
            GROUP BY source_job_id
        """
        if self.backend == "postgres":
            with self._pg_conn.cursor() as cur:
                cur.execute(
                    sql_body.format(table="staging.listing_seen", ph="%s"),
                    (source_norm,),
                )
                rows = cur.fetchall()
            return {
                str(r[0]): {
                    "first_seen": str(r[1]),
                    "last_seen": str(r[2]),
                    "stratum": str(r[3]),
                    "n_seen_runs": int(r[4]),
                }
                for r in rows
            }

        assert self._sqlite_conn is not None
        rows = self._sqlite_conn.execute(
            sql_body.format(table="listing_seen", ph="?"),
            (source_norm,),
        ).fetchall()
        return {
            str(r["source_job_id"]): {
                "first_seen": str(r["first_seen"]),
                "last_seen": str(r["last_seen"]),
                "stratum": str(r["stratum"]),
                "n_seen_runs": int(r["n_seen_runs"]),
            }
            for r in rows
        }

    def get_known_job_ids(self, source: str = "jobthai") -> set[str]:
        source_norm = validate_source(source)
        if self.backend == "postgres":
            with self._pg_conn.cursor() as cur:
                cur.execute(
                    "SELECT DISTINCT source_job_id FROM staging.job_posting_raw WHERE source = %s",
                    (source_norm,),
                )
                return {str(r[0]) for r in cur.fetchall()}

        assert self._sqlite_conn is not None
        rows = self._sqlite_conn.execute(
            "SELECT DISTINCT source_job_id FROM job_posting_raw WHERE source = ?",
            (source_norm,),
        ).fetchall()
        return {str(r["source_job_id"]) for r in rows}

    def upsert_job_postings(
        self,
        records: Sequence[dict[str, Any]],
        scrape_run_id: int | None = None,
    ) -> dict[str, int]:
        if not records:
            return {
                "inserted": 0,
                "duplicates": 0,
                "total_rows": self.count_job_postings(),
            }

        prepared: list[tuple[Any, ...]] = []
        now_ts = _now_iso()
        for rec in records:
            src = validate_source(str(rec["source"]))
            _assert_no_hr_keys(rec)
            payload_json = json.dumps(rec.get("payload"), ensure_ascii=False)
            prepared.append(
                (
                    scrape_run_id,
                    src,
                    str(rec["source_job_id"]),
                    str(rec["source_url"]),
                    rec.get("title"),
                    rec.get("description"),
                    rec.get("qualifications"),
                    rec.get("salary_text"),
                    rec.get("salary_min"),
                    rec.get("salary_max"),
                    rec.get("province"),
                    rec.get("district"),
                    rec.get("job_category"),
                    rec.get("industry"),
                    rec.get("employment_type"),
                    rec.get("date_posted"),
                    rec.get("valid_through"),
                    rec.get("company_name"),
                    payload_json,
                    str(rec["content_hash"]),
                    now_ts,
                )
            )

        if self.backend == "postgres":
            inserted = 0
            with self._pg_conn.cursor() as cur:
                for row in prepared:
                    cur.execute(
                        """
                        INSERT INTO staging.job_posting_raw (
                            scrape_run_id, source, source_job_id, source_url,
                            title, description, qualifications, salary_text,
                            salary_min, salary_max, province, district,
                            job_category, industry, employment_type,
                            date_posted, valid_through, company_name,
                            payload, content_hash, scraped_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s
                        )
                        ON CONFLICT (source, source_job_id, content_hash) DO NOTHING
                        """,
                        row,
                    )
                    inserted += cur.rowcount
            self._pg_conn.commit()
            return {
                "inserted": inserted,
                "duplicates": len(prepared) - inserted,
                "total_rows": self.count_job_postings(),
            }

        assert self._sqlite_conn is not None
        before = self.count_job_postings()
        self._sqlite_conn.executemany(
            """
            INSERT OR IGNORE INTO job_posting_raw (
                scrape_run_id, source, source_job_id, source_url,
                title, description, qualifications, salary_text,
                salary_min, salary_max, province, district,
                job_category, industry, employment_type,
                date_posted, valid_through, company_name,
                payload, content_hash, scraped_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            prepared,
        )
        self._sqlite_conn.commit()
        after = self.count_job_postings()
        inserted = after - before
        return {
            "inserted": inserted,
            "duplicates": len(prepared) - inserted,
            "total_rows": after,
        }

    def count_job_postings(self, source: str | None = None) -> int:
        if source is not None:
            source_norm = validate_source(source)
            if self.backend == "postgres":
                with self._pg_conn.cursor() as cur:
                    cur.execute(
                        "SELECT COUNT(*) FROM staging.job_posting_raw WHERE source = %s",
                        (source_norm,),
                    )
                    return int(cur.fetchone()[0])
            assert self._sqlite_conn is not None
            return int(
                self._sqlite_conn.execute(
                    "SELECT COUNT(*) FROM job_posting_raw WHERE source = ?",
                    (source_norm,),
                ).fetchone()[0]
            )

        if self.backend == "postgres":
            with self._pg_conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM staging.job_posting_raw")
                return int(cur.fetchone()[0])
        assert self._sqlite_conn is not None
        return int(
            self._sqlite_conn.execute("SELECT COUNT(*) FROM job_posting_raw").fetchone()[0]
        )


def write_clean_jsonl(
    records: Sequence[dict[str, Any]],
    out_path: str | Path,
) -> int:
    """Write deduplicated PDPA-clean staging records to a JSONL file."""
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    seen: set[tuple[str, str, str]] = set()
    unique_records: list[dict[str, Any]] = []
    for rec in records:
        _assert_no_hr_keys(rec)
        key = (str(rec["source"]), str(rec["source_job_id"]), str(rec["content_hash"]))
        if key not in seen:
            seen.add(key)
            unique_records.append(rec)

    with path.open("w", encoding="utf-8") as fh:
        for rec in unique_records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return len(unique_records)


def load_raw_directory(
    raw_dirs: str | Path | Sequence[str | Path],
    *,
    store: StagingStore | None = None,
    source: str = "jobthai",
    scrape_run_id: int | None = None,
    jsonl_out: str | Path | None = None,
    pattern: str = "job_*.html",
) -> dict[str, Any]:
    """Parse raw HTML files in `raw_dirs` and load into `staging.job_posting_raw`."""
    source_norm = validate_source(source)
    if isinstance(raw_dirs, (str, Path)):
        dir_list = [Path(raw_dirs)]
    else:
        dir_list = [Path(d) for d in raw_dirs]

    html_files: list[Path] = []
    for d in dir_list:
        if d.is_dir():
            html_files.extend(sorted(d.glob(pattern)))

    parsed_records: list[dict[str, Any]] = []
    n_failed = 0
    for fpath in html_files:
        rec = parse_file(fpath, source=source_norm)
        if rec is None:
            n_failed += 1
        else:
            parsed_records.append(rec)

    own_store = store is None
    active_store = store or StagingStore()
    try:
        active_run_id = scrape_run_id
        if active_run_id is None:
            active_run_id = active_store.create_scrape_run(
                source_norm, scope="load_raw_directory"
            )
        upsert_stats = active_store.upsert_job_postings(
            parsed_records, scrape_run_id=active_run_id
        )
        active_store.update_scrape_run(
            active_run_id,
            status="done",
            n_discovered=len(html_files),
            n_fetched=len(parsed_records),
            n_failed=n_failed,
            finished=True,
        )
    finally:
        if own_store:
            active_store.close()

    jsonl_count = None
    if jsonl_out is not None:
        jsonl_count = write_clean_jsonl(parsed_records, jsonl_out)

    return {
        "source": source_norm,
        "scrape_run_id": active_run_id,
        "files_scanned": len(html_files),
        "parsed": len(parsed_records),
        "failed": n_failed,
        "inserted": upsert_stats["inserted"],
        "duplicates": upsert_stats["duplicates"],
        "total_rows": upsert_stats["total_rows"],
        "jsonl_written": jsonl_count,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Load raw JobThai HTML directory into staging.job_posting_raw."
    )
    parser.add_argument("--raw-dirs", nargs="+", required=True, help="Raw HTML directories")
    parser.add_argument("--source", default="jobthai", help="Source name (jobthai|jobbkk)")
    parser.add_argument("--sqlite-path", default=None, help="Optional SQLite DB path")
    parser.add_argument("--jsonl-out", default=None, help="Optional clean JSONL output path")
    args = parser.parse_args(argv)

    store = StagingStore(sqlite_path=args.sqlite_path) if args.sqlite_path else StagingStore()
    try:
        result = load_raw_directory(
            args.raw_dirs,
            store=store,
            source=args.source,
            jsonl_out=args.jsonl_out,
        )
    finally:
        store.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
