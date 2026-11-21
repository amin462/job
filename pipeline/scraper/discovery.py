"""Listing discovery for JobThai provinces and province x category strata (T1.3, T1.6).

Provides:
- `extract_listing_ids(html, stratum)`: Pure offline HTML parser extracting
  job IDs and listing total counts into `staging.listing_seen` format.
- `build_discovery_targets(...)`: Plans province-level targets plus per-category
  targets for large provinces (Bangkok 01, Chonburi 09).
- `discover_targets(...)`: Sequential Playwright or injected-provider runner that
  records every seen job ID into `staging.listing_seen` and stops immediately on
  HTTP 403/429 or CAPTCHA.
"""
from __future__ import annotations

import html as htmllib
import random
import re
import time
from datetime import date
from typing import Any, Callable, Sequence

from pipeline.scraper.config import (
    DEFAULT_JITTER_SEC,
    DEFAULT_TIMEOUT_SEC,
    JOBTHAI_JOBTYPES,
    JOBTHAI_PROVINCES,
    JOBTHAI_PROVINCE_CATEGORY_URL,
    JOBTHAI_PROVINCE_LIST_URL,
    LARGE_PROVINCE_CODES,
    LARGE_PROVINCE_THRESHOLD,
    MIN_DELAY_SEC,
    SELECTORS,
    USER_AGENT,
    enforce_delay,
    validate_source,
    validate_url,
)
from pipeline.scraper.load_staging import StagingStore

_JOB_ID_RX = re.compile(str(SELECTORS["job_id_regex"]))
_TOTAL_RX = re.compile(str(SELECTORS["total_count_regex"]))
_TITLE_RX = re.compile(str(SELECTORS["title_regex"]), re.I | re.S)


class DiscoveryBlockedError(RuntimeError):
    """Raised internally when discovery encounters 403, 429, or CAPTCHA."""

    def __init__(self, status: str, url: str) -> None:
        super().__init__(f"Discovery blocked ({status}) at {url}")
        self.status = status
        self.url = url


def _detect_block(status_code: int | None, html: str) -> str | None:
    if status_code == 403:
        return "stopped_403"
    if status_code == 429:
        return "stopped_429"
    lowered = (html or "").lower()
    keywords = SELECTORS["captcha_keywords"]
    if any(str(kw) in lowered for kw in keywords):
        return "stopped_captcha"
    return None


def extract_listing_ids(
    html: str,
    stratum: str,
    source: str = "jobthai",
    seen_date: date | str | None = None,
) -> dict[str, Any]:
    """Extract ordered unique job IDs and listing_seen records from listing HTML."""
    source_norm = validate_source(source)
    seen_str = (
        seen_date.isoformat()
        if isinstance(seen_date, date)
        else (str(seen_date) if seen_date else date.today().isoformat())
    )

    job_ids = list(dict.fromkeys(_JOB_ID_RX.findall(html or "")))
    total_match = _TOTAL_RX.search(html or "")
    total = int(total_match.group(1)) if total_match else None

    title_match = _TITLE_RX.search(html or "")
    page_title = htmllib.unescape(title_match.group(1)).strip() if title_match else None

    records = [
        {
            "source": source_norm,
            "source_job_id": jid,
            "stratum": stratum,
            "seen_date": seen_str,
        }
        for jid in job_ids
    ]

    return {
        "source": source_norm,
        "stratum": stratum,
        "total": total,
        "page_title": page_title,
        "job_ids": job_ids,
        "records": records,
        "seen_date": seen_str,
    }


def build_discovery_targets(
    province_codes: Sequence[str] | None = None,
    *,
    province_totals: dict[str, int] | None = None,
    large_province_codes: frozenset[str] | set[str] = LARGE_PROVINCE_CODES,
    large_threshold: int = LARGE_PROVINCE_THRESHOLD,
    jobtypes: dict[int, str] = JOBTHAI_JOBTYPES,
) -> list[dict[str, Any]]:
    """Build province and (for large provinces) province x jobtype discovery targets."""
    codes = list(province_codes) if province_codes is not None else sorted(JOBTHAI_PROVINCES.keys())
    targets: list[dict[str, Any]] = []
    for code in codes:
        code_str = str(code).zfill(2) if str(code).isdigit() else str(code)
        pop = province_totals.get(code_str, 0) if province_totals else 0
        is_large = code_str in large_province_codes or pop >= large_threshold
        if is_large:
            for jt_code, jt_name in sorted(jobtypes.items()):
                url = JOBTHAI_PROVINCE_CATEGORY_URL.format(
                    province_code=code_str,
                    jobtype_code=jt_code,
                )
                validate_url(url)
                targets.append(
                    {
                        "province_code": code_str,
                        "province_name": JOBTHAI_PROVINCES.get(code_str, ""),
                        "jobtype_code": jt_code,
                        "jobtype_name": jt_name,
                        "stratum": f"p={code_str}|c={jt_code}",
                        "url": url,
                    }
                )
        else:
            url = JOBTHAI_PROVINCE_LIST_URL.format(province_code=code_str)
            validate_url(url)
            targets.append(
                {
                    "province_code": code_str,
                    "province_name": JOBTHAI_PROVINCES.get(code_str, ""),
                    "jobtype_code": None,
                    "jobtype_name": None,
                    "stratum": f"p={code_str}",
                    "url": url,
                }
            )
    return targets


