"""Polite sequential httpx detail-page fetcher with immediate block halt (T1.4).

Enforces:
- Concurrency = 1 (strictly sequential).
- Minimum delay >= 5.0 seconds + random jitter (refuses delay < 5.0).
- Resume support: skips any job ID whose raw HTML file already exists on disk.
- Immediate halt on HTTP 403, HTTP 429, or CAPTCHA body, recording
  `stopped_403` / `stopped_429` / `stopped_captcha` into `staging.scrape_run`.
- Strict rejection of forbidden sources and domains (`jobtopgun`, `jobsdb`, `indeed`).
"""
from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Any, Callable, Sequence

import httpx

from pipeline.scraper.config import (
    DEFAULT_CONCURRENCY,
    DEFAULT_JITTER_SEC,
    DEFAULT_TIMEOUT_SEC,
    JOBTHAI_DETAIL_URL,
    MIN_DELAY_SEC,
    SELECTORS,
    USER_AGENT,
    enforce_delay,
    validate_source,
    validate_url,
)
from pipeline.scraper.load_staging import StagingStore


def detect_block_reason(status_code: int, body: str) -> str | None:
    """Return halt status (`stopped_403` | `stopped_429` | `stopped_captcha`) or None."""
    status_map = SELECTORS["block_status_map"]
    if isinstance(status_map, dict) and status_code in status_map:
        return str(status_map[status_code])

    lowered = (body or "").lower()
    for kw in SELECTORS["captcha_keywords"]:  # type: ignore[union-attr]
        if str(kw) in lowered:
            return "stopped_captcha"
    return None


def fetch_jobs(
    job_ids: Sequence[str],
    out_dir: str | Path,
    *,
    source: str = "jobthai",
    delay_sec: float = MIN_DELAY_SEC,
    jitter_sec: float = DEFAULT_JITTER_SEC,
    timeout_sec: float = DEFAULT_TIMEOUT_SEC,
    store: StagingStore | None = None,
    scrape_run_id: int | None = None,
    scope: str = "detail_fetch",
    client: httpx.Client | None = None,
    transport: httpx.BaseTransport | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    rng: random.Random | None = None,
    url_template: str | None = None,
) -> dict[str, Any]:
    """Fetch detail HTML pages sequentially with polite pacing and resume support."""
    if DEFAULT_CONCURRENCY != 1:
        raise RuntimeError("Concurrency must remain strictly 1")

    source_norm = validate_source(source)
    base_delay = enforce_delay(delay_sec)
    if jitter_sec < 0:
        raise ValueError(f"jitter_sec must be >= 0, got {jitter_sec}")

    local_rng = rng or random.Random(42)
    out_path_dir = Path(out_dir)
    out_path_dir.mkdir(parents=True, exist_ok=True)

    unique_ids = list(dict.fromkeys(str(jid).strip() for jid in job_ids if str(jid).strip()))
    template = url_template or JOBTHAI_DETAIL_URL

    # Validate all target URLs upfront before making any request
    for jid in unique_ids:
        validate_url(template.format(job_id=jid))

    active_run_id = scrape_run_id
    if store is not None and active_run_id is None:
        active_run_id = store.create_scrape_run(source_norm, scope=scope)

    own_client = client is None
    active_client = client or httpx.Client(
        headers={"User-Agent": USER_AGENT},
        timeout=timeout_sec,
        follow_redirects=True,
        transport=transport,
    )

    n_fetched = 0
    n_skipped = 0
    n_failed = 0
    fetched_files: list[str] = []
    sleep_calls: list[float] = []
    final_status = "done"
    stopped_at_job_id: str | None = None
    requests_made = 0

    try:
        for idx, jid in enumerate(unique_ids):
            dest_file = out_path_dir / f"job_{jid}.html"
            if dest_file.exists() and dest_file.stat().st_size > 0:
                n_skipped += 1
                continue

            if requests_made > 0:
                wait_sec = base_delay + local_rng.uniform(0.0, jitter_sec)
                sleep_calls.append(wait_sec)
                sleep_fn(wait_sec)

            url = template.format(job_id=jid)
            validate_url(url)

            try:
                resp = active_client.get(url)
                requests_made += 1
            except httpx.HTTPError:
                requests_made += 1
                n_failed += 1
                continue

            block_status = detect_block_reason(resp.status_code, resp.text)
            if block_status is not None:
                final_status = block_status
                stopped_at_job_id = jid
                break

            if resp.status_code >= 400:
                n_failed += 1
                continue

            dest_file.write_text(resp.text, encoding="utf-8")
            n_fetched += 1
            fetched_files.append(str(dest_file))

            if store is not None and active_run_id is not None:
                store.update_scrape_run(
                    active_run_id,
                    n_discovered=len(unique_ids),
                    n_fetched=n_fetched,
                    n_failed=n_failed,
                )

        if store is not None and active_run_id is not None:
            store.update_scrape_run(
                active_run_id,
                status=final_status,
                n_discovered=len(unique_ids),
                n_fetched=n_fetched,
                n_failed=n_failed,
                finished=True,
            )
    finally:
        if own_client:
            active_client.close()

    return {
        "source": source_norm,
        "scrape_run_id": active_run_id,
        "status": final_status,
        "n_discovered": len(unique_ids),
        "n_fetched": n_fetched,
        "n_skipped": n_skipped,
        "n_failed": n_failed,
        "requests_made": requests_made,
        "sleep_calls": sleep_calls,
        "fetched_files": fetched_files,
        "stopped_at_job_id": stopped_at_job_id,
    }
