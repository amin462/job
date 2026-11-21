"""JobThai harvester: bulk first, then keep collecting new postings slowly.

State lives in one SQLite file, so you can stop (Ctrl+C) and start again any time.

Commands
  python -X utf8 scraper/jobthai_harvester.py run       # loop forever: discover -> fetch -> sleep
  python -X utf8 scraper/jobthai_harvester.py discover  # one pass over province x jobtype listings
  python -X utf8 scraper/jobthai_harvester.py fetch     # fetch details for all pending job ids
  python -X utf8 scraper/jobthai_harvester.py stats     # progress summary
  python -X utf8 scraper/jobthai_harvester.py export    # write data/jobthai_jobs.csv + .jsonl

Options (env vars): JT_DELAY=5 (seconds between requests, min 5 per AGENTS.md), JT_DB=data/jobthai.sqlite,
  JT_REDISCOVER_HOURS=12 (how often `run` rescans listings for new postings)

Rules this script follows: only paths allowed by robots.txt, one request at a time,
fixed delay + jitter, pause 60 min on HTTP 403/429/CAPTCHA and stop after 3 blocks in a row,
no contact data stored (phone/e-mail/contact person are dropped), no raw HTML kept.
Use for study only; do not republish posting text (JobThai terms).
"""
import csv
import json
import os
import random
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone

import requests

DELAY = max(5.0, float(os.environ.get("JT_DELAY", "5")))  # AGENTS.md: >= 5 s
DB = os.environ.get("JT_DB", "data/jobthai.sqlite")
REDISCOVER_HOURS = float(os.environ.get("JT_REDISCOVER_HOURS", "12"))
UA = "Mozilla/5.0 (compatible; student-capstone-research/1.0)"
SITEMAPS = [
    "https://www.jobthai.com/sitemap/location-and-jobtype/th/1.xml",
    "https://www.jobthai.com/sitemap/location/th/1.xml",
]
PII_KEYS = {"telephone", "email", "contactPoint", "applicationContact"}
NEXT_S = re.compile(r'\(self\.__next_s=self\.__next_s\|\|\[\]\)\.push\(\[0,(\{.*?\})\]\)</script>', re.S)
LD_TAG = re.compile(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.S)

session = requests.Session()
session.headers["User-Agent"] = UA
blocks_in_a_row = 0


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log(msg):
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    print(line, flush=True)
    with open(os.path.join(os.path.dirname(DB) or ".", "harvester.log"), "a", encoding="utf-8") as f:
        f.write(line + "\n")


def db():
    os.makedirs(os.path.dirname(DB) or ".", exist_ok=True)
    con = sqlite3.connect(DB)
    con.executescript("""
    CREATE TABLE IF NOT EXISTS listing (url TEXT PRIMARY KEY, last_scanned TEXT, last_count INTEGER);
    CREATE TABLE IF NOT EXISTS job (
        job_id TEXT PRIMARY KEY, first_seen TEXT, last_seen TEXT, seen_in TEXT,
        status TEXT DEFAULT 'pending',            -- pending | ok | gone | error
        fetched_at TEXT, attempts INTEGER DEFAULT 0, jsonld TEXT);
    CREATE INDEX IF NOT EXISTS job_status ON job(status);
    """)
    return con


def polite_get(url):
    """GET with delay; returns text or None (404/expired). Pauses on blocks."""
    global blocks_in_a_row
    time.sleep(DELAY + random.uniform(0, DELAY * 0.5))
    try:
        r = session.get(url, timeout=40)
    except requests.RequestException as e:
        log(f"network error {e.__class__.__name__} on {url}; waiting 5 min")
        time.sleep(300)
        return None
    blocked = r.status_code in (403, 429) or "captcha" in r.text[:5000].lower()
    if blocked:
        blocks_in_a_row += 1
        if blocks_in_a_row >= 3:
            log("blocked 3 times in a row - stopping. Wait a day and lower the speed (JT_DELAY).")
            sys.exit(2)
        log(f"blocked (HTTP {r.status_code}) - pausing 60 min")
        time.sleep(3600)
        return None
    blocks_in_a_row = 0
    if r.status_code == 404:
        return None
    if r.status_code >= 500:
        log(f"server error {r.status_code} on {url}; waiting 2 min")
        time.sleep(120)
        return None
    return r.text


def load_listing_urls(con):
    if con.execute("SELECT COUNT(*) FROM listing").fetchone()[0]:
        return
    urls = set()
    for sm in SITEMAPS:
        body = polite_get(sm) or ""
        for loc in re.findall(r"<loc>([^<]*)</loc>", body):
            loc = loc.replace("&amp;", "&")
            if "province=" in loc:
                urls.add(loc)
    con.executemany("INSERT OR IGNORE INTO listing(url) VALUES (?)", [(u,) for u in sorted(urls)])
    con.commit()
    log(f"loaded {len(urls)} listing urls (province, province x jobtype)")


