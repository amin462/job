"""Polite sequential batch harvester for real JobThai job postings.

Collects stratified samples across diverse Thai provinces and JobThai jobtype
categories into `data/raw/jobthai/`, strictly enforcing ToS, PDPA, and Polite
Scraping rules (D2, D4, D12, D13):
- Source: JobThai ONLY (`https://www.jobthai.com`).
- Concurrency: strictly 1 (sequential single-thread `httpx.Client`).
- Delay: >= 5.0s + jitter (default 5.2s - 6.3s) BEFORE EVERY HTTP request.
- Immediate halt on HTTP 403, HTTP 429, or CAPTCHA keywords in first 8000 chars.
- Resume / deduplication across `spike/raw/jobthai/` and `data/raw/jobthai/`.

Usage:
  .\\.venv\\Scripts\\python.exe -B -X utf8 -m pipeline.scraper.harvest_batch --batch-size 70
  .\\.venv\\Scripts\\python.exe -B -X utf8 -m pipeline.scraper.harvest_batch --summary-only
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
from typing import Any

import httpx

from pipeline.scraper.config import (
    DEFAULT_TIMEOUT_SEC,
    JOBTHAI_DETAIL_URL,
    JOBTHAI_JOBTYPES,
    JOBTHAI_PROVINCES,
    JOBTHAI_PROVINCE_CATEGORY_PAGE_URL,
    JOBTHAI_PROVINCE_CATEGORY_URL,
    JOBTHAI_PROVINCE_LIST_URL,
    JOBTHAI_PROVINCE_PAGE_URL,
    MIN_DELAY_SEC,
    SELECTORS,
    USER_AGENT,
    enforce_delay,
    validate_source,
    validate_url,
)
from pipeline.scraper.discovery import extract_listing_ids
from pipeline.scraper.parse import parse_html

# Alias matching spec reference while keeping pipeline.scraper.parse intact
parse_job_html = parse_html

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = REPO_ROOT / "data" / "raw" / "jobthai"
DEFAULT_EXISTING_DIRS: tuple[Path, ...] = (
    REPO_ROOT / "spike" / "raw" / "jobthai" / "sample",
    REPO_ROOT / "spike" / "raw" / "jobthai" / "by_province",
    REPO_ROOT / "spike" / "raw" / "jobthai",
    DEFAULT_OUT_DIR,
)

DEFAULT_MIN_DELAY_SEC: float = 5.2
DEFAULT_MAX_DELAY_SEC: float = 6.3
CONCURRENCY: int = 1
_JOB_FILE_RX = re.compile(r"^job_(\d+)\.html?$", re.I)

# Diverse regional & industrial provinces across Thailand
TARGET_PROVINCES: tuple[str, ...] = (
    "01",  # กรุงเทพมหานคร
    "09",  # ชลบุรี
    "59",  # สมุทรปราการ
    "49",  # ระยอง
    "24",  # นนทบุรี
    "28",  # ปทุมธานี
    "14",  # เชียงใหม่
    "06",  # ขอนแก่น
    "41",  # ภูเก็ต
    "57",  # สงขลา
    "21",  # นครราชสีมา
    "32",  # พระนครศรีอยุธยา
    "19",  # นครปฐม
    "61",  # สมุทรสาคร
    "67",  # สุราษฎร์ธานี
    "08",  # ฉะเชิงเทรา
    "30",  # ปราจีนบุรี
    "63",  # สระบุรี
    "50",  # ราชบุรี
    "73",  # อุดรธานี
    "53",  # ลำพูน
    "37",  # พิษณุโลก
    "13",  # เชียงราย
    "03",  # กาญจนบุรี
)

# Diverse JobThai jobtype codes for balanced occupation coverage & salary signal
TARGET_JOBTYPES: tuple[int, ...] = (
    7,   # งานคอมพิวเตอร์-ไอที
    15,  # งานบัญชี
    4,   # งานขาย
    28,  # งานวิศวกรรม
    11,  # งานช่างเทคนิค
    2,   # งานการตลาด
    6,   # งานขนส่งและคลังสินค้า
    16,  # งานทรัพยากรบุคคล
    17,  # งานผลิต-ควบคุมคุณภาพ-โรงงาน
    9,   # งานจัดซื้อ-งานธุรการ-ประสานงาน
    42,  # งานการเงิน-ธนาคาร
    14,  # งานบริการลูกค้า
    30,  # งานออกแบบ-กราฟิก-ช่างภาพ
    23,  # งานก่อสร้างสถาปัตยกรรม
    20,  # งานบริการด้านการแพทย์
    13,  # งานนำเข้า-ส่งออก
    10,  # งานสิ่งแวดล้อม-ความปลอดภัย
    50,  # งานบริการท่องเที่ยว-การโรงแรม
    27,  # งานวิทยาศาสตร์
    1,   # งานกฎหมาย
)

# Smaller regional provinces work well with province-only listing (all categories together)
PROVINCE_ONLY_FIRST: frozenset[str] = frozenset(
    {"14", "06", "41", "57", "21", "67", "50", "73", "53", "37", "13", "03"}
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def detect_block_in_head(status_code: int, body: str) -> str | None:
    """Detect HTTP 403/429 or CAPTCHA markers in first 8000 chars of body."""
    if status_code == 403:
        return "stopped_403"
    if status_code == 429:
        return "stopped_429"
    head = (body or "")[:8000].lower()
    if "captcha" in head:
        return "stopped_captcha"
    for kw in SELECTORS["captcha_keywords"]:  # type: ignore[union-attr]
        if str(kw).lower() in head:
            return "stopped_captcha"
    return None


def scan_existing_job_ids(dirs: tuple[Path, ...] = DEFAULT_EXISTING_DIRS) -> set[str]:
    """Scan all existing `job_*.html` across spike and data raw dirs for dedup/resume."""
    existing: set[str] = set()
    for base_dir in dirs:
        if not base_dir.is_dir():
            continue
        for fpath in base_dir.iterdir():
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


def build_stratified_listing_schedule(max_pages: int = 3) -> list[dict[str, Any]]:
    """Build deterministic interleaved schedule across diverse provinces x jobtypes."""
    schedule: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    def _add(province_code: str, jobtype_code: int | None, page: int) -> None:
        if province_code not in JOBTHAI_PROVINCES:
            return
        if jobtype_code is not None and jobtype_code not in JOBTHAI_JOBTYPES:
            return
        if jobtype_code is None:
            url = (
                JOBTHAI_PROVINCE_LIST_URL.format(province_code=province_code)
                if page == 1
                else JOBTHAI_PROVINCE_PAGE_URL.format(province_code=province_code, page=page)
            )
            stratum = f"p={province_code}|p_page={page}"
        else:
            url = (
                JOBTHAI_PROVINCE_CATEGORY_URL.format(
                    province_code=province_code, jobtype_code=jobtype_code
                )
                if page == 1
                else JOBTHAI_PROVINCE_CATEGORY_PAGE_URL.format(
                    province_code=province_code, jobtype_code=jobtype_code, page=page
                )
            )
            stratum = f"p={province_code}|c={jobtype_code}"
        validate_url(url)
        if url in seen_urls:
            return
        seen_urls.add(url)
        schedule.append(
            {
                "url": url,
                "stratum": stratum,
                "province_code": province_code,
                "province_name": JOBTHAI_PROVINCES[province_code],
                "jobtype_code": jobtype_code,
                "jobtype_name": JOBTHAI_JOBTYPES.get(jobtype_code) if jobtype_code else None,
                "page": page,
            }
        )

    # Wave 1: Interleaved mix of major hub province x jobtype strata AND regional province-wide strata
    # so even Batch 1 covers Bangkok, industrial hubs, regional centers, and diverse jobtypes.
    major_hubs = ["01", "09", "59", "49", "24", "28", "32", "19", "61", "08", "30", "63"]
    regional_provs = [p for p in TARGET_PROVINCES if p in PROVINCE_ONLY_FIRST]
    max_len = max(len(major_hubs), len(regional_provs))
    for i in range(max_len):
        if i < len(major_hubs):
            _add(major_hubs[i], TARGET_JOBTYPES[i % len(TARGET_JOBTYPES)], 1)
        if i < len(regional_provs):
            _add(regional_provs[i], None, 1)

    # Wave 2+: Interleave remaining province x jobtype combinations across pages 1..max_pages
    core_provs = list(TARGET_PROVINCES)
    n_jt = len(TARGET_JOBTYPES)
    for page in range(1, max_pages + 1):
        for jt_offset in range(n_jt):
            for p_idx, prov in enumerate(core_provs):
                jt = TARGET_JOBTYPES[(jt_offset + p_idx) % n_jt]
                _add(prov, jt, page)

    # Extra province-only page 2-3 for regional provinces
    for page in range(2, max_pages + 1):
        for prov in TARGET_PROVINCES:
            if prov in PROVINCE_ONLY_FIRST:
                _add(prov, None, page)

    return schedule


def _round_robin_pick(
    candidates_by_stratum: dict[str, list[str]],
    excluded_ids: set[str],
    limit: int,
) -> list[tuple[str, str]]:
    """Select up to `limit` unique (job_id, stratum) pairs evenly across strata."""
    queues: dict[str, list[str]] = {}
    for stratum, ids in candidates_by_stratum.items():
        clean = [jid for jid in ids if jid not in excluded_ids]
        if clean:
            queues[stratum] = clean

    picked: list[tuple[str, str]] = []
    picked_ids: set[str] = set()
    strata_keys = list(queues.keys())
    while len(picked) < limit and strata_keys:
        next_keys: list[str] = []
        for st in strata_keys:
            if len(picked) >= limit:
                break
            q = queues[st]
            while q:
                jid = q.pop(0)
                if jid not in excluded_ids and jid not in picked_ids:
                    picked.append((jid, st))
                    picked_ids.add(jid)
                    break
            if q:
                next_keys.append(st)
        strata_keys = next_keys
    return picked


def summarize_raw_dir(out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Any]:
    """Parse all saved `job_*.html` in `out_dir` and report completeness/salary stats."""
    files = sorted(
        p for p in out_dir.glob("job_*.html") if p.is_file() and p.stat().st_size > 0
    ) if out_dir.is_dir() else []

    parsed_clean = 0
    parse_failed = 0
    with_numeric_salary = 0
    provinces: Counter[str] = Counter()
    categories: Counter[str] = Counter()

    for fpath in files:
        html = fpath.read_text(encoding="utf-8", errors="ignore")
        rec = parse_job_html(html, source="jobthai", file_path=fpath)
        if rec is None:
            parse_failed += 1
            continue
        parsed_clean += 1
        if rec.get("salary_min") is not None or rec.get("salary_max") is not None:
            with_numeric_salary += 1
        provinces[str(rec.get("province") or "ไม่ระบุ")] += 1
        categories[str(rec.get("job_category") or "ไม่ระบุ")] += 1

    return {
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


def _polite_sleep(
    min_delay: float,
    max_delay: float,
    rng: random.Random,
    sleep_fn: Any = time.sleep,
) -> float:
    enforce_delay(min_delay)
    if max_delay < min_delay:
        raise ValueError(f"max_delay ({max_delay}) must be >= min_delay ({min_delay})")
    wait_sec = rng.uniform(min_delay, max_delay)
    sleep_fn(wait_sec)
    return wait_sec


def run_batch(
    *,
    batch_size: int = 70,
    min_listings_per_batch: int = 6,
    max_listings_per_batch: int = 16,
    out_dir: Path = DEFAULT_OUT_DIR,
    min_delay: float = DEFAULT_MIN_DELAY_SEC,
    max_delay: float = DEFAULT_MAX_DELAY_SEC,
    batch_label: str = "batch",
    seed: int | None = None,
    probe_only: bool = False,
) -> dict[str, Any]:
    """Run one sequential polite harvest batch and append JSONL logs."""
    if CONCURRENCY != 1:
        raise RuntimeError("Concurrency must remain strictly 1")
    source_norm = validate_source("jobthai")
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

    existing_dirs = tuple(dict.fromkeys((*DEFAULT_EXISTING_DIRS, out_dir)))
    existing_ids = scan_existing_job_ids(existing_dirs)
    failed_rows = _read_jsonl(failed_ids_path)
    failed_ids = {str(r.get("source_job_id")) for r in failed_rows if r.get("source_job_id")}
    excluded_ids = existing_ids | failed_ids

    # Load previously discovered IDs and listing URLs fetched today
    seen_rows = _read_jsonl(listing_seen_path)
    fetched_listing_urls_today: set[str] = {
        str(r.get("listing_url"))
        for r in seen_rows
        if r.get("seen_date") == today_str and r.get("listing_url")
    }
    candidates_by_stratum: dict[str, list[str]] = defaultdict(list)
    seen_candidate_set: set[str] = set()
    for r in seen_rows:
        jid = str(r.get("source_job_id") or "").strip()
        st = str(r.get("stratum") or "unknown")
        if jid and jid not in excluded_ids and jid not in seen_candidate_set:
            candidates_by_stratum[st].append(jid)
            seen_candidate_set.add(jid)

    schedule = build_stratified_listing_schedule(max_pages=3)
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

    def _current_unfetched_count() -> int:
        return sum(
            1
            for ids in candidates_by_stratum.values()
            for jid in ids
            if jid not in excluded_ids
        )

    with httpx.Client(
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7",
        },
        timeout=DEFAULT_TIMEOUT_SEC,
        follow_redirects=True,
    ) as client:
        # Phase A: Discovery across new strata until we have diverse buffer
        target_buffer = max(batch_size + 40, int(batch_size * 1.5))
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
            _polite_sleep(min_delay, max_delay, rng)

            try:
                resp = client.get(url)
                n_listing_requests += 1
            except httpx.HTTPError as exc:
                n_listing_requests += 1
                print(f"[listing] HTTP error on {url}: {exc}", file=sys.stderr, flush=True)
                continue

            block = detect_block_in_head(resp.status_code, resp.text)
            if block is not None:
                status = block
                stopped_url = url
                print(f"[HALT] {block} detected on listing {url} (HTTP {resp.status_code})", flush=True)
                break

            if resp.status_code >= 400:
                print(f"[listing] HTTP {resp.status_code} on {url}, skipping", flush=True)
                continue

            parsed_list = extract_listing_ids(
                resp.text,
                stratum=str(target["stratum"]),
                source=source_norm,
                seen_date=today_str,
            )
            ids_found = parsed_list["job_ids"]
            n_discovered_total += len(ids_found)
            new_here = 0
            now_ts = _now_iso()
            for jid in ids_found:
                _append_jsonl(
                    listing_seen_path,
                    {
                        "run_id": run_id,
                        "source": source_norm,
                        "source_job_id": jid,
                        "stratum": target["stratum"],
                        "province_code": target["province_code"],
                        "jobtype_code": target["jobtype_code"],
                        "page": target["page"],
                        "listing_url": url,
                        "listing_total": parsed_list["total"],
                        "seen_date": today_str,
                        "discovered_at": now_ts,
                    },
                )
                if jid not in excluded_ids and jid not in seen_candidate_set:
                    candidates_by_stratum[str(target["stratum"])].append(jid)
                    seen_candidate_set.add(jid)
                    n_discovered_new += 1
                    new_here += 1

            print(
                f"[listing {n_listing_requests}] {target['stratum']} | found={len(ids_found)} new={new_here} total_reported={parsed_list['total']}",
                flush=True,
            )

        # Phase B: Sequential detail fetch (unless halted or probe_only)
        if status == "done" and not probe_only and batch_size > 0:
            picked = _round_robin_pick(candidates_by_stratum, excluded_ids, limit=batch_size)
            print(
                f"[detail] Starting batch={batch_label}: queued={len(picked)} across {len({st for _, st in picked})} strata (existing={len(existing_ids)})",
                flush=True,
            )

            for idx, (jid, stratum) in enumerate(picked, 1):
                dest_file = out_dir / f"job_{jid}.html"
                if jid in excluded_ids or (dest_file.exists() and dest_file.stat().st_size > 0):
                    excluded_ids.add(jid)
                    continue

                detail_url = JOBTHAI_DETAIL_URL.format(job_id=jid)
                validate_url(detail_url)
                _polite_sleep(min_delay, max_delay, rng)

                try:
                    resp = client.get(detail_url)
                    n_detail_requests += 1
                except httpx.HTTPError as exc:
                    n_detail_requests += 1
                    n_failed += 1
                    _append_jsonl(
                        failed_ids_path,
                        {
                            "run_id": run_id,
                            "source_job_id": jid,
                            "stratum": stratum,
                            "reason": f"http_error:{type(exc).__name__}",
                            "recorded_at": _now_iso(),
                        },
                    )
                    excluded_ids.add(jid)
                    print(f"[{idx}/{len(picked)}] job {jid} HTTP error: {exc}", flush=True)
                    continue

                block = detect_block_in_head(resp.status_code, resp.text)
                if block is not None:
                    status = block
                    stopped_url = detail_url
                    print(
                        f"[HALT] {block} detected on detail {detail_url} (HTTP {resp.status_code})",
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
                            "stratum": stratum,
                            "reason": f"http_{resp.status_code}",
                            "recorded_at": _now_iso(),
                        },
                    )
                    excluded_ids.add(jid)
                    print(f"[{idx}/{len(picked)}] job {jid} HTTP {resp.status_code} (skipped)", flush=True)
                    continue

                rec = parse_job_html(resp.text, source=source_norm, source_job_id=jid)
                if rec is None:
                    n_failed += 1
                    _append_jsonl(
                        failed_ids_path,
                        {
                            "run_id": run_id,
                            "source_job_id": jid,
                            "stratum": stratum,
                            "reason": "no_jobposting_jsonld",
                            "recorded_at": _now_iso(),
                        },
                    )
                    excluded_ids.add(jid)
                    print(f"[{idx}/{len(picked)}] job {jid} missing JobPosting JSON-LD (skipped)", flush=True)
                    continue

                tmp_file = out_dir / f".tmp_job_{jid}.html"
                tmp_file.write_text(resp.text, encoding="utf-8")
                tmp_file.replace(dest_file)

                excluded_ids.add(jid)
                n_fetched += 1
                n_parsed_clean += 1
                has_sal = rec.get("salary_min") is not None or rec.get("salary_max") is not None
                if has_sal:
                    n_with_salary += 1
                strata_fetched[stratum] += 1

                if idx % 10 == 0 or idx == len(picked):
                    print(
                        f"[{idx}/{len(picked)}] saved={n_fetched} clean={n_parsed_clean} salary={n_with_salary} prov={rec.get('province')} cat={rec.get('job_category')}",
                        flush=True,
                    )

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
    }
    _append_jsonl(scrape_runs_path, run_record)
    return run_record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Polite sequential batch JobThai harvester into data/raw/jobthai/."
    )
    parser.add_argument("--batch-size", type=int, default=70, help="Target new detail pages per batch")
    parser.add_argument("--min-listings", type=int, default=6, help="Min listing requests per batch")
    parser.add_argument("--max-listings", type=int, default=16, help="Max listing requests per batch")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="Output directory")
    parser.add_argument("--min-delay", type=float, default=DEFAULT_MIN_DELAY_SEC, help="Min delay >= 5.0s")
    parser.add_argument("--max-delay", type=float, default=DEFAULT_MAX_DELAY_SEC, help="Max delay >= min-delay")
    parser.add_argument("--label", default="batch", help="Batch label for logs")
    parser.add_argument("--seed", type=int, default=None, help="Optional RNG seed")
    parser.add_argument("--probe-only", action="store_true", help="Only probe listing pages without fetching details")
    parser.add_argument("--summary-only", action="store_true", help="Print offline stats for out-dir without HTTP requests")
    args = parser.parse_args(argv)

    out_path = Path(args.out_dir)
    if args.summary_only:
        summary = summarize_raw_dir(out_path)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    result = run_batch(
        batch_size=args.batch_size,
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
