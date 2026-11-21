"""Tests for pipeline.scraper.import_sqlite (harvester SQLite -> staging).

Builds small fake harvester DBs with the same schema as scraper/jobthai_harvester.py
and scraper/jobbkk_harvester.py; fully offline.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline.scraper.import_sqlite import (  # noqa: E402
    import_source,
    jobbkk_stratum,
    jobthai_stratum,
    to_bangkok_date,
)
from pipeline.scraper.load_staging import StagingStore  # noqa: E402
from pipeline.scraper.parse import HR_CONTACT_KEYS  # noqa: E402

JOBTHAI_DDL = """
CREATE TABLE listing (url TEXT PRIMARY KEY, last_scanned TEXT, last_count INTEGER);
CREATE TABLE job (
    job_id TEXT PRIMARY KEY, first_seen TEXT, last_seen TEXT, seen_in TEXT,
    status TEXT DEFAULT 'pending', fetched_at TEXT, attempts INTEGER DEFAULT 0, jsonld TEXT);
"""
JOBBKK_DDL = """
CREATE TABLE province (name TEXT PRIMARY KEY, total INTEGER, last_page INTEGER DEFAULT 0, last_scanned TEXT);
CREATE TABLE job (
    job_key TEXT PRIMARY KEY, first_seen TEXT, last_seen TEXT, seen_in TEXT,
    status TEXT DEFAULT 'pending', fetched_at TEXT, attempts INTEGER DEFAULT 0, jsonld TEXT);
