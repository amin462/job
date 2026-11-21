"""Polite sequential harvester for JobBKK public job postings (T1.9, T8.6).

Collects academic non-commercial samples across Thailand from `www.jobbkk.com`
and `store.jobbkk.com` into `data/raw/jobbkk/`:
- Source: JobBKK ONLY (never JobTopGun, JobsDB, Indeed).
- Concurrency: strictly 1 (sequential Playwright listing render + sequential httpx detail fetch).
- Delay: >= 5.0s + jitter (default 5.2s - 6.3s) BEFORE EVERY HTTP / page request.
- Immediate halt on HTTP 403, HTTP 429, or CAPTCHA body -> logs status to
  `data/raw/jobbkk/scrape_runs.jsonl` and exits with code 2.
- Resume: skips any `job_{id}.html` already present in `data/raw/jobbkk/`.
- PDPA validation: parses `JobPosting` JSON-LD via `pipeline.scraper.parse.parse_html`
  (stripping all HR contact keys and scrubbing phones/emails/LINE IDs).

Usage:
  .\\.venv\\Scripts\\python.exe -B -X utf8 -m pipeline.scraper.jobbkk_harvest --max-jobs 80
  .\\.venv\\Scripts\\python.exe -B -X utf8 -m pipeline.scraper.jobbkk_harvest --summary-only
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
import json
from pathlib import Path
import random
import re
import sys
import time
from typing import Any, Callable
from urllib.parse import quote

import httpx

from pipeline.scraper.config import (
    DEFAULT_TIMEOUT_SEC,
    JOBBKK_CATEGORY_LIST_URL,
    JOBBKK_DETAIL_URL,
    JOBBKK_LIST_URL,
    JOBBKK_REGION_URLS,
    JOBBKK_URGENT_URL,
    MIN_DELAY_SEC,
    SELECTORS,
    USER_AGENT,
    enforce_delay,
    validate_source,
    validate_url,
)
from pipeline.scraper.parse import parse_html

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = REPO_ROOT / "data" / "raw" / "jobbkk"
DEFAULT_MIN_DELAY_SEC: float = 5.2
DEFAULT_MAX_DELAY_SEC: float = 6.3
CONCURRENCY: int = 1

_JOB_FILE_RX = re.compile(r"^job_(\d+)\.html?$", re.I)
_DETAIL_PAIR_RX = re.compile(str(SELECTORS["jobbkk_detail_path_regex"]))

# Diverse Thailand-wide JobBKK listing provinces & categories
JOBBKK_PROVINCE_SLUGS: tuple[str, ...] = (
    "ทุกจังหวัด",
    "กรุงเทพมหานคร",
    "สมุทรปราการ",
    "ชลบุรี",
    "ระยอง",
    "นนทบุรี",
    "ปทุมธานี",
    "เชียงใหม่",
    "ขอนแก่น",
    "ภูเก็ต",
    "สงขลา",
    "นครราชสีมา",
    "พระนครศรีอยุธยา",
    "นครปฐม",
    "สมุทรสาคร",
    "สุราษฎร์ธานี",
    "ฉะเชิงเทรา",
    "สระบุรี",
    "อุดรธานี",
)

JOBBKK_CATEGORY_SLUGS: tuple[str, ...] = (
    "ทั้งหมด",
    "โปรแกรมเมอร์",
    "บัญชี",
    "วิศวกรรม",
    "การตลาด",
    "ขาย",
    "ช่างเทคนิค",
    "คีย์ข้อมูล",
    "เจ้าหน้าที่ความปลอดภัย",
    "ขนส่ง",
    "ทรัพยากรบุคคล",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _encode_jobbkk_url(url: str) -> str:
    """Percent-encode non-ASCII path segments in JobBKK Thai URLs cleanly."""
    if "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    host, _, path_q = rest.partition("/")
    path, sep, query = path_q.partition("?")
    encoded_path = quote(path, safe="/,.-_~")
    return f"{scheme}://{host}/{encoded_path}{sep}{query}"


_SCRIPT_TAG_RX = re.compile(r"<script[^>]*>.*?</script>", re.S | re.I)


def detect_block(status_code: int | None, body: str) -> str | None:
    """Detect HTTP 403/429 or CAPTCHA challenge markers in status/visible body."""
    if status_code == 403:
        return "stopped_403"
    if status_code == 429:
        return "stopped_429"
    raw = body or ""
    head = raw[:12000].lower()
    visible = _SCRIPT_TAG_RX.sub(" ", raw).lower()
    # Hard challenge markers checked across full body
    full_lower = raw.lower()
    for challenge_kw in ("cf-challenge", "verify you are human", "g-recaptcha", "hcaptcha", "turnstile"):
        if challenge_kw in full_lower:
            return "stopped_captcha"
    # General 'captcha' checked in head or non-script HTML (ignores Next.js i18n JSON bundles)
    if "captcha" in head or "captcha" in visible:
        return "stopped_captcha"
    for kw in SELECTORS["captcha_keywords"]:  # type: ignore[union-attr]
        k = str(kw).lower()
        if k in head or k in visible:
            return "stopped_captcha"
    return None


def scan_existing_jobbkk_ids(out_dir: Path = DEFAULT_OUT_DIR) -> set[str]:
    """Scan existing `job_*.html` files in `out_dir` so they are skipped on resume."""
    existing: set[str] = set()
    if not out_dir.is_dir():
        return existing
    for fpath in out_dir.iterdir():
        if not fpath.is_file():
            continue
        m = _JOB_FILE_RX.match(fpath.name)
        if m and fpath.stat().st_size > 0:
            existing.add(m.group(1))
    return existing


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            raw = line.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
                if isinstance(obj, dict):
                    rows.append(obj)
            except json.JSONDecodeError:
                continue
    return rows


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def extract_jobbkk_listing_targets(
    html: str,
    stratum: str,
    seen_date: date | str | None = None,
) -> dict[str, Any]:
    """Offline HTML parser extracting unique JobBKK `(company_id, job_id)` pairs."""
    seen_str = (
        seen_date.isoformat()
        if isinstance(seen_date, date)
        else (str(seen_date) if seen_date else date.today().isoformat())
    )
    targets: list[dict[str, str]] = []
    seen_job_ids: set[str] = set()
    for cid, jid in _DETAIL_PAIR_RX.findall(html or ""):
        if jid in seen_job_ids:
            continue
        seen_job_ids.add(jid)
        detail_url = JOBBKK_DETAIL_URL.format(company_id=cid, job_id=jid)
        validate_url(detail_url)
        targets.append(
            {
                "source": "jobbkk",
                "company_id": cid,
                "source_job_id": jid,
                "detail_url": detail_url,
                "stratum": stratum,
                "seen_date": seen_str,
            }
        )
    return {
        "source": "jobbkk",
        "stratum": stratum,
        "seen_date": seen_str,
        "job_ids": [t["source_job_id"] for t in targets],
        "targets": targets,
    }


def build_jobbkk_schedule(max_pages: int = 4) -> list[dict[str, Any]]:
    """Build deterministic Thailand-wide stratified listing schedule for JobBKK."""
    schedule: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    def _add(url: str, stratum: str, province: str, category: str, page: int, mode: str) -> None:
        encoded = _encode_jobbkk_url(url)
        validate_url(encoded)
        if encoded in seen_urls:
            return
        seen_urls.add(encoded)
        schedule.append(
            {
                "url": encoded,
                "raw_url": url,
                "stratum": stratum,
                "province": province,
                "category": category,
                "page": page,
                "mode": mode,
            }
        )

    # Wave 1: Diverse category pages + regional pages + province page 1 across Thailand
    for cat in JOBBKK_CATEGORY_SLUGS[1:]:
        _add(
            JOBBKK_CATEGORY_LIST_URL.format(page=1, category=cat, province="ทุกจังหวัด"),
            f"jobbkk|p=ทุกจังหวัด|c={cat}|page=1",
            "ทุกจังหวัด",
            cat,
            1,
            "playwright",
        )
    for prov in JOBBKK_PROVINCE_SLUGS:
        _add(
            JOBBKK_LIST_URL.format(page=1, province=prov),
            f"jobbkk|p={prov}|c=ทั้งหมด|page=1",
            prov,
            "ทั้งหมด",
            1,
            "playwright",
        )
    for region_name, reg_url in JOBBKK_REGION_URLS.items():
        _add(
            reg_url,
            f"jobbkk|region={region_name}",
            region_name,
            "ทั้งหมด",
            1,
            "http",
        )
    _add(JOBBKK_URGENT_URL, "jobbkk|urgent", "ทุกจังหวัด", "urgent", 1, "playwright")

    # Wave 2+: Paginated pages 2..max_pages across provinces & categories
    for page in range(2, max_pages + 1):
        for prov in JOBBKK_PROVINCE_SLUGS:
            _add(
                JOBBKK_LIST_URL.format(page=page, province=prov),
                f"jobbkk|p={prov}|c=ทั้งหมด|page={page}",
                prov,
                "ทั้งหมด",
                page,
                "playwright",
            )
        for cat in JOBBKK_CATEGORY_SLUGS[1:]:
            _add(
                JOBBKK_CATEGORY_LIST_URL.format(page=page, category=cat, province="ทุกจังหวัด"),
                f"jobbkk|p=ทุกจังหวัด|c={cat}|page={page}",
                "ทุกจังหวัด",
                cat,
                page,
                "playwright",
            )

    return schedule


def _polite_sleep(
    min_delay: float,
    max_delay: float,
    rng: random.Random,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> float:
    enforce_delay(min_delay)
    if max_delay < min_delay:
        raise ValueError(f"max_delay ({max_delay}) must be >= min_delay ({min_delay})")
    wait_sec = rng.uniform(min_delay, max_delay)
    sleep_fn(wait_sec)
    return wait_sec


def _launch_playwright_browser(pw: Any) -> Any:
    """Launch installed Chrome/Edge/Chromium headless browser cleanly."""
    for channel in ("chrome", "msedge", None):
        try:
            if channel:
                return pw.chromium.launch(channel=channel, headless=True)
            return pw.chromium.launch(headless=True)
        except Exception:
            continue
    raise RuntimeError("No Playwright Chromium/Chrome/Edge browser executable available.")


def _fetch_jobbkk_listing_live(
    target: dict[str, Any],
    *,
    http_client: httpx.Client,
    pw_page: Any | None,
    timeout_ms: int = 30000,
) -> tuple[int | None, str]:
    """Fetch a single JobBKK listing URL via Playwright (CSR) or httpx (SSR regional)."""
    url = str(target["url"])
    validate_url(url)
    if target.get("mode") == "http" or pw_page is None:
        resp = http_client.get(url)
        return resp.status_code, resp.text

    resp = pw_page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
    status_code = resp.status if resp else None
    initial_html = pw_page.content()
    block = detect_block(status_code, initial_html)
    if block is not None:
        return status_code, initial_html

    try:
        pw_page.wait_for_selector(str(SELECTORS["jobbkk_job_link"]), timeout=12000)
        pw_page.wait_for_timeout(800)
    except Exception:
        pass
    return status_code, pw_page.content()


def summarize_jobbkk_dir(out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Any]:
    """Parse all saved `job_*.html` in `out_dir` offline and report summary stats."""
    files = (
        sorted(p for p in out_dir.glob("job_*.html") if p.is_file() and p.stat().st_size > 0)
        if out_dir.is_dir()
        else []
    )

    parsed_clean = 0
    parse_failed = 0
    with_numeric_salary = 0
    provinces: Counter[str] = Counter()
    categories: Counter[str] = Counter()

    for fpath in files:
        html = fpath.read_text(encoding="utf-8", errors="ignore")
        rec = parse_html(html, source="jobbkk", file_path=fpath)
        if rec is None:
            parse_failed += 1
            continue
        parsed_clean += 1
        if rec.get("salary_min") is not None or rec.get("salary_max") is not None:
            with_numeric_salary += 1
        provinces[str(rec.get("province") or "ไม่ระบุ")] += 1
        categories[str(rec.get("job_category") or "ไม่ระบุ")] += 1

    return {
        "source": "jobbkk",
        "out_dir": str(out_dir),
        "total_files": len(files),
        "parsed_clean": parsed_clean,
        "parse_failed": parse_failed,
        "with_numeric_salary": with_numeric_salary,
        "salary_pct": round((100.0 * with_numeric_salary / parsed_clean), 1) if parsed_clean else 0.0,
        "unique_provinces": len(provinces),
        "unique_categories": len(categories),
        "top_provinces": provinces.most_common(12),
        "top_categories": categories.most_common(12),
    }


def run_jobbkk_batch(
    *,
    max_jobs: int = 80,
    min_listings_per_batch: int = 4,
    max_listings_per_batch: int = 12,
    out_dir: Path = DEFAULT_OUT_DIR,
    min_delay: float = DEFAULT_MIN_DELAY_SEC,
    max_delay: float = DEFAULT_MAX_DELAY_SEC,
    batch_label: str = "jobbkk_batch",
    seed: int | None = None,
    probe_only: bool = False,
    listing_provider: Callable[[dict[str, Any]], tuple[int | None, str] | str] | None = None,
    detail_transport: httpx.BaseTransport | None = None,
    detail_client: httpx.Client | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Run one sequential polite JobBKK harvest batch and append JSONL logs."""
    if CONCURRENCY != 1:
        raise RuntimeError("Concurrency must remain strictly 1")
    source_norm = validate_source("jobbkk")
    enforce_delay(min_delay)
    if max_delay < min_delay:
        raise ValueError(f"max_delay ({max_delay}) must be >= min_delay ({min_delay})")

    out_dir.mkdir(parents=True, exist_ok=True)
    listing_seen_path = out_dir / "listing_seen.jsonl"
    scrape_runs_path = out_dir / "scrape_runs.jsonl"
    failed_ids_path = out_dir / "failed_ids.jsonl"

    rng = random.Random(seed if seed is not None else int(time.time() * 1000))
    today_str = date.today().isoformat()
    run_id = f"{batch_label}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    started_at = _now_iso()

    existing_ids = scan_existing_jobbkk_ids(out_dir)
    failed_rows = _read_jsonl(failed_ids_path)
    failed_ids = {str(r.get("source_job_id")) for r in failed_rows if r.get("source_job_id")}
    excluded_ids = existing_ids | failed_ids

    seen_rows = _read_jsonl(listing_seen_path)
    fetched_listing_urls_today: set[str] = {
        str(r.get("listing_url"))
        for r in seen_rows
        if r.get("seen_date") == today_str and r.get("listing_url")
    }

    candidates_by_stratum: dict[str, list[tuple[str, str]]] = defaultdict(list)
    seen_candidate_ids: set[str] = set()
    for r in seen_rows:
        jid = str(r.get("source_job_id") or "").strip()
        d_url = str(r.get("detail_url") or "").strip()
        st = str(r.get("stratum") or "jobbkk|unknown")
        if jid and d_url and jid not in excluded_ids and jid not in seen_candidate_ids:
            validate_url(d_url)
            candidates_by_stratum[st].append((jid, d_url))
            seen_candidate_ids.add(jid)

    schedule = build_jobbkk_schedule(max_pages=4)
    unseen_schedule = [t for t in schedule if t["url"] not in fetched_listing_urls_today]

    status = "done"
    stopped_url: str | None = None
    n_listing_requests = 0
    n_discovered_total = 0
    n_discovered_new = 0
    n_detail_requests = 0
    n_fetched = 0
    n_parsed_clean = 0
    n_with_salary = 0
    n_failed = 0
    strata_fetched: Counter[str] = Counter()
    sleep_calls: list[float] = []

    def _sleep() -> None:
        sleep_calls.append(_polite_sleep(min_delay, max_delay, rng, sleep_fn=sleep_fn))

    def _current_unfetched_count() -> int:
        return sum(
            1
            for items in candidates_by_stratum.values()
            for jid, _ in items
            if jid not in excluded_ids
        )

    own_client = detail_client is None
    active_client = detail_client or httpx.Client(
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7",
        },
        timeout=DEFAULT_TIMEOUT_SEC,
        follow_redirects=True,
        transport=detail_transport,
    )

    pw_ctx = None
    pw_browser = None
    pw_context = None
    pw_page = None

    try:
        # Phase A: Sequential listing discovery
        target_buffer = max(max_jobs + 20, int(max_jobs * 1.25))
        if unseen_schedule and (probe_only or _current_unfetched_count() < target_buffer):
            if listing_provider is None and any(t.get("mode") == "playwright" for t in unseen_schedule):
                from playwright.sync_api import sync_playwright

                pw_ctx = sync_playwright().start()
                pw_browser = _launch_playwright_browser(pw_ctx)
                pw_context = pw_browser.new_context(user_agent=USER_AGENT, locale="th-TH")
                pw_page = pw_context.new_page()

            for target in unseen_schedule:
                if probe_only and n_listing_requests >= min_listings_per_batch:
                    break
                if not probe_only:
                    if n_listing_requests >= max_listings_per_batch:
                        break
                    if (
                        n_listing_requests >= min_listings_per_batch
                        and _current_unfetched_count() >= target_buffer
                    ):
                        break

                url = str(target["url"])
                validate_url(url)
                _sleep()

                try:
                    if listing_provider is not None:
                        out = listing_provider(target)
                        if isinstance(out, tuple) and len(out) == 2:
                            status_code, body = out
                        else:
                            status_code, body = 200, str(out)
                    else:
                        status_code, body = _fetch_jobbkk_listing_live(
                            target,
                            http_client=active_client,
                            pw_page=pw_page,
                        )
                    n_listing_requests += 1
                except Exception as exc:
                    n_listing_requests += 1
                    print(f"[jobbkk-listing] error on {url}: {exc}", file=sys.stderr, flush=True)
                    continue

                block = detect_block(status_code, body)
                if block is not None:
                    status = block
                    stopped_url = url
                    print(
                        f"[HALT] {block} detected on JobBKK listing {url} (HTTP {status_code})",
                        flush=True,
                    )
                    break

                if status_code is not None and status_code >= 400:
                    print(f"[jobbkk-listing] HTTP {status_code} on {url}, skipping", flush=True)
                    continue

                parsed_list = extract_jobbkk_listing_targets(
                    body,
                    stratum=str(target["stratum"]),
                    seen_date=today_str,
                )
                n_discovered_total += len(parsed_list["targets"])
                new_here = 0
                now_ts = _now_iso()
                for t in parsed_list["targets"]:
                    jid = t["source_job_id"]
                    d_url = t["detail_url"]
                    _append_jsonl(
                        listing_seen_path,
                        {
                            "run_id": run_id,
                            "source": source_norm,
                            "source_job_id": jid,
                            "company_id": t["company_id"],
                            "detail_url": d_url,
                            "stratum": target["stratum"],
                            "province": target.get("province"),
                            "category": target.get("category"),
                            "page": target.get("page"),
                            "listing_url": url,
                            "seen_date": today_str,
                            "discovered_at": now_ts,
                        },
                    )
                    if jid not in excluded_ids and jid not in seen_candidate_ids:
                        candidates_by_stratum[str(target["stratum"])].append((jid, d_url))
                        seen_candidate_ids.add(jid)
                        n_discovered_new += 1
                        new_here += 1

                print(
                    f"[jobbkk-listing {n_listing_requests}] {target['stratum']} | found={len(parsed_list['targets'])} new={new_here}",
                    flush=True,
                )

        # Phase B: Sequential detail fetch (strictly concurrency = 1)
        if status == "done" and not probe_only and max_jobs > 0:
            picked: list[tuple[str, str, str]] = []
            picked_ids: set[str] = set()
            queues = {
                st: [(jid, d_url) for jid, d_url in items if jid not in excluded_ids]
                for st, items in candidates_by_stratum.items()
            }
            strata_keys = [st for st, q in queues.items() if q]
            while len(picked) < max_jobs and strata_keys:
                next_keys: list[str] = []
                for st in strata_keys:
                    if len(picked) >= max_jobs:
                        break
                    q = queues[st]
                    while q:
                        jid, d_url = q.pop(0)
                        if jid not in excluded_ids and jid not in picked_ids:
                            picked.append((jid, d_url, st))
                            picked_ids.add(jid)
                            break
                    if q:
                        next_keys.append(st)
                strata_keys = next_keys

            print(
                f"[jobbkk-detail] Starting batch={batch_label}: queued={len(picked)} across {len({st for _, _, st in picked})} strata (existing={len(existing_ids)})",
                flush=True,
            )

            for idx, (jid, detail_url, stratum) in enumerate(picked, 1):
                dest_file = out_dir / f"job_{jid}.html"
                if jid in excluded_ids or (dest_file.exists() and dest_file.stat().st_size > 0):
                    excluded_ids.add(jid)
                    continue

                validate_url(detail_url)
                _sleep()

                try:
                    resp = active_client.get(detail_url)
                    n_detail_requests += 1
                except httpx.HTTPError as exc:
                    n_detail_requests += 1
                    n_failed += 1
                    _append_jsonl(
                        failed_ids_path,
                        {
                            "run_id": run_id,
                            "source_job_id": jid,
                            "detail_url": detail_url,
                            "stratum": stratum,
                            "reason": f"http_error:{type(exc).__name__}",
                            "recorded_at": _now_iso(),
                        },
                    )
                    excluded_ids.add(jid)
                    print(f"[{idx}/{len(picked)}] jobbkk job {jid} HTTP error: {exc}", flush=True)
                    continue

                block = detect_block(resp.status_code, resp.text)
                if block is not None:
                    status = block
                    stopped_url = detail_url
                    print(
                        f"[HALT] {block} detected on JobBKK detail {detail_url} (HTTP {resp.status_code})",
                        flush=True,
                    )
                    break

                if resp.status_code >= 400:
                    n_failed += 1
                    _append_jsonl(
                        failed_ids_path,
                        {
                            "run_id": run_id,
                            "source_job_id": jid,
                            "detail_url": detail_url,
                            "stratum": stratum,
                            "reason": f"http_{resp.status_code}",
                            "recorded_at": _now_iso(),
                        },
                    )
                    excluded_ids.add(jid)
                    print(f"[{idx}/{len(picked)}] jobbkk job {jid} HTTP {resp.status_code} (skipped)", flush=True)
                    continue

                rec = parse_html(
                    resp.text,
                    source="jobbkk",
                    source_job_id=jid,
                    source_url=detail_url,
                )
                if rec is None:
                    n_failed += 1
                    _append_jsonl(
                        failed_ids_path,
                        {
                            "run_id": run_id,
                            "source_job_id": jid,
                            "detail_url": detail_url,
                            "stratum": stratum,
                            "reason": "no_jobposting_jsonld",
                            "recorded_at": _now_iso(),
                        },
                    )
                    excluded_ids.add(jid)
                    print(f"[{idx}/{len(picked)}] jobbkk job {jid} missing JobPosting JSON-LD (skipped)", flush=True)
                    continue

                tmp_file = out_dir / f".tmp_job_{jid}.html"
                tmp_file.write_text(resp.text, encoding="utf-8")
                tmp_file.replace(dest_file)

                excluded_ids.add(jid)
                n_fetched += 1
                n_parsed_clean += 1
                if rec.get("salary_min") is not None or rec.get("salary_max") is not None:
                    n_with_salary += 1
                strata_fetched[stratum] += 1

                if idx % 10 == 0 or idx == len(picked):
                    print(
                        f"[{idx}/{len(picked)}] saved={n_fetched} clean={n_parsed_clean} salary={n_with_salary} prov={rec.get('province')} cat={rec.get('job_category')}",
                        flush=True,
                    )
    finally:
        if pw_context is not None:
            pw_context.close()
        if pw_browser is not None:
            pw_browser.close()
        if pw_ctx is not None:
            pw_ctx.stop()
        if own_client:
            active_client.close()

    total_files_now = len(
        [p for p in out_dir.glob("job_*.html") if p.is_file() and p.stat().st_size > 0]
    )
    run_record = {
        "run_id": run_id,
        "batch_label": batch_label,
        "source": source_norm,
        "started_at": started_at,
        "finished_at": _now_iso(),
        "status": status,
        "stopped_url": stopped_url,
        "min_delay_sec": min_delay,
        "max_delay_sec": max_delay,
        "concurrency": CONCURRENCY,
        "n_listing_requests": n_listing_requests,
        "n_discovered_total": n_discovered_total,
        "n_discovered_new": n_discovered_new,
        "n_detail_requests": n_detail_requests,
        "n_fetched": n_fetched,
        "n_parsed_clean": n_parsed_clean,
        "n_with_salary": n_with_salary,
        "n_failed": n_failed,
        "total_files_in_out_dir": total_files_now,
        "strata_sampled": dict(strata_fetched),
        "sleep_count": len(sleep_calls),
        "min_sleep_observed": min(sleep_calls) if sleep_calls else None,
    }
    _append_jsonl(scrape_runs_path, run_record)
    return run_record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Polite sequential JobBKK batch harvester (academic non-commercial)."
    )
    parser.add_argument("--max-jobs", type=int, default=80, help="Target new detail pages per batch")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Alias for --max-jobs (used by automated harvest runners)",
    )
    parser.add_argument("--min-listings", type=int, default=4, help="Min listing requests per batch")
    parser.add_argument("--max-listings", type=int, default=12, help="Max listing requests per batch")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="Output directory")
    parser.add_argument("--min-delay", type=float, default=DEFAULT_MIN_DELAY_SEC, help="Min delay >= 5.0s")
    parser.add_argument("--max-delay", type=float, default=DEFAULT_MAX_DELAY_SEC, help="Max delay >= min-delay")
    parser.add_argument("--label", default="jobbkk_batch", help="Batch label for logs")
    parser.add_argument("--seed", type=int, default=None, help="Optional RNG seed")
    parser.add_argument("--probe-only", action="store_true", help="Only probe listing pages without fetching details")
    parser.add_argument("--summary-only", action="store_true", help="Print offline stats for out-dir without HTTP requests")
    args = parser.parse_args(argv)

    out_path = Path(args.out_dir)
    if args.summary_only:
        summary = summarize_jobbkk_dir(out_path)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    limit = args.batch_size if args.batch_size is not None else args.max_jobs
    result = run_jobbkk_batch(
        max_jobs=limit,
        min_listings_per_batch=args.min_listings,
        max_listings_per_batch=args.max_listings,
        out_dir=out_path,
        min_delay=args.min_delay,
        max_delay=args.max_delay,
        batch_label=args.label,
        seed=args.seed,
        probe_only=args.probe_only,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] in ("stopped_403", "stopped_429", "stopped_captcha"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
