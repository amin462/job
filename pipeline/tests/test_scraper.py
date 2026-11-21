"""Offline test suite for the polite JobThai scraper modules (T1.2-T1.7, T1.10).

All tests run 100% offline against saved HTML files in `spike/raw/jobthai/` and
`httpx.MockTransport`. Never sends live HTTP/Playwright requests.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline.scraper import (
    FORBIDDEN_SOURCES,
    MIN_DELAY_SEC,
    ForbiddenSourceError,
    StagingStore,
    build_discovery_targets,
    compute_stratified_quota,
    discover_targets,
    enforce_delay,
    extract_listing_ids,
    fetch_jobs,
    load_province_totals,
    load_raw_directory,
    parse_file,
    parse_html,
    run_weekly_rediscovery,
    select_stratified_sample,
    validate_source,
    validate_url,
    verify_weight_conservation,
)
from pipeline.scraper.config import JOBTHAI_PROVINCES, LARGE_PROVINCE_CODES
from pipeline.scraper.parse import HR_CONTACT_KEYS

SAMPLE_DIR = REPO_ROOT / "spike" / "raw" / "jobthai" / "sample"
BY_PROVINCE_DIR = REPO_ROOT / "spike" / "raw" / "jobthai" / "by_province"
PROVINCE_TOTALS_CSV = BY_PROVINCE_DIR / "province_totals.csv"
PROV_TEST_HTML = REPO_ROOT / "spike" / "raw" / "jobthai" / "prov_test.html"
JOBS_LIST_P1_HTML = REPO_ROOT / "spike" / "raw" / "jobthai" / "jobs_list_p1.html"
JOBBKK_SAMPLE_HTML = REPO_ROOT / "spike" / "raw" / "jobbkk" / "job_sample.html"
JOBBKK_SOUTH_HTML = REPO_ROOT / "spike" / "raw" / "jobbkk" / "region_south.html"

FIXTURES_DIR = REPO_ROOT / "pipeline" / "tests" / "fixtures"
FIXTURE_POSTINGS_DIR = FIXTURES_DIR / "jobthai_postings"
FIXTURE_LISTING_HTML = FIXTURES_DIR / "jobthai_listing_sample.html"
FIXTURE_PROVINCE_TOTALS_CSV = FIXTURES_DIR / "province_totals.csv"
FIXTURE_JOBBKK_SAMPLE_HTML = FIXTURES_DIR / "jobbkk_job_sample.html"
FIXTURE_JOBBKK_LISTING_HTML = FIXTURES_DIR / "jobbkk_listing_sample.html"

_EMAIL_CHECK_RX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_CHECK_RX = re.compile(
    r"(?<![\dA-Za-z])"
    r"(?:\+66[\s\-.]*(?:\(0\)[\s\-.]*)?(?:[689]\d[\s\-.]?\d{3}[\s\-.]?\d{4}|[2-7][\s\-.]?\d{3,4}[\s\-.]?\d{3,4})"
    r"|\(?0[689]\d\)?[\s\-.]?\d{3}[\s\-.]?\d{4}"
    r"|\(?02\)?[\s\-.]?\d{3}[\s\-.]?\d{4}"
    r"|\(?0[3-7]\d\)?[\s\-.]?\d{3}[\s\-.]?\d{3,4})"
    r"(?!\d)"
)
_LINE_CHECK_RX = re.compile(
    r"(?:id\s*line|line\s*id|ไอดี\s*ไลน์|แอด\s*ไลน์)\s*[:=@\-]?\s*@?[A-Za-z0-9._-]{2,}",
    re.I,
)


def _collect_all_keys(obj: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(str(k).strip().lower())
            keys.update(_collect_all_keys(v))
    elif isinstance(obj, list):
        for item in obj:
            keys.update(_collect_all_keys(item))
    return keys


def _collect_all_strings(obj: Any) -> list[str]:
    out: list[str] = []
    if isinstance(obj, dict):
        for v in obj.values():
            out.extend(_collect_all_strings(v))
    elif isinstance(obj, list):
        for item in obj:
            out.extend(_collect_all_strings(item))
    elif isinstance(obj, str):
        out.append(obj)
    return out


# ---------------------------------------------------------------------------
# 1. Source & Polite Delay Policy Enforcement
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_source", sorted(FORBIDDEN_SOURCES) + ["JobTopGun", "JOBSDB", "indeed", "unknown"])
def test_forbidden_sources_rejected(bad_source: str, tmp_path: Path) -> None:
    with pytest.raises(ForbiddenSourceError):
        validate_source(bad_source)

    with pytest.raises(ForbiddenSourceError):
        extract_listing_ids("<html></html>", stratum="p=01", source=bad_source)

    with pytest.raises(ForbiddenSourceError):
        fetch_jobs(["123"], tmp_path, source=bad_source)

    with pytest.raises(ForbiddenSourceError):
        load_raw_directory(tmp_path, source=bad_source)


@pytest.mark.parametrize(
    "bad_url",
    [
        "https://www.jobtopgun.com/th/jobs/j123-1",
        "https://th.jobsdb.com/th/job/12345",
        "https://th.indeed.com/viewjob?jk=abc",
    ],
)
def test_forbidden_urls_rejected(bad_url: str, tmp_path: Path) -> None:
    with pytest.raises(ForbiddenSourceError):
        validate_url(bad_url)

    with pytest.raises(ForbiddenSourceError):
        fetch_jobs(["123"], tmp_path, url_template=bad_url)


def test_delay_below_5_seconds_refused(tmp_path: Path) -> None:
    assert MIN_DELAY_SEC == 5.0
    with pytest.raises(ValueError):
        enforce_delay(4.99)
    with pytest.raises(ValueError):
        fetch_jobs(["101"], tmp_path, delay_sec=3.0)


# ---------------------------------------------------------------------------
# 2. Parsing Real JobThai HTML Files & PDPA PII Stripping (T1.2)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not SAMPLE_DIR.exists(), reason="spike/raw/jobthai not present in clean git clone")
def test_parse_at_least_20_real_jobthai_html_files() -> None:
    sample_files = sorted(SAMPLE_DIR.glob("job_*.html"))
    province_files = sorted(BY_PROVINCE_DIR.glob("job_*.html"))
    all_files = sample_files + province_files
    assert len(sample_files) >= 20
    assert len(all_files) >= 131

    expected_keys = {
        "source",
        "source_job_id",
        "source_url",
        "title",
        "description",
        "qualifications",
        "salary_text",
        "salary_min",
        "salary_max",
        "province",
        "district",
        "job_category",
        "industry",
        "employment_type",
        "date_posted",
        "valid_through",
        "company_name",
        "payload",
        "content_hash",
    }

    for fpath in all_files:
        rec = parse_file(fpath)
        assert rec is not None, f"Failed to parse {fpath.name}"
        assert set(rec.keys()) == expected_keys
        assert rec["source"] == "jobthai"
        assert rec["source_job_id"].isdigit()
        assert rec["source_url"] == f"https://www.jobthai.com/th/company/job/{rec['source_job_id']}"
        assert len(rec["content_hash"]) == 64
        assert rec["title"]
        assert rec["company_name"]

        # Verify zero HR contact keys anywhere in record or payload
        all_keys = _collect_all_keys(rec)
        assert not (all_keys & HR_CONTACT_KEYS), f"HR key leaked in {fpath.name}: {all_keys & HR_CONTACT_KEYS}"

        # Verify zero unredacted phone/email/LINE PII in non-URL text fields
        for field in ("title", "description", "qualifications", "salary_text", "company_name"):
            val = rec[field] or ""
            assert not _EMAIL_CHECK_RX.search(val), f"Email leaked in {fpath.name}.{field}: {val}"
            assert not _PHONE_CHECK_RX.search(val), f"Phone leaked in {fpath.name}.{field}: {val}"
            assert not _LINE_CHECK_RX.search(val), f"LINE ID leaked in {fpath.name}.{field}: {val}"

        for s in _collect_all_strings(rec["payload"]):
            if s.startswith(("http://", "https://")):
                assert not _EMAIL_CHECK_RX.search(s), f"Email in URL payload {fpath.name}: {s}"
            else:
                assert not _EMAIL_CHECK_RX.search(s), f"Email in payload {fpath.name}: {s}"
                assert not _PHONE_CHECK_RX.search(s), f"Phone in payload {fpath.name}: {s}"
                assert not _LINE_CHECK_RX.search(s), f"LINE ID in payload {fpath.name}: {s}"


def test_parse_at_least_20_synthetic_fixture_html_files() -> None:
    files = sorted(FIXTURE_POSTINGS_DIR.glob("job_*.html"))
    assert len(files) >= 20
    for fpath in files:
        rec = parse_file(fpath)
        assert rec is not None, f"Failed to parse {fpath.name}"
        assert rec["source"] == "jobthai"
        assert rec["source_job_id"].isdigit()
        assert not (_collect_all_keys(rec) & HR_CONTACT_KEYS)
        for field in ("title", "description", "qualifications", "salary_text", "company_name"):
            val = rec[field] or ""
            assert not _EMAIL_CHECK_RX.search(val)
            assert not _PHONE_CHECK_RX.search(val)
            assert not _LINE_CHECK_RX.search(val)


def test_parse_strips_all_hr_keys_and_inline_pii_from_ld_json() -> None:
    fake_ld = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": "Data Analyst โทร 081-234-5678",
        "description": "<p>วิเคราะห์ข้อมูลด้วย SQL และ Python ติดต่อ hr@company.co.th หรือ ID Line: @hrdata</p>",
        "qualifications": "ป.ตรี โทร +66 89 111 2233",
        "telephone": "02-123-4567",
        "email": "recruit@company.co.th",
        "faxNumber": "02-999-8888",
        "contact": "คุณสมชาย",
        "contactPoint": {"@type": "ContactPoint", "telephone": "0812345678", "email": "a@b.com"},
        "applicationContact": {"@type": "ContactPoint", "telephone": "0899999999"},
        "hiringOrganization": {
            "@type": "Organization",
            "name": "บริษัท ตัวอย่าง จำกัด",
            "telephone": "02-000-0000",
            "email": "org@company.co.th",
        },
        "jobLocation": {
            "@type": "Place",
            "address": {"@type": "PostalAddress", "addressRegion": "จังหวัดสงขลา", "addressLocality": "หาดใหญ่"},
        },
        "baseSalary": {
            "@type": "MonetaryAmount",
            "currency": "THB",
            "value": {"@type": "QuantitativeValue", "minValue": 25000, "maxValue": 35000, "unitText": "MONTH"},
        },
        "datePosted": "2026-11-18T10:00:00.000Z",
    }
    html = f"""
    <html>
      <head><link rel="canonical" href="https://www.jobthai.com/th/company/job/7778889" /></head>
      <body><script type="application/ld+json">{json.dumps(fake_ld, ensure_ascii=False)}</script></body>
    </html>
    """
    rec = parse_html(html)
    assert rec is not None
    assert rec["source_job_id"] == "7778889"
    assert rec["province"] == "สงขลา"
    assert rec["district"] == "หาดใหญ่"
    assert rec["salary_min"] == 25000.0
    assert rec["salary_max"] == 35000.0
    assert not (_collect_all_keys(rec) & HR_CONTACT_KEYS)
    serialized = json.dumps(rec, ensure_ascii=False)
    for leaked in ("081-234-5678", "02-123-4567", "hr@company.co.th", "recruit@company.co.th", "@hrdata", "คุณสมชาย", "89 111 2233"):
        assert leaked not in serialized


# ---------------------------------------------------------------------------
# 3. Polite Fetcher: Delay, Resume, and Immediate 403 / 429 / CAPTCHA Halt (T1.4)
# ---------------------------------------------------------------------------


def test_fetch_polite_delay_and_resume_skip(tmp_path: Path) -> None:
    existing = tmp_path / "job_1001.html"
    existing.write_text("<html>existing</html>", encoding="utf-8")

    requested_urls: list[str] = []
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(200, text=f"<html><body>job {request.url}</body></html>")

    store = StagingStore(sqlite_path=tmp_path / "staging.db")
    try:
        res = fetch_jobs(
            ["1001", "1002", "1003"],
            tmp_path,
            delay_sec=5.0,
            jitter_sec=1.0,
            store=store,
            transport=httpx.MockTransport(handler),
            sleep_fn=sleeps.append,
        )
        run = store.get_scrape_run(res["scrape_run_id"])
    finally:
        store.close()

    assert res["status"] == "done"
    assert res["n_skipped"] == 1
    assert res["n_fetched"] == 2
    assert res["requests_made"] == 2
    assert requested_urls == [
        "https://www.jobthai.com/th/company/job/1002",
        "https://www.jobthai.com/th/company/job/1003",
    ]
    assert len(sleeps) == 1
    assert all(s >= MIN_DELAY_SEC for s in sleeps)
    assert existing.read_text(encoding="utf-8") == "<html>existing</html>"
    assert (tmp_path / "job_1002.html").exists()
    assert (tmp_path / "job_1003.html").exists()
    assert run is not None
    assert run["status"] == "done"
    assert run["n_fetched"] == 2
    assert run["finished_at"] is not None


@pytest.mark.parametrize(
    ("block_code", "block_body", "expected_status"),
    [
        (403, "Forbidden", "stopped_403"),
        (429, "Too Many Requests", "stopped_429"),
        (200, "<html><body>Please verify CAPTCHA challenge</body></html>", "stopped_captcha"),
    ],
)
def test_fetch_halts_immediately_on_block_or_captcha(
    tmp_path: Path,
    block_code: int,
    block_body: str,
    expected_status: str,
) -> None:
    requested_urls: list[str] = []
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        if request.url.path.endswith("/2002"):
            return httpx.Response(block_code, text=block_body)
        return httpx.Response(200, text="<html>ok</html>")

    store = StagingStore(sqlite_path=tmp_path / "staging.db")
    try:
        res = fetch_jobs(
            ["2001", "2002", "2003", "2004", "2005"],
            tmp_path,
            delay_sec=5.0,
            jitter_sec=0.5,
            store=store,
            transport=httpx.MockTransport(handler),
            sleep_fn=sleeps.append,
        )
        run = store.get_scrape_run(res["scrape_run_id"])
    finally:
        store.close()

    assert res["status"] == expected_status
    assert res["stopped_at_job_id"] == "2002"
    assert res["n_fetched"] == 1
    # Must halt immediately at job 2002 without requesting 2003, 2004, 2005
    assert requested_urls == [
        "https://www.jobthai.com/th/company/job/2001",
        "https://www.jobthai.com/th/company/job/2002",
    ]
    assert (tmp_path / "job_2001.html").exists()
    assert not (tmp_path / "job_2002.html").exists()
    assert run is not None
    assert run["status"] == expected_status
    assert run["n_fetched"] == 1
    assert run["finished_at"] is not None


# ---------------------------------------------------------------------------
# 4. Discovery & Province x Category Planning (T1.3, T1.6)
# ---------------------------------------------------------------------------


def test_discovery_extracts_real_listing_html_and_category_targets(tmp_path: Path) -> None:
    listing_path = PROV_TEST_HTML if PROV_TEST_HTML.exists() else FIXTURE_LISTING_HTML
    expected_total = 4991 if PROV_TEST_HTML.exists() else 120
    html = listing_path.read_text(encoding="utf-8", errors="ignore")
    parsed = extract_listing_ids(html, stratum="p=59", seen_date="2026-11-18")
    assert parsed["total"] == expected_total
    assert len(parsed["job_ids"]) == 20
    assert len(parsed["records"]) == 20
    assert parsed["records"][0]["stratum"] == "p=59"
    assert parsed["records"][0]["seen_date"] == "2026-11-18"

    # Large provinces (Bangkok 01, Chonburi 09) expand into province x jobtype strata
    targets = build_discovery_targets(province_codes=["01", "09", "57"])
    bkk_targets = [t for t in targets if t["province_code"] == "01"]
    chon_targets = [t for t in targets if t["province_code"] == "09"]
    songkhla_targets = [t for t in targets if t["province_code"] == "57"]
    assert "01" in LARGE_PROVINCE_CODES and "09" in LARGE_PROVINCE_CODES
    assert len(bkk_targets) >= 40
    assert all("|c=" in t["stratum"] and "jobtype=" in t["url"] for t in bkk_targets)
    assert len(chon_targets) >= 40
    assert len(songkhla_targets) == 1
    assert songkhla_targets[0]["stratum"] == "p=57"

    # Offline discovery run persisting to staging.listing_seen
    store = StagingStore(sqlite_path=tmp_path / "staging.db")
    try:
        res = discover_targets(
            songkhla_targets,
            seen_date="2026-11-18",
            store=store,
            html_provider=lambda _t: html,
            sleep_fn=lambda _s: None,
        )
        summary = store.get_listing_seen_summary("jobthai")
    finally:
        store.close()

    assert res["status"] == "done"
    assert res["n_discovered"] == 20
    assert len(summary) == 20

    # Discovery also halts immediately on 429 / CAPTCHA
    store2 = StagingStore(sqlite_path=tmp_path / "staging_block.db")
    visited: list[str] = []
    try:
        def blocked_provider(target: dict[str, Any]) -> tuple[int, str]:
            visited.append(target["stratum"])
            if target["stratum"] == "p=02":
                return 429, "Too Many Requests"
            return 200, html

        res_block = discover_targets(
            build_discovery_targets(province_codes=["02", "03", "04"]),
            seen_date="2026-11-18",
            store=store2,
            html_provider=blocked_provider,
            sleep_fn=lambda _s: None,
        )
        run_block = store2.get_scrape_run(res_block["scrape_run_id"])
    finally:
        store2.close()

    assert res_block["status"] == "stopped_429"
    assert visited == ["p=02"]
    assert run_block is not None and run_block["status"] == "stopped_429"


def test_playwright_scroll_listing_uses_valid_selectors_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    import types

    from pipeline.scraper import config as scraper_config
    from pipeline.scraper.discovery import DiscoveryBlockedError, _playwright_scroll_listing

    # Verify every SELECTORS[...] lookup across all scraper modules exists in config.SELECTORS
    scraper_dir = REPO_ROOT / "pipeline" / "scraper"
    for py_file in sorted(scraper_dir.glob("*.py")):
        src = py_file.read_text(encoding="utf-8")
        for key in re.findall(r'SELECTORS\[["\']([^"\']+)["\']\]', src):
            assert key in scraper_config.SELECTORS, f"Missing SELECTORS[{key!r}] used in {py_file.name}"
            assert scraper_config.SELECTORS[key]

    evaluated_scripts: list[str] = []
    sleeps: list[float] = []
    pages_content = iter(
        [
            '<html><a href="/th/company/job/101">101</a></html>',
            '<html><a href="/th/company/job/101">101</a><a href="/th/company/job/102">102</a></html>',
            '<html><a href="/th/company/job/101">101</a><a href="/th/company/job/102">102</a></html>',
        ]
    )

    class FakeResp:
        status = 200

    class FakePage:
        def goto(self, url: str, wait_until: str = "domcontentloaded", timeout: int = 30000) -> FakeResp:
            return FakeResp()

        def content(self) -> str:
            return next(pages_content)

        def evaluate(self, script: str) -> None:
            evaluated_scripts.append(script)

        def wait_for_timeout(self, ms: int) -> None:
            return None

    class FakeContext:
        def new_page(self) -> FakePage:
            return FakePage()

        def close(self) -> None:
            return None

    class FakeBrowser:
        def new_context(self, user_agent: str = "") -> FakeContext:
            return FakeContext()

        def close(self) -> None:
            return None

    class FakeChromium:
        def launch(self, headless: bool = True) -> FakeBrowser:
            return FakeBrowser()

    class FakePlaywrightCM:
        def __enter__(self) -> Any:
            return types.SimpleNamespace(chromium=FakeChromium())

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            return None

    fake_sync_api = types.ModuleType("playwright.sync_api")
    fake_sync_api.sync_playwright = lambda: FakePlaywrightCM()  # type: ignore[attr-defined]
    fake_pw = types.ModuleType("playwright")
    fake_pw.sync_api = fake_sync_api  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "playwright", fake_pw)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", fake_sync_api)

    collected = _playwright_scroll_listing(
        "https://www.jobthai.com/th/jobs?province=57",
        max_scrolls=5,
        delay_sec=5.0,
        sleep_fn=sleeps.append,
    )
    assert len(collected) == 3
    assert evaluated_scripts == [str(scraper_config.SELECTORS["load_more_trigger"])] * 2
    assert all(s >= MIN_DELAY_SEC for s in sleeps)

    # Also verify blocked Playwright response raises DiscoveryBlockedError immediately
    pages_content_blocked = iter(['<html><body>cf-challenge captcha</body></html>'])
    FakePage.content = lambda self: next(pages_content_blocked)  # type: ignore[method-assign]
    with pytest.raises(DiscoveryBlockedError) as exc_info:
        _playwright_scroll_listing(
            "https://www.jobthai.com/th/jobs?province=57",
            delay_sec=5.0,
            sleep_fn=sleeps.append,
        )
    assert exc_info.value.status == "stopped_captcha"


# ---------------------------------------------------------------------------
# 5. Stratified Quota & Exact Weight Conservation (T1.7, D13)
# ---------------------------------------------------------------------------


def test_quota_stratification_and_exact_weight_conservation() -> None:
    totals_csv = PROVINCE_TOTALS_CSV if PROVINCE_TOTALS_CSV.exists() else FIXTURE_PROVINCE_TOTALS_CSV
    strata = load_province_totals(totals_csv)
    assert len(strata) == len(JOBTHAI_PROVINCES) == 79
    assert {r["code"] for r in strata} == set(JOBTHAI_PROVINCES.keys())

    plan = compute_stratified_quota(strata, n_target=6000, min_per_stratum=5)
    by_code = {r["code"]: r for r in plan}

    # Check floor & boundary cases from province_totals.csv
    assert by_code["25"]["N_h"] == 0 and by_code["25"]["n_h"] == 0  # นราธิวาส
    assert by_code["44"]["N_h"] == 2 and by_code["44"]["n_h"] == 2  # แม่ฮ่องสอน
    assert by_code["58"]["N_h"] == 3 and by_code["58"]["n_h"] == 3  # สตูล
    assert by_code["46"]["N_h"] == 5 and by_code["46"]["n_h"] == 5  # ยะลา
    assert by_code["01"]["n_h"] > 1000  # กรุงเทพฯ proportional share

    # Verify exact formula n_h = min(N_h, max(5, round(n_target * N_h / N_total)))
    n_total = sum(r["N_h"] for r in strata)
    for r in plan:
        if r["N_h"] == 0:
            assert r["n_h"] == 0
            assert r["sample_weight"] == 0.0
        else:
            expected_n_h = min(r["N_h"], max(5, round(6000 * r["N_h"] / n_total)))
            assert r["n_h"] == expected_n_h
            assert r["sample_weight"] == pytest.approx(r["N_h"] / expected_n_h)

    # Simulate discovered IDs matching N_h and verify sum(sample_weight in h) == N_h
    discovered = {
        r["stratum"]: [f"{r['code']}_{i}" for i in range(r["N_h"])]
        for r in plan
        if r["N_h"] > 0
    }
    sampled = select_stratified_sample(discovered, plan, seed=42)
    check = verify_weight_conservation(plan, sampled)
    assert check["passed"] is True
    assert check["failures"] == []

    # Direct per-stratum sum check
    weights_by_stratum: dict[str, float] = {}
    for row in sampled:
        st = row["sample_stratum"]
        weights_by_stratum[st] = weights_by_stratum.get(st, 0.0) + row["sample_weight"]
    for r in plan:
        if r["N_h"] > 0:
            assert weights_by_stratum[r["stratum"]] == pytest.approx(r["N_h"], rel=1e-9, abs=1e-9)


# ---------------------------------------------------------------------------
# 6. Staging Loader Deduplication (T1.5)
# ---------------------------------------------------------------------------


def test_load_staging_deduplication_fixtures(tmp_path: Path) -> None:
    db_path = tmp_path / "staging_fix.db"
    jsonl_path = tmp_path / "staging_fix.jsonl"
    store = StagingStore(sqlite_path=db_path)
    try:
        first = load_raw_directory([FIXTURE_POSTINGS_DIR], store=store, jsonl_out=jsonl_path)
        second = load_raw_directory([FIXTURE_POSTINGS_DIR], store=store)
        total_in_db = store.count_job_postings("jobthai")
    finally:
        store.close()

    assert first["files_scanned"] == 21
    assert first["parsed"] == 21
    assert first["inserted"] == 21
    assert second["inserted"] == 0
    assert second["duplicates"] == 21
    assert total_in_db == 21
    assert jsonl_path.exists()


@pytest.mark.skipif(not SAMPLE_DIR.exists(), reason="spike/raw/jobthai not present in clean git clone")
def test_load_staging_deduplication(tmp_path: Path) -> None:
    db_path = tmp_path / "staging.db"
    jsonl_path = tmp_path / "staging_clean.jsonl"
    store = StagingStore(sqlite_path=db_path)
    try:
        first = load_raw_directory([SAMPLE_DIR], store=store, jsonl_out=jsonl_path)
        second = load_raw_directory([SAMPLE_DIR], store=store)
        total_in_db = store.count_job_postings("jobthai")
    finally:
        store.close()

    assert first["files_scanned"] == 21
    assert first["parsed"] == 21
    assert first["inserted"] == 21
    assert first["duplicates"] == 0
    assert second["inserted"] == 0
    assert second["duplicates"] == 21
    assert second["total_rows"] == 21
    assert total_in_db == 21
    assert jsonl_path.exists()
    assert len(jsonl_path.read_text(encoding="utf-8").splitlines()) == 21

    # Load all 131 HTML files across sample + by_province (some job IDs appear in both dirs)
    distinct_filenames = {
        p.name for p in list(SAMPLE_DIR.glob("job_*.html")) + list(BY_PROVINCE_DIR.glob("job_*.html"))
    }
    store_all = StagingStore(sqlite_path=tmp_path / "staging_all.db")
    try:
        res_all_1 = load_raw_directory([SAMPLE_DIR, BY_PROVINCE_DIR], store=store_all)
        res_all_2 = load_raw_directory([SAMPLE_DIR, BY_PROVINCE_DIR], store=store_all)
        assert res_all_1["files_scanned"] == 131
        assert res_all_1["parsed"] == 131
        assert res_all_1["total_rows"] == len(distinct_filenames) == 126
        assert res_all_1["inserted"] == 126
        assert res_all_1["duplicates"] == 5
        assert res_all_2["inserted"] == 0
        assert res_all_2["duplicates"] == 131
        assert res_all_2["total_rows"] == 126
    finally:
        store_all.close()


# ---------------------------------------------------------------------------
# 7. Weekly Re-discovery Without Re-fetching Existing Detail Pages (T1.10, D14)
# ---------------------------------------------------------------------------


def test_weekly_rediscovery_updates_last_seen_without_refetching(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    listing_path = PROV_TEST_HTML if PROV_TEST_HTML.exists() else FIXTURE_LISTING_HTML
    listing_week1 = listing_path.read_text(encoding="utf-8", errors="ignore")
    week1_parsed = extract_listing_ids(listing_week1, stratum="p=59")
    week1_ids = week1_parsed["job_ids"]
    assert len(week1_ids) == 20

    # Week 2 listing keeps all 20 existing IDs plus 3 brand-new IDs
    new_ids = ["9990001", "9990002", "9990003"]
    listing_week2 = listing_week1 + "".join(
        f'<a href="/th/company/job/{jid}">new {jid}</a>' for jid in new_ids
    )
    targets = [{"province_code": "59", "stratum": "p=59", "url": "https://www.jobthai.com/th/jobs?province=59"}]

    requested_detail_ids: list[str] = []

    def detail_handler(request: httpx.Request) -> httpx.Response:
        jid = request.url.path.rsplit("/", 1)[-1]
        requested_detail_ids.append(jid)
        ld = {
            "@context": "https://schema.org",
            "@type": "JobPosting",
            "title": f"Job {jid}",
            "description": "SQL Python",
            "hiringOrganization": {"@type": "Organization", "name": "Demo Co"},
            "jobLocation": {"@type": "Place", "address": {"@type": "PostalAddress", "addressRegion": "สมุทรปราการ"}},
            "datePosted": "2026-11-25",
        }
        return httpx.Response(
            200,
            text=f'<html><script type="application/ld+json">{json.dumps(ld)}</script></html>',
        )

    store = StagingStore(sqlite_path=tmp_path / "staging.db")
    try:
        # Week 1: rediscovery sees 20 IDs -> simulate those 20 jobs fetched to disk & staging
        w1 = run_weekly_rediscovery(
            targets,
            store=store,
            raw_dir=raw_dir,
            seen_date="2026-11-18",
            n_target_new=100,
            html_provider=lambda _t: listing_week1,
            sleep_fn=lambda _s: None,
            fetch_new=False,
        )
        assert w1["n_discovered"] == 20
        assert w1["n_new_discovered"] == 20

        # Persist Week 1 existing detail HTML files and staging records
        for jid in week1_ids:
            (raw_dir / f"job_{jid}.html").write_text("<html>saved</html>", encoding="utf-8")
        store.upsert_job_postings(
            [
                {
                    "source": "jobthai",
                    "source_job_id": jid,
                    "source_url": f"https://www.jobthai.com/th/company/job/{jid}",
                    "title": f"Existing {jid}",
                    "payload": {"@type": "JobPosting"},
                    "content_hash": f"hash_{jid}",
                }
                for jid in week1_ids
            ]
        )

        # Week 2: rediscovery runs on listing only and fetches ONLY newly discovered IDs
        w2 = run_weekly_rediscovery(
            targets,
            store=store,
            raw_dir=raw_dir,
            seen_date="2026-11-25",
            n_target_new=100,
            html_provider=lambda _t: listing_week2,
            sleep_fn=lambda _s: None,
            fetch_new=True,
            fetch_transport=httpx.MockTransport(detail_handler),
        )
    finally:
        store.close()

    assert w2["n_discovered"] == 23
    assert w2["n_existing_seen"] == 20
    assert w2["n_new_discovered"] == 3
    assert sorted(w2["queued_job_ids"]) == new_ids

    # Existing IDs must NEVER be re-fetched
    assert sorted(requested_detail_ids) == new_ids
    assert not (set(requested_detail_ids) & set(week1_ids))

    # first_seen remains Week 1 while last_seen advances to Week 2
    summary = w2["seen_summary"]
    for existing_id in week1_ids:
        assert summary[existing_id]["first_seen"] == "2026-11-18"
        assert summary[existing_id]["last_seen"] == "2026-11-25"
        assert summary[existing_id]["n_seen_runs"] == 2
    for nid in new_ids:
        assert summary[nid]["first_seen"] == "2026-11-25"
        assert summary[nid]["last_seen"] == "2026-11-25"
        assert summary[nid]["n_seen_runs"] == 1


# ---------------------------------------------------------------------------
# 8. JobBKK Secondary Source Harvester (T1.9, T8.6 — 100% Offline Tests)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not JOBBKK_SAMPLE_HTML.exists(), reason="spike/raw/jobbkk not present in clean git clone")
def test_jobbkk_parse_real_sample_and_scrubs_pii() -> None:
    from pipeline.scraper.config import USER_AGENT

    assert "academic-noncommercial" in USER_AGENT.lower()
    sample_html = REPO_ROOT / "spike" / "raw" / "jobbkk" / "job_sample.html"
    rec = parse_file(sample_html, source="jobbkk")
    assert rec is not None
    assert rec["source"] == "jobbkk"
    assert rec["source_job_id"] == "1110990"
    assert rec["source_url"] == "https://www.jobbkk.com/jobs/detail/35638/1110990"
    assert rec["province"] == "สมุทรปราการ"
    assert rec["district"] == "บางเสาธง"
    assert rec["salary_min"] == 16000.0
    assert rec["salary_max"] == 20000.0
    assert rec["date_posted"] == "2026-11-18"
    assert rec["valid_through"] == "2027-03-26"

    serialized = json.dumps(rec, ensure_ascii=False)
    for leaked in ("thanakorn_n@toagroup.com", "sa28ku", "062-132-2174", "02-335-5670", "คุณธนกร"):
        assert leaked not in serialized
    assert not (_collect_all_keys(rec) & HR_CONTACT_KEYS)


def test_jobbkk_parse_synthetic_fixture_and_scrubs_pii() -> None:
    rec = parse_file(FIXTURE_JOBBKK_SAMPLE_HTML, source="jobbkk")
    assert rec is not None
    assert rec["source"] == "jobbkk"
    assert rec["source_job_id"] == "1110990"
    assert rec["province"] == "สมุทรปราการ"
    assert rec["salary_min"] == 20000.0
    serialized = json.dumps(rec, ensure_ascii=False)
    for leaked in ("081-000-0000", "fake@example.com", "hr@example.com", "@fakeid", "02-000-0000"):
        assert leaked not in serialized
    assert not (_collect_all_keys(rec) & HR_CONTACT_KEYS)


def test_jobbkk_listing_extraction_and_schedule() -> None:
    from pipeline.scraper.jobbkk_harvest import (
        build_jobbkk_schedule,
        extract_jobbkk_listing_targets,
    )

    south_path = JOBBKK_SOUTH_HTML if JOBBKK_SOUTH_HTML.exists() else FIXTURE_JOBBKK_LISTING_HTML
    south_html = south_path.read_text(encoding="utf-8", errors="ignore")
    parsed = extract_jobbkk_listing_targets(south_html, stratum="jobbkk|region=southern", seen_date="2026-11-18")
    assert len(parsed["targets"]) == 9
    assert parsed["targets"][0]["detail_url"].startswith("https://www.jobbkk.com/jobs/detail/")
    assert all(t["source"] == "jobbkk" and t["source_job_id"].isdigit() for t in parsed["targets"])

    schedule = build_jobbkk_schedule(max_pages=2)
    assert len(schedule) > 20
    assert all("jobbkk.com" in s["url"] for s in schedule)


def test_jobbkk_harvest_polite_delay_resume_and_jsonl_logs(tmp_path: Path) -> None:
    from pipeline.scraper.jobbkk_harvest import run_jobbkk_batch

    south_path = JOBBKK_SOUTH_HTML if JOBBKK_SOUTH_HTML.exists() else FIXTURE_JOBBKK_LISTING_HTML
    sample_path = JOBBKK_SAMPLE_HTML if JOBBKK_SAMPLE_HTML.exists() else FIXTURE_JOBBKK_SAMPLE_HTML
    south_html = south_path.read_text(encoding="utf-8", errors="ignore")
    sample_html = sample_path.read_text(encoding="utf-8", errors="ignore")

    # Delay < 5.0 must be refused
    with pytest.raises(ValueError):
        run_jobbkk_batch(out_dir=tmp_path, min_delay=4.5)

    # Pre-existing job 1306297 on disk must be skipped on resume
    (tmp_path / "job_1306297.html").write_text(sample_html, encoding="utf-8")

    requested_urls: list[str] = []
    sleeps: list[float] = []

    def listing_provider(_target: dict[str, Any]) -> tuple[int, str]:
        return 200, south_html

    def detail_handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(200, text=sample_html)

    res = run_jobbkk_batch(
        max_jobs=3,
        min_listings_per_batch=1,
        max_listings_per_batch=1,
        out_dir=tmp_path,
        min_delay=5.2,
        max_delay=5.8,
        batch_label="test_b1",
        seed=42,
        listing_provider=listing_provider,
        detail_transport=httpx.MockTransport(detail_handler),
        sleep_fn=sleeps.append,
    )

    assert res["status"] == "done"
    assert res["concurrency"] == 1
    assert res["n_fetched"] == 3
    assert res["n_parsed_clean"] == 3
    assert res["n_with_salary"] == 3
    assert len(requested_urls) == 3
    assert all("1306297" not in u for u in requested_urls)
    # Sleep called BEFORE EVERY request (1 listing + 3 detail = 4)
    assert len(sleeps) == 4
    assert all(s >= 5.2 for s in sleeps)

    assert (tmp_path / "listing_seen.jsonl").exists()
    assert (tmp_path / "scrape_runs.jsonl").exists()
    runs = [
        json.loads(line)
        for line in (tmp_path / "scrape_runs.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(runs) == 1 and runs[0]["status"] == "done"


@pytest.mark.parametrize(
    ("block_code", "block_body", "expected_status"),
    [
        (403, "Forbidden", "stopped_403"),
        (429, "Too Many Requests", "stopped_429"),
        (200, "<html><body>Please solve CAPTCHA</body></html>", "stopped_captcha"),
    ],
)
def test_jobbkk_harvest_halts_immediately_on_block_or_captcha(
    tmp_path: Path,
    block_code: int,
    block_body: str,
    expected_status: str,
) -> None:
    from pipeline.scraper.jobbkk_harvest import run_jobbkk_batch

    south_path = JOBBKK_SOUTH_HTML if JOBBKK_SOUTH_HTML.exists() else FIXTURE_JOBBKK_LISTING_HTML
    sample_path = JOBBKK_SAMPLE_HTML if JOBBKK_SAMPLE_HTML.exists() else FIXTURE_JOBBKK_SAMPLE_HTML
    south_html = south_path.read_text(encoding="utf-8", errors="ignore")
    sample_html = sample_path.read_text(encoding="utf-8", errors="ignore")

    requested_urls: list[str] = []
    sleeps: list[float] = []

    def detail_handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        if len(requested_urls) == 2:
            return httpx.Response(block_code, text=block_body)
        return httpx.Response(200, text=sample_html)

    res = run_jobbkk_batch(
        max_jobs=5,
        min_listings_per_batch=1,
        max_listings_per_batch=1,
        out_dir=tmp_path,
        min_delay=5.2,
        max_delay=5.5,
        seed=42,
        listing_provider=lambda _t: (200, south_html),
        detail_transport=httpx.MockTransport(detail_handler),
        sleep_fn=sleeps.append,
    )

    assert res["status"] == expected_status
    assert res["n_fetched"] == 1
    assert len(requested_urls) == 2
    runs = [
        json.loads(line)
        for line in (tmp_path / "scrape_runs.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert runs[-1]["status"] == expected_status