"""


def _posting(title: str, extra: dict | None = None) -> str:
    item = {
        "@context": "http://schema.org",
        "@type": "JobPosting",
        "title": title,
        "datePosted": "2026-11-19T06:08:52.000Z",
        "description": "<p>ดูแลบัญชี ใช้ Excel และ SAP โทร 081-234-5678 หรือ hr@example.com</p>",
        "hiringOrganization": {"@type": "Organization", "name": "บริษัท ตัวอย่าง จำกัด"},
        "jobLocation": {"@type": "Place", "address": {"addressRegion": "สงขลา", "addressLocality": "หาดใหญ่"}},
        "baseSalary": {"@type": "MonetaryAmount", "currency": "THB",
                       "value": {"@type": "QuantitativeValue", "minValue": 15000, "maxValue": 20000, "unitText": "MONTH"}},
        # The harvester already drops these, but the importer must not trust that.
        "contactPoint": {"telephone": "074-123456", "email": "boss@example.com"},
    }
    item.update(extra or {})
    return json.dumps(item, ensure_ascii=False)


def _make_jobthai_db(path: Path) -> None:
    con = sqlite3.connect(path)
    con.executescript(JOBTHAI_DDL)
    con.executemany(
        "INSERT INTO job (job_id, first_seen, last_seen, seen_in, status, jsonld) VALUES (?,?,?,?,?,?)",
        [
            # 18:36 UTC on 18 Nov = 01:36 on 19 Nov in Bangkok
            ("1001", "2026-11-18T18:36:42+00:00", "2026-11-21T05:00:00+00:00",
             "https://www.jobthai.com/th/jobs?province=15&jobtype=14", "ok", _posting("นักบัญชี")),
            ("1002", "2026-11-19T04:00:00+00:00", "2026-11-19T04:00:00+00:00",
             "https://www.jobthai.com/th/jobs?province=01", "pending", None),
            ("1003", "2026-11-19T04:00:00+00:00", "2026-11-19T04:00:00+00:00",
             "https://www.jobthai.com/th/jobs?province=01", "error", None),
            ("1004", "2026-11-19T04:00:00+00:00", "2026-11-19T04:00:00+00:00",
             "https://www.jobthai.com/th/jobs?province=90&jobtype=3", "ok", "{not json"),
        ],
    )
    con.commit()
    con.close()


def _make_jobbkk_db(path: Path) -> None:
    con = sqlite3.connect(path)
    con.executescript(JOBBKK_DDL)
    con.executemany(
        "INSERT INTO job (job_key, first_seen, last_seen, seen_in, status, jsonld) VALUES (?,?,?,?,?,?)",
        [
            ("49548/1269049", "2026-11-18T18:32:02+00:00", "2026-11-18T18:46:58+00:00",
             "กรุงเทพมหานคร", "ok", _posting("โปรแกรมเมอร์")),
            ("33657/519392", "2026-11-18T18:32:02+00:00", "2026-11-18T18:46:58+00:00",
             "กรุงเทพมหานคร", "pending", None),
        ],
    )
    con.commit()
    con.close()


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _keys(obj) -> set[str]:
    if isinstance(obj, dict):
        out = {str(k).lower() for k in obj}
        for v in obj.values():
            out |= _keys(v)
        return out
    if isinstance(obj, list):
        out: set[str] = set()
        for v in obj:
            out |= _keys(v)
        return out
    return set()


def test_helpers() -> None:
    assert to_bangkok_date("2026-11-18T18:36:42+00:00") == "2026-11-19"
    assert to_bangkok_date("2026-11-19T04:00:00Z") == "2026-11-19"
    assert to_bangkok_date(None) is None
    assert jobthai_stratum("https://www.jobthai.com/th/jobs?province=15&jobtype=14") == "p=15|c=14"
    assert jobthai_stratum("https://www.jobthai.com/th/jobs?province=01") == "p=01"
    assert jobthai_stratum(None) == "unknown"
    assert jobbkk_stratum("สงขลา") == "jobbkk|p=สงขลา|c=ทั้งหมด"


def test_import_jobthai_listing_seen_postings_and_pii(tmp_path: Path) -> None:
    harvester = tmp_path / "jobthai.sqlite"
    _make_jobthai_db(harvester)
    before = _digest(harvester)

    with StagingStore(sqlite_path=tmp_path / "staging.db") as store:
        counts = import_source(store, harvester, "jobthai")

        assert counts["jobs"] == 4
        assert counts["ok"] == 2 and counts["parsed"] == 1 and counts["parse_failed"] == 1
        assert counts["not_fetched"] == 1 and counts["errors"] == 1
        assert counts["inserted"] == 1

        # every job id (fetched or not) is in listing_seen, with Thai-time first/last seen
        summary = store.get_listing_seen_summary("jobthai")
        assert set(summary) == {"1001", "1002", "1003", "1004"}
        assert summary["1001"]["first_seen"] == "2026-11-19"
        assert summary["1001"]["last_seen"] == "2026-11-21"
        assert summary["1001"]["stratum"] == "p=15|c=14"
        assert summary["1002"]["stratum"] == "p=01"

        con = store._sqlite_conn
        row = con.execute("SELECT * FROM job_posting_raw").fetchone()
        assert row["source_url"] == "https://www.jobthai.com/th/company/job/1001"
        assert row["province"] and row["salary_min"] == 15000
        payload = json.loads(row["payload"])
        assert not (_keys(payload) & HR_CONTACT_KEYS)
        for text in (row["description"], row["payload"]):
            assert "081-234-5678" not in text and "hr@example.com" not in text
            assert "074-123456" not in text and "boss@example.com" not in text

    # the harvester file is opened read-only and never changed
    assert _digest(harvester) == before


def test_reimport_is_idempotent_and_moves_last_seen(tmp_path: Path) -> None:
    harvester = tmp_path / "jobthai.sqlite"
    _make_jobthai_db(harvester)
    with StagingStore(sqlite_path=tmp_path / "staging.db") as store:
        import_source(store, harvester, "jobthai")
        con = store._sqlite_conn
        n_runs = con.execute("SELECT COUNT(*) FROM scrape_run").fetchone()[0]
        n_seen = con.execute("SELECT COUNT(*) FROM listing_seen").fetchone()[0]
        assert n_runs == 3 and n_seen == 8

        # harvester sees the posting again later (rediscovery)
        h = sqlite3.connect(harvester)
        h.execute("UPDATE job SET last_seen='2026-11-28T03:00:00+00:00' WHERE job_id='1001'")
        h.commit()
        h.close()

        again = import_source(store, harvester, "jobthai")
        assert again["inserted"] == 0 and again["duplicates"] == 1
        assert again["listing_seen_new"] == 0
        assert con.execute("SELECT COUNT(*) FROM scrape_run").fetchone()[0] == n_runs
        assert con.execute("SELECT COUNT(*) FROM listing_seen").fetchone()[0] == n_seen
        assert con.execute("SELECT COUNT(*) FROM job_posting_raw").fetchone()[0] == 1
        summary = store.get_listing_seen_summary("jobthai")
        assert summary["1001"]["first_seen"] == "2026-11-19"
        assert summary["1001"]["last_seen"] == "2026-11-28"


def test_import_jobbkk_uses_job_id_and_detail_url(tmp_path: Path) -> None:
    harvester = tmp_path / "jobbkk.sqlite"
    _make_jobbkk_db(harvester)
    with StagingStore(sqlite_path=tmp_path / "staging.db") as store:
        counts = import_source(store, harvester, "jobbkk")
        assert counts["jobs"] == 2 and counts["inserted"] == 1
        row = store._sqlite_conn.execute("SELECT source, source_job_id, source_url FROM job_posting_raw").fetchone()
        assert tuple(row) == ("jobbkk", "1269049", "https://www.jobbkk.com/jobs/detail/49548/1269049")
        summary = store.get_listing_seen_summary("jobbkk")
        assert set(summary) == {"1269049", "519392"}
        assert summary["519392"]["stratum"] == "jobbkk|p=กรุงเทพมหานคร|c=ทั้งหมด"


# ---------------------------------------------------------------------------
# N_h (T1.7): listing totals + each job's own province x job type
# ---------------------------------------------------------------------------
import csv  # noqa: E402
import importlib  # noqa: E402

LISTING_BODY = (
    '<script>{"ROOT_QUERY":{"searchJobs({\\"filter\\":{\\"province\\":\\"57\\",\\"jobtype\\":\\"4\\"}})":'
    '{"data":{"total":137,"data":['
    '{"id":2001,"companyID":1,"jobTitle":"x","companyName":"ACME","province":{"id":"57","name":"สงขลา"},'
    '"jobType":{"id":4,"name":"งานขาย"},"urgent":{"id":1,"name":"รับสมัครด่วน"},'
    '"transitStations":[{"id":1,"name":"BTS"}],"tags":["Online Interview"],"district":{"id":"5701","name":"x"},'
    '"salary":"15,000 - 20,000 บาท","updatedAt":"2026-11-21T01:00:00.000Z"},'
    '{"id":2002,"companyID":2,"jobTitle":"y","companyName":"B","province":{"id":"57","name":"สงขลา"},'
    '"jobType":{"id":28,"name":"งานวิศวกรรม"}}'
    ']}}}}</script><a href="/th/company/job/2003">z</a>'
)


def _harvester():
    sys.path.insert(0, str(REPO_ROOT / "scraper"))
    return importlib.import_module("jobthai_harvester")


def test_parse_listing_reads_total_and_each_jobs_stratum() -> None:
    total, jobs, refs, flags = _harvester().parse_listing(LISTING_BODY)
    assert total == 137
    assert jobs == [("2001", "57", "4"), ("2002", "57", "28"), ("2003", None, None)]
    assert refs[("province", "57")] == "สงขลา" and refs[("jobtype", "4")] == "งานขาย"
    f = flags["2001"]
    assert f["urgent"] is True and f["near_transit"] is True and f["online_interview"] is True
    assert f["district_id"] == "5701" and f["salary_text_listing"] == "15,000 - 20,000 บาท"
    assert flags["2002"]["urgent"] is False and "2003" not in flags
    # the full listing record is kept (company-level data is not personal data) ...
    assert f["listing"]["companyName"] == "ACME" and f["listing"]["jobType"]["id"] == 4
    # ... but company names never end up in the stratum/category tables
    assert "ACME" not in repr((jobs, refs))
    assert _harvester().parse_listing("<html>no data</html>") == (None, [], {}, {})


def test_parse_detail_extras_positions_and_salary_text() -> None:
    h = _harvester()
    html = ('<img alt="number of positions icon"/><span>อัตรา</span></div>'
            '<span id="job-number-of-position" class="text-base">2 อัตรา</span>'
            '<span id="job-salary" class="x">ตามโครงสร้างบริษัทฯ</span>')
    assert h.parse_detail_extras(html) == {
        "positions_text": "2 อัตรา", "positions": 2, "salary_text": "ตามโครงสร้างบริษัทฯ"}
    many = '<span id="job-number-of-position">หลายอัตรา</span>'
    assert h.parse_detail_extras(many) == {"positions_text": "หลายอัตรา", "positions": None}
    assert h.parse_detail_extras("<html></html>") == {}


def test_discover_skips_recently_empty_listings(tmp_path: Path, monkeypatch) -> None:
    h = _harvester()
    db = tmp_path / "jobthai.sqlite"
    monkeypatch.setattr(h, "DB", str(db))
    con = h.db()
    fresh = h.now()
    con.executemany("INSERT INTO listing(url, last_scanned, total) VALUES (?,?,?)", [
        ("https://www.jobthai.com/th/jobs?province=25&jobtype=38", fresh, 0),          # empty, just scanned -> skip
        ("https://www.jobthai.com/th/jobs?province=25&jobtype=37", "2026-01-01T00:00:00+00:00", 0),  # empty, old
        ("https://www.jobthai.com/th/jobs?province=57&jobtype=4", fresh, 137),        # has postings
    ])
    con.commit()
    asked = []
    monkeypatch.setattr(h, "polite_get", lambda url: asked.append(url) or LISTING_BODY)
    h.discover(con)
    assert "https://www.jobthai.com/th/jobs?province=25&jobtype=38" not in asked
    assert len(asked) == 2
    row = con.execute("SELECT province_id, jobtype_id, listing_meta FROM job WHERE job_id='2001'").fetchone()
    assert row[0] == "57" and row[1] == "4" and json.loads(row[2])["urgent"] is True
    con.close()


def test_harvester_db_upgrades_old_schema_in_place(tmp_path: Path, monkeypatch) -> None:
    old = tmp_path / "jobthai.sqlite"
    _make_jobthai_db(old)  # schema from before 2026-11-21
    h = _harvester()
    monkeypatch.setattr(h, "DB", str(old))
    con = h.db()
    assert "total" in {r[1] for r in con.execute("PRAGMA table_info(listing)")}
    assert {"province_id", "jobtype_id", "listing_meta"} <= {r[1] for r in con.execute("PRAGMA table_info(job)")}
    assert con.execute("SELECT COUNT(*) FROM job").fetchone()[0] == 4  # data kept
    con.close()


def _make_jobthai_db_with_totals(path: Path, *, all_provinces: bool) -> None:
    _make_jobthai_db(path)
    h = _harvester()
    h.DB = str(path)
    con = h.db()
    con.executemany(
        "INSERT INTO listing(url, last_scanned, last_count, total) VALUES (?,?,?,?)",
        [
            ("https://www.jobthai.com/th/jobs?province=15&jobtype=14", "2026-11-21T08:00:00+00:00", 20, 40),
            ("https://www.jobthai.com/th/jobs?province=15&jobtype=3", "2026-11-21T08:00:00+00:00", 0, 0),
            ("https://www.jobthai.com/th/jobs?province=15", "2026-11-21T08:00:00+00:00", 20, 40),
            ("https://www.jobthai.com/th/jobs?province=01", "2026-11-21T08:00:00+00:00", 20,
             17848 if all_provinces else None),
        ],
    )
    con.execute("UPDATE job SET province_id='15', jobtype_id='14' WHERE job_id IN ('1001','1004')")
    con.executemany("INSERT INTO ref VALUES (?,?,?)",
                    [("province", "15", "ฉะเชิงเทรา"), ("province", "01", "กรุงเทพมหานคร"), ("jobtype", "14", "งานบัญชี")])
    con.commit()
    con.close()


def test_import_uses_jobs_own_stratum_and_exports_n_h(tmp_path: Path) -> None:
    from pipeline.scraper.import_sqlite import export_jobthai_strata

    harvester = tmp_path / "jobthai.sqlite"
    _make_jobthai_db_with_totals(harvester, all_provinces=True)
    with StagingStore(sqlite_path=tmp_path / "staging.db") as store:
        import_source(store, harvester, "jobthai")
        summary = store.get_listing_seen_summary("jobthai")
    assert summary["1001"]["stratum"] == "p=15|c=14"   # from its own province/job type
    assert summary["1002"]["stratum"] == "p=01"        # unknown yet -> where it was seen

    out = tmp_path / "processed"
    res = export_jobthai_strata(harvester, out)
    assert res["strata"] == 2 and res["strata_N"] == 40 and res["strata_empty"] == 1
    assert res["provinces"] == 2 and "jobthai_province_totals.csv" in res["files"]
    with (out / "jobthai_strata.csv").open(encoding="utf-8-sig") as fh:
        rows = {r["stratum"]: r for r in csv.DictReader(fh)}
    assert rows["p=15|c=14"]["N_h"] == "40"
    assert rows["p=15|c=14"]["n_seen"] == "2" and rows["p=15|c=14"]["n_fetched"] == "2"
    assert rows["p=15|c=14"]["jobtype"] == "งานบัญชี"
    with (out / "jobthai_province_totals.csv").open(encoding="utf-8-sig") as fh:
        prov = {r["code"]: r for r in csv.DictReader(fh)}
    assert prov["01"]["total"] == "17848" and prov["01"]["province"] == "กรุงเทพมหานคร"

    # the ETL reads this file format directly
    from pipeline.etl.load_dw import load_province_population
    pop = load_province_population(out / "jobthai_province_totals.csv")
    assert pop.get("กรุงเทพมหานคร") == 17848


def test_province_totals_not_written_until_every_province_has_a_total(tmp_path: Path) -> None:
    from pipeline.scraper.import_sqlite import export_jobthai_strata

    harvester = tmp_path / "jobthai.sqlite"
    _make_jobthai_db_with_totals(harvester, all_provinces=False)
    res = export_jobthai_strata(harvester, tmp_path / "processed")
    assert res["listings_without_total"] == {"strata": 0, "provinces": 1}
    assert res["files"] == ["jobthai_strata.csv"]
    assert not (tmp_path / "processed" / "jobthai_province_totals.csv").exists()


def test_pdpa_scrub_of_extra_text_fields() -> None:
    h = _harvester()
    t = h.scrub_text("ติดต่อ 081-234-5678, 02 123 4567, hr@abc.co.th, Line ID: hr_abc เงินเดือน 15,000 บาท 2026-11-18")
    assert "081" not in t and "123 4567" not in t and "hr@abc" not in t and "hr_abc" not in t
    assert "15,000" in t and "2026-11-18" in t
    item = {"companyName": "X", "telephone": "081", "contactPoint": {"email": "a@b.co"}, "workLocation": "โทร 0812345678"}
    clean = h.scrub_obj(item)
    assert "telephone" not in clean and "contactPoint" not in clean and "0812345678" not in clean["workLocation"]


def test_detail_extras_skip_other_postings_on_the_page() -> None:
    h = _harvester()
    html = ('<div id="job-detail"><p>บริษัทผลิต <b>อาหาร</b></p><p>โทร 081-111-2222</p></div>'
            '<span id="job-number-of-position">3 อัตรา</span>'
            '<div id="job-position-1"><span>งานอื่น</span></div>'
            '<a id="job-detail-1987020">ดูรายละเอียดงาน</a>'
            '<span id="job-card-title-5">x</span>')
    out = h.parse_detail_extras(html)
    assert out["company_detail"] == "บริษัทผลิต อาหาร โทร [phone]"
    assert out["positions"] == 3
    assert not any(k.startswith(("position_", "detail_", "card_")) for k in out)