def discover(con):
    load_listing_urls(con)
    rows = con.execute("SELECT url FROM listing ORDER BY COALESCE(last_scanned,'') ASC").fetchall()
    new_total = 0
    for i, (url,) in enumerate(rows, 1):
        body = polite_get(url)
        if body is None:
            continue
        ids = list(dict.fromkeys(re.findall(r"/th/company/job/(\d+)", body)))
        t = now()
        for jid in ids:
            cur = con.execute("UPDATE job SET last_seen=? WHERE job_id=?", (t, jid))
            if cur.rowcount == 0:
                con.execute("INSERT INTO job(job_id, first_seen, last_seen, seen_in) VALUES (?,?,?,?)", (jid, t, t, url))
                new_total += 1
        con.execute("UPDATE listing SET last_scanned=?, last_count=? WHERE url=?", (t, len(ids), url))
        con.commit()
        if i % 10 == 0:
            log(f"discover {i}/{len(rows)} listings | new ids so far {new_total}")
    con.commit()
    log(f"discover done: {new_total} new job ids")


def extract_jobposting(html):
    raws = []
    for m in NEXT_S.finditer(html):
        try:
            o = json.loads(m.group(1))
            if o.get("type") == "application/ld+json":
                raws.append(o.get("children", ""))
        except json.JSONDecodeError:
            pass
    raws += [m.group(1) for m in LD_TAG.finditer(html)]
    for raw in raws:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for item in data if isinstance(data, list) else [data]:
            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                return strip_pii(item)
    return None


def strip_pii(o):
    if isinstance(o, dict):
        return {k: strip_pii(v) for k, v in o.items() if k not in PII_KEYS}
    if isinstance(o, list):
        return [strip_pii(v) for v in o]
    return o


def fetch(con, limit=None):
    q = "SELECT job_id FROM job WHERE status='pending' OR (status='error' AND attempts<3) ORDER BY first_seen DESC"
    ids = [r[0] for r in con.execute(q).fetchall()][: limit or None]
    log(f"fetching {len(ids)} job pages (about {len(ids) * DELAY * 1.25 / 3600:.1f} h)")
    for i, jid in enumerate(ids, 1):
        html = polite_get(f"https://www.jobthai.com/th/company/job/{jid}")
        if html is None:
            con.execute("UPDATE job SET status='gone', attempts=attempts+1 WHERE job_id=?", (jid,))
        else:
            rec = extract_jobposting(html)
            if rec:
                con.execute("UPDATE job SET status='ok', fetched_at=?, jsonld=?, attempts=attempts+1 WHERE job_id=?",
                            (now(), json.dumps(rec, ensure_ascii=False), jid))
            else:
                con.execute("UPDATE job SET status='error', attempts=attempts+1 WHERE job_id=?", (jid,))
        if i % 20 == 0:
            con.commit()
            log(f"fetch {i}/{len(ids)}")
    con.commit()


def stats(con):
    print(dict(con.execute("SELECT status, COUNT(*) FROM job GROUP BY status").fetchall()))
    print("listings scanned:", con.execute("SELECT COUNT(*) FROM listing WHERE last_scanned IS NOT NULL").fetchone()[0],
          "/", con.execute("SELECT COUNT(*) FROM listing").fetchone()[0])


def flat(rec):
    loc = rec.get("jobLocation") or {}
    loc = loc[0] if isinstance(loc, list) and loc else loc
    addr = (loc or {}).get("address") or {}
    sal = (rec.get("baseSalary") or {}).get("value") or {}
    return {
        "title": rec.get("title"), "company": (rec.get("hiringOrganization") or {}).get("name"),
        "province": addr.get("addressRegion"), "district": addr.get("addressLocality"),
        "occupational_category": rec.get("occupationalCategory"), "industry": rec.get("industry"),
        "employment_type": rec.get("employmentType"), "date_posted": (rec.get("datePosted") or "")[:10],
        "valid_through": (rec.get("validThrough") or "")[:10], "salary_min": sal.get("minValue"),
        "salary_max": sal.get("maxValue"), "salary_unit": sal.get("unitText"),
        "description": rec.get("description"), "qualifications": rec.get("qualifications"),
    }


def export(con):
    os.makedirs("data", exist_ok=True)
    rows = con.execute("SELECT job_id, first_seen, last_seen, jsonld FROM job WHERE status='ok'").fetchall()
    with open("data/jobthai_jobs.jsonl", "w", encoding="utf-8") as fj, \
         open("data/jobthai_jobs.csv", "w", encoding="utf-8-sig", newline="") as fc:
        w = None
        for jid, fs, ls, js in rows:
            rec = json.loads(js)
            fj.write(json.dumps({"job_id": jid, "first_seen": fs, "last_seen": ls, **rec}, ensure_ascii=False) + "\n")
            row = {"job_id": jid, "first_seen": fs, "last_seen": ls, **flat(rec)}
            if w is None:
                w = csv.DictWriter(fc, fieldnames=list(row))
                w.writeheader()
            w.writerow(row)
    log(f"exported {len(rows)} postings to data/jobthai_jobs.csv and .jsonl")


def run_forever(con):
    while True:
        discover(con)
        fetch(con)
        export(con)
        stats(con)
        log(f"sleeping {REDISCOVER_HOURS} h before the next round")
        time.sleep(REDISCOVER_HOURS * 3600)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    con = db()
    try:
        {"run": run_forever, "discover": discover, "fetch": fetch, "stats": stats, "export": export}[cmd](con)
    except KeyboardInterrupt:
        con.commit()
        log("stopped by user - progress saved, run again to continue")
    except SystemExit:
        raise
    except Exception:
        import traceback
        con.commit()
        log("CRASH:\n" + traceback.format_exc())
        sys.exit(1)
