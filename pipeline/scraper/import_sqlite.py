"""Import the harvester SQLite files (scraper/) into staging (listing_seen + job_posting_raw).

The harvesters in `scraper/` (jobthai_harvester.py, jobbkk_harvester.py) collect
data into `data/jobthai.sqlite` and `data/jobbkk.sqlite`. This module is the
bridge into the planned pipeline (ARCHITECTURE §3.2), so the collected data is
kept and no second scraper is needed:

  harvester `job` row                    -> staging target
  ------------------------------------------------------------------------------
  first_seen / last_seen / seen_in       -> staging.listing_seen (two import runs:
                                            `...:first_seen` and `...:last_seen`, so
                                            MIN/MAX(seen_date) give first/last seen)
  jsonld (status = 'ok')                 -> parse_jobposting_item (strip HR contact,
                                            scrub PII) -> staging.job_posting_raw
                                            (dedupe on content_hash)

It also writes the N_h tables for stratified sampling (T1.7) from the listing
totals the JobThai harvester records: data/processed/jobthai_strata.csv and
data/processed/jobthai_province_totals.csv.

The harvester files are opened read-only, so this can run while they collect.
Re-running is idempotent: the same scrape_run rows are reused, listing_seen rows
are updated in place and unchanged postings are not inserted again.

Usage (Windows):
  py -X utf8 -m pipeline.scraper.import_sqlite
  py -X utf8 -m pipeline.scraper.import_sqlite --sqlite-path data/processed/staging.db
  (with DATABASE_URL set in the environment and no --sqlite-path, it writes to Postgres)
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv

from pipeline.scraper.config import JOBBKK_DETAIL_URL, JOBTHAI_DETAIL_URL
from pipeline.scraper.load_staging import StagingStore
from pipeline.scraper.parse import parse_jobposting_item

BANGKOK = timezone(timedelta(hours=7))
DEFAULT_JOBTHAI_DB = Path("data/jobthai.sqlite")
DEFAULT_JOBBKK_DB = Path("data/jobbkk.sqlite")
DEFAULT_STRATA_DIR = Path("data/processed")
BATCH = 1000

# source -> (key column in the harvester `job` table)
_KEY_COLUMN = {"jobthai": "job_id", "jobbkk": "job_key"}


def to_bangkok_date(ts: str | None) -> str | None:
    """'2026-11-18T18:36:42+00:00' -> '2026-11-19' (dates are kept in Thai time)."""
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return ts[:10] or None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(BANGKOK).date().isoformat()


def jobthai_stratum(seen_in: str | None) -> str:
    """Listing URL -> stratum in the same format as pipeline/scraper/discovery.py.

    ...jobs?province=15&jobtype=14 -> 'p=15|c=14' ; ...jobs?province=01 -> 'p=01'
    """
    if not seen_in:
        return "unknown"
    qs = parse_qs(urlparse(seen_in).query)
    prov = (qs.get("province") or [""])[0]
    jobtype = (qs.get("jobtype") or [""])[0]
    if not prov:
        return "unknown"
    return f"p={prov}|c={jobtype}" if jobtype else f"p={prov}"


def jobbkk_stratum(seen_in: str | None) -> str:
    """Province name the JobBKK harvester walked -> 'jobbkk|p=<province>|c=ทั้งหมด'."""
    prov = (seen_in or "").strip()
    return f"jobbkk|p={prov}|c=ทั้งหมด" if prov else "jobbkk|unknown"


def split_job_key(source: str, key: str) -> tuple[str, str]:
    """Return (source_job_id, source_url) for a harvester key."""
    if source == "jobthai":
        return key, JOBTHAI_DETAIL_URL.format(job_id=key)
    company_id, _, job_id = key.partition("/")
    if not job_id:  # defensive: key without company part
        return company_id, ""
    return job_id, JOBBKK_DETAIL_URL.format(company_id=company_id, job_id=job_id)


def open_readonly(path: Path) -> sqlite3.Connection:
    """Open a harvester DB read-only; waits if the harvester is mid-commit."""
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    con = sqlite3.connect(uri, uri=True, timeout=30)
    con.row_factory = sqlite3.Row
    return con


def _columns(con: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in con.execute(f"PRAGMA table_info({table})")}


def _iter_jobs(con: sqlite3.Connection, source: str) -> Iterator[sqlite3.Row]:
    key = _KEY_COLUMN[source]
    cols = _columns(con, "job")
    # province_id / jobtype_id come from the listing data (added to the JobThai harvester 2026-11-21)
    extra = ", ".join(
        c if c in cols else f"NULL AS {c}" for c in ("province_id", "jobtype_id")
    )
    yield from con.execute(
        f"SELECT {key} AS job_key, first_seen, last_seen, seen_in, status, jsonld, {extra} "
        f"FROM job ORDER BY {key}"
    )


def job_stratum(source: str, row: sqlite3.Row) -> str:
    """Stratum of one job: its own province x job type when known, else where it was seen."""
    if source == "jobthai":
        if row["province_id"] and row["jobtype_id"]:
            return f"p={row['province_id']}|c={row['jobtype_id']}"
        return jobthai_stratum(row["seen_in"])
    return jobbkk_stratum(row["seen_in"])


def export_jobthai_strata(harvester_db: Path, out_dir: Path) -> dict[str, Any]:
    """Write N_h tables from the listing totals the JobThai harvester recorded.

    - jobthai_strata.csv: one row per province x job type listing
      (stratum, N_h = listing total, n_seen = ids found, n_fetched = details fetched)
    - jobthai_province_totals.csv: code, province, total (same format as
      spike/raw/jobthai/by_province/province_totals.csv, read by pipeline/etl/load_dw.py)
    """
    con = open_readonly(harvester_db)
    try:
        if "total" not in _columns(con, "listing"):
            return {"strata": 0, "provinces": 0, "note": "harvester has no listing totals yet"}
        refs: dict[tuple[str, str], str] = {}
        if con.execute("SELECT 1 FROM sqlite_master WHERE name='ref'").fetchone():
            refs = {(r["kind"], r["id"]): r["name"] for r in con.execute("SELECT kind, id, name FROM ref")}
        counts: dict[str, list[int]] = {}
        if {"province_id", "jobtype_id"} <= _columns(con, "job"):
            for r in con.execute(
                "SELECT province_id, jobtype_id, COUNT(*) AS n, SUM(status='ok') AS ok FROM job "
                "WHERE province_id IS NOT NULL AND jobtype_id IS NOT NULL GROUP BY 1, 2"
            ):
                counts[f"p={r['province_id']}|c={r['jobtype_id']}"] = [r["n"], r["ok"] or 0]

        strata, provinces = [], []
        missing = {"strata": 0, "provinces": 0}
        for r in con.execute("SELECT url, total, last_scanned FROM listing"):
            qs = parse_qs(urlparse(r["url"]).query)
            prov = (qs.get("province") or [""])[0]
            jt = (qs.get("jobtype") or [""])[0]
            if not prov:
                continue
            if r["total"] is None:  # not rescanned since totals were added
                missing["strata" if jt else "provinces"] += 1
                continue
            scanned = to_bangkok_date(r["last_scanned"])
            if jt:
                st = f"p={prov}|c={jt}"
                n_seen, n_ok = counts.get(st, [0, 0])
                strata.append({
                    "stratum": st, "province_code": prov, "province": refs.get(("province", prov), ""),
                    "jobtype_code": jt, "jobtype": refs.get(("jobtype", jt), ""),
                    "N_h": r["total"], "scanned_date": scanned, "n_seen": n_seen, "n_fetched": n_ok,
                })
            else:
                provinces.append({"code": prov, "province": refs.get(("province", prov), ""),
                                  "total": r["total"], "scanned_date": scanned})
    finally:
        con.close()

    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = [
        ("jobthai_strata.csv", sorted(strata, key=lambda x: x["stratum"]),
         ["stratum", "province_code", "province", "jobtype_code", "jobtype", "N_h", "scanned_date", "n_seen", "n_fetched"]),
    ]
    # load_dw.py uses the province file as soon as it exists, so only write it once
    # every province listing has a total; until then the spike file stays in use.
    if provinces and not missing["provinces"]:
        outputs.append(("jobthai_province_totals.csv", sorted(provinces, key=lambda x: x["code"]),
                        ["code", "province", "total", "scanned_date"]))
    for name, rows, fields in outputs:
        with (out_dir / name).open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)

    sum_strata = sum(s["N_h"] for s in strata)
    sum_prov = sum(p["total"] for p in provinces)
    return {
        "strata": len(strata),
        "strata_N": sum_strata,
        "strata_empty": sum(1 for s in strata if s["N_h"] == 0),
        "provinces": len(provinces),
        "provinces_N": sum_prov,
        # > 1 means some postings are listed under more than one job type
        "strata_N_over_province_N": round(sum_strata / sum_prov, 3) if sum_prov else None,
        "listings_without_total": missing,
        "files": [name for name, _, _ in outputs],
        "out_dir": str(out_dir),
    }


def import_source(
    store: StagingStore,
    harvester_db: Path,
    source: str,
) -> dict[str, Any]:
    """Import one harvester SQLite file into `store`. Returns counts."""
    scope = f"import_sqlite:{harvester_db.name}"
    run_first = store.get_or_create_scrape_run(source, f"{scope}:first_seen")
    run_last = store.get_or_create_scrape_run(source, f"{scope}:last_seen")
    run_posts = store.get_or_create_scrape_run(source, f"{scope}:postings")

    counts = {
        "source": source,
        "harvester_db": str(harvester_db),
        "jobs": 0,
        "listing_seen_new": 0,
        "ok": 0,
        "parsed": 0,
        "parse_failed": 0,
        "inserted": 0,
        "duplicates": 0,
        "not_fetched": 0,
        "errors": 0,
    }
    first_rows: list[dict[str, Any]] = []
    last_rows: list[dict[str, Any]] = []
    postings: list[dict[str, Any]] = []

    def flush() -> None:
        counts["listing_seen_new"] += store.insert_listing_seen(
            run_first, first_rows, update_existing=True
        )
        counts["listing_seen_new"] += store.insert_listing_seen(
            run_last, last_rows, update_existing=True
        )
        if postings:
            stats = store.upsert_job_postings(postings, scrape_run_id=run_posts)
            counts["inserted"] += stats["inserted"]
            counts["duplicates"] += stats["duplicates"]
        first_rows.clear()
        last_rows.clear()
        postings.clear()

    con = open_readonly(harvester_db)
    try:
        for row in _iter_jobs(con, source):
            counts["jobs"] += 1
            job_id, url = split_job_key(source, str(row["job_key"]))
            stratum = job_stratum(source, row)
            first = to_bangkok_date(row["first_seen"])
            last = to_bangkok_date(row["last_seen"]) or first
            if first:
                base = {"source": source, "source_job_id": job_id, "stratum": stratum}
                first_rows.append({**base, "seen_date": first})
                last_rows.append({**base, "seen_date": last})

            status = row["status"]
            if status == "ok" and row["jsonld"]:
                counts["ok"] += 1
                try:
                    item = json.loads(row["jsonld"])
                except json.JSONDecodeError:
                    item = None
                rec = parse_jobposting_item(
                    item, source=source, source_job_id=job_id, source_url=url or None
                ) if isinstance(item, dict) else None
                if rec is None:
                    counts["parse_failed"] += 1
                else:
                    counts["parsed"] += 1
                    postings.append(rec)
            elif status == "error":
                counts["errors"] += 1
            else:  # pending / gone
                counts["not_fetched"] += 1

            if len(first_rows) >= BATCH or len(postings) >= BATCH:
                flush()
        flush()
    finally:
        con.close()

    for run_id, n_fetched in ((run_first, 0), (run_last, 0), (run_posts, counts["parsed"])):
        store.update_scrape_run(
            run_id,
            status="done",
            n_discovered=counts["jobs"],
            n_fetched=n_fetched,
            n_failed=counts["errors"] + counts["parse_failed"],
            finished=True,
        )
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--jobthai", type=Path, default=DEFAULT_JOBTHAI_DB)
    parser.add_argument("--jobbkk", type=Path, default=DEFAULT_JOBBKK_DB)
    parser.add_argument(
        "--sqlite-path",
        default=None,
        help="Write staging to this SQLite file (default: DATABASE_URL, else data/processed/staging.db)",
    )
    parser.add_argument(
        "--strata-dir",
        type=Path,
        default=DEFAULT_STRATA_DIR,
        help="Where to write jobthai_strata.csv and jobthai_province_totals.csv (N_h)",
    )
    args = parser.parse_args(argv)

    targets = [(p, s) for p, s in ((args.jobthai, "jobthai"), (args.jobbkk, "jobbkk")) if p.is_file()]
    if not targets:
        parser.error("no harvester SQLite file found (looked for --jobthai / --jobbkk)")

    if args.sqlite_path is None and not os.getenv("DATABASE_URL"):
        env_file = Path(__file__).resolve().parents[2] / ".env"
        if env_file.exists():
            load_dotenv(dotenv_path=env_file, override=False)

    store = StagingStore(sqlite_path=args.sqlite_path) if args.sqlite_path else StagingStore()
    try:
        results = [import_source(store, path, source) for path, source in targets]
        strata = export_jobthai_strata(args.jobthai, args.strata_dir) if args.jobthai.is_file() else None
        print(json.dumps({"backend": store.backend, "results": results, "jobthai_strata": strata},
                         ensure_ascii=False, indent=2))
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