def _playwright_scroll_listing(
    url: str,
    *,
    max_scrolls: int = 10,
    delay_sec: float = MIN_DELAY_SEC,
    timeout_ms: int = int(DEFAULT_TIMEOUT_SEC * 1000),
    sleep_fn: Callable[[float], None] = time.sleep,
) -> list[str]:
    """Open a single JobThai listing URL with Playwright, scroll, and collect HTML."""
    validate_url(url)
    enforce_delay(delay_sec)
    from playwright.sync_api import sync_playwright

    pages_html: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT)
        page = context.new_page()
        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            status_code = resp.status if resp else None
            html = page.content()
            block = _detect_block(status_code, html)
            if block:
                raise DiscoveryBlockedError(block, url)
            pages_html.append(html)

            prev_count = len(_JOB_ID_RX.findall(html))
            for _ in range(max_scrolls):
                sleep_fn(delay_sec)
                page.evaluate(str(SELECTORS["load_more_trigger"]))
                page.wait_for_timeout(1200)
                cur_html = page.content()
                block = _detect_block(None, cur_html)
                if block:
                    raise DiscoveryBlockedError(block, url)
                pages_html.append(cur_html)
                cur_count = len(_JOB_ID_RX.findall(cur_html))
                if cur_count <= prev_count:
                    break
                prev_count = cur_count
        finally:
            context.close()
            browser.close()
    return pages_html


def discover_targets(
    targets: Sequence[dict[str, Any]],
    *,
    source: str = "jobthai",
    delay_sec: float = MIN_DELAY_SEC,
    jitter_sec: float = DEFAULT_JITTER_SEC,
    seen_date: date | str | None = None,
    max_scrolls: int = 10,
    store: StagingStore | None = None,
    scrape_run_id: int | None = None,
    scope: str = "discovery",
    html_provider: Callable[[dict[str, Any]], str | Sequence[str]] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    """Discover job IDs across targets, recording all seen IDs into `staging.listing_seen`."""
    source_norm = validate_source(source)
    enforce_delay(delay_sec)
    local_rng = rng or random.Random(42)

    seen_str = (
        seen_date.isoformat()
        if isinstance(seen_date, date)
        else (str(seen_date) if seen_date else date.today().isoformat())
    )

    own_store = store is None
    active_store = store
    active_run_id = scrape_run_id
    if active_store is not None and active_run_id is None:
        active_run_id = active_store.create_scrape_run(source_norm, scope=scope)

    discovered_by_stratum: dict[str, list[str]] = {}
    stratum_totals: dict[str, int] = {}
    all_records: list[dict[str, Any]] = []
    all_unique_ids: list[str] = []
    seen_global: set[str] = set()
    final_status = "done"
    stopped_url: str | None = None

    try:
        for idx, target in enumerate(targets):
            url = str(target["url"])
            stratum = str(target["stratum"])
            validate_url(url)

            if idx > 0:
                sleep_fn(delay_sec + local_rng.uniform(0.0, max(0.0, jitter_sec)))

            try:
                if html_provider is not None:
                    raw_out = html_provider(target)
                    if isinstance(raw_out, tuple) and len(raw_out) == 2 and isinstance(raw_out[0], int):
                        status_code, body = raw_out
                        block = _detect_block(status_code, str(body))
                        if block:
                            raise DiscoveryBlockedError(block, url)
                        html_pages = [str(body)]
                    elif isinstance(raw_out, str):
                        block = _detect_block(None, raw_out)
                        if block:
                            raise DiscoveryBlockedError(block, url)
                        html_pages = [raw_out]
                    else:
                        html_pages = [str(x) for x in raw_out]
                        for page_html in html_pages:
                            block = _detect_block(None, page_html)
                            if block:
                                raise DiscoveryBlockedError(block, url)
                else:
                    html_pages = _playwright_scroll_listing(
                        url,
                        max_scrolls=max_scrolls,
                        delay_sec=delay_sec,
                        sleep_fn=sleep_fn,
                    )
            except DiscoveryBlockedError as exc:
                final_status = exc.status
                stopped_url = exc.url
                break

            stratum_ids = discovered_by_stratum.setdefault(stratum, [])
            stratum_seen_set = set(stratum_ids)
            for html in html_pages:
                parsed = extract_listing_ids(
                    html,
                    stratum=stratum,
                    source=source_norm,
                    seen_date=seen_str,
                )
                if parsed["total"] is not None:
                    stratum_totals[stratum] = parsed["total"]
                for jid in parsed["job_ids"]:
                    if jid not in stratum_seen_set:
                        stratum_seen_set.add(jid)
                        stratum_ids.append(jid)
                    if jid not in seen_global:
                        seen_global.add(jid)
                        all_unique_ids.append(jid)
                        all_records.append(
                            {
                                "source": source_norm,
                                "source_job_id": jid,
                                "stratum": stratum,
                                "seen_date": seen_str,
                            }
                        )

        if active_store is not None and active_run_id is not None:
            if all_records:
                active_store.insert_listing_seen(active_run_id, all_records)
            active_store.update_scrape_run(
                active_run_id,
                status=final_status,
                n_discovered=len(all_unique_ids),
                finished=True,
            )
    finally:
        if own_store and active_store is not None:
            active_store.close()

    return {
        "source": source_norm,
        "scrape_run_id": active_run_id,
        "status": final_status,
        "stopped_url": stopped_url,
        "seen_date": seen_str,
        "n_discovered": len(all_unique_ids),
        "job_ids": all_unique_ids,
        "by_stratum": discovered_by_stratum,
        "stratum_totals": stratum_totals,
        "records": all_records,
    }
