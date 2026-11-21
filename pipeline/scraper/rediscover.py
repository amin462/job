"""Weekly re-discovery runner (T1.10, D14).

Opens ONLY listing pages (never re-fetches existing detail pages):
1. Runs discovery on configured targets and inserts all seen IDs into
   `staging.listing_seen` with `seen_date`, updating `last_seen`.
2. Excludes job IDs already fetched/stored in `staging.job_posting_raw` or on disk.
3. Plans stratified quota for newly discovered job IDs only.
4. Optionally fetches only newly queued job IDs.
"""
from __future__ import annotations

import argparse
import json
import random
import time
from datetime import date
from pathlib import Path
from typing import Any, Callable, Sequence

import httpx

from pipeline.scraper.config import (
    DEFAULT_JITTER_SEC,
    MIN_DELAY_SEC,
    enforce_delay,
    validate_source,
)
from pipeline.scraper.discovery import build_discovery_targets, discover_targets
from pipeline.scraper.fetch import fetch_jobs
from pipeline.scraper.load_staging import StagingStore
from pipeline.scraper.quota import compute_stratified_quota, select_stratified_sample


def _existing_disk_job_ids(raw_dir: str | Path | None) -> set[str]:
    if raw_dir is None:
        return set()
    p = Path(raw_dir)
    if not p.is_dir():
        return set()
    known: set[str] = set()
    for f in p.glob("job_*.html"):
        stem = f.stem
        if stem.startswith("job_") and f.stat().st_size > 0:
            known.add(stem[4:])
    return known


def run_weekly_rediscovery(
    targets: Sequence[dict[str, Any]],
    *,
    store: StagingStore,
    raw_dir: str | Path | None = None,
    source: str = "jobthai",
    seen_date: date | str | None = None,
    n_target_new: int = 500,
    min_per_stratum: int = 5,
    delay_sec: float = MIN_DELAY_SEC,
    jitter_sec: float = DEFAULT_JITTER_SEC,
    html_provider: Callable[[dict[str, Any]], str | Sequence[str]] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    fetch_new: bool = False,
    fetch_client: httpx.Client | None = None,
    fetch_transport: httpx.BaseTransport | None = None,
    seed: int = 42,
) -> dict[str, Any]:
    """Execute one weekly listing-only re-discovery cycle and queue only new IDs."""
    source_norm = validate_source(source)
    enforce_delay(delay_sec)

    seen_str = (
        seen_date.isoformat()
        if isinstance(seen_date, date)
        else (str(seen_date) if seen_date else date.today().isoformat())
    )

    scrape_run_id = store.create_scrape_run(
        source_norm, scope=f"weekly_rediscovery:{seen_str}"
    )

    disc_result = discover_targets(
        targets,
        source=source_norm,
        delay_sec=delay_sec,
        jitter_sec=jitter_sec,
        seen_date=seen_str,
        store=store,
        scrape_run_id=scrape_run_id,
        scope=f"weekly_rediscovery:{seen_str}",
        html_provider=html_provider,
        sleep_fn=sleep_fn,
        rng=random.Random(seed),
    )

    # Known job IDs from staging DB and existing HTML files on disk
    known_ids = store.get_known_job_ids(source_norm) | _existing_disk_job_ids(raw_dir)

    new_by_stratum: dict[str, list[str]] = {}
    new_pop_sizes: dict[str, int] = {}
    all_new_ids: list[str] = []
    seen_new: set[str] = set()
    existing_seen_ids: list[str] = []

    for stratum, ids in disc_result["by_stratum"].items():
        stratum_new: list[str] = []
        for jid in ids:
            if jid in known_ids:
                existing_seen_ids.append(jid)
                continue
            stratum_new.append(jid)
            if jid not in seen_new:
                seen_new.add(jid)
                all_new_ids.append(jid)
        if stratum_new:
            new_by_stratum[stratum] = stratum_new
            pop_val = disc_result["stratum_totals"].get(stratum)
            new_pop_sizes[stratum] = (
                int(pop_val) if pop_val is not None else len(stratum_new)
            )

    quota_plan = compute_stratified_quota(
        new_pop_sizes,
        n_target=n_target_new,
        min_per_stratum=min_per_stratum,
    )
    queued_jobs = select_stratified_sample(
        new_by_stratum,
        quota_plan,
        seed=seed,
    )
    queued_job_ids = [row["source_job_id"] for row in queued_jobs]

    # Guardrail: never allow an existing job ID into the detail-fetch queue
    overlap = set(queued_job_ids) & known_ids
    if overlap:
        raise RuntimeError(f"Rediscovery invariant violated: queued known IDs {overlap}")

    fetch_result: dict[str, Any] | None = None
    if fetch_new and queued_job_ids and disc_result["status"] == "done":
        if raw_dir is None:
            raise ValueError("raw_dir must be provided when fetch_new=True")
        fetch_result = fetch_jobs(
            queued_job_ids,
            raw_dir,
            source=source_norm,
            delay_sec=delay_sec,
            jitter_sec=jitter_sec,
            store=store,
            scope=f"weekly_rediscovery_fetch:{seen_str}",
            client=fetch_client,
            transport=fetch_transport,
            sleep_fn=sleep_fn,
            rng=random.Random(seed),
        )

    seen_summary = store.get_listing_seen_summary(source_norm)

    return {
        "source": source_norm,
        "scrape_run_id": scrape_run_id,
        "seen_date": seen_str,
        "discovery_status": disc_result["status"],
        "n_discovered": disc_result["n_discovered"],
        "n_existing_seen": len(dict.fromkeys(existing_seen_ids)),
        "n_new_discovered": len(all_new_ids),
        "new_job_ids": all_new_ids,
        "quota_plan": quota_plan,
        "queued_jobs": queued_jobs,
        "queued_job_ids": queued_job_ids,
        "seen_summary": seen_summary,
        "fetch_result": fetch_result,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run weekly listing-only JobThai re-discovery."
    )
    parser.add_argument(
        "--provinces",
        nargs="*",
        default=None,
        help="Optional province codes (e.g. 01 09 90); defaults to all provinces.",
    )
    parser.add_argument("--raw-dir", default="data/raw/jobthai", help="Raw HTML folder")
    parser.add_argument("--sqlite-path", default=None, help="Optional SQLite DB path")
    parser.add_argument("--target-new", type=int, default=500, help="Target new jobs to queue")
    parser.add_argument("--delay", type=float, default=MIN_DELAY_SEC, help="Delay >= 5.0s")
    parser.add_argument("--fetch-new", action="store_true", help="Fetch newly queued IDs")
    args = parser.parse_args(argv)

    enforce_delay(args.delay)
    targets = build_discovery_targets(province_codes=args.provinces)
    store = StagingStore(sqlite_path=args.sqlite_path) if args.sqlite_path else StagingStore()
    try:
        res = run_weekly_rediscovery(
            targets,
            store=store,
            raw_dir=args.raw_dir,
            n_target_new=args.target_new,
            delay_sec=args.delay,
            fetch_new=args.fetch_new,
        )
    finally:
        store.close()
    print(
        json.dumps(
            {
                "scrape_run_id": res["scrape_run_id"],
                "seen_date": res["seen_date"],
                "discovery_status": res["discovery_status"],
                "n_discovered": res["n_discovered"],
                "n_existing_seen": res["n_existing_seen"],
                "n_new_discovered": res["n_new_discovered"],
                "n_queued": len(res["queued_job_ids"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
