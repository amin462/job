"""JobThai harvester: bulk first, then keep collecting new postings slowly.

State lives in one SQLite file, so you can stop (Ctrl+C) and start again any time. A restart
continues the current round: listings already scanned in it are skipped, and if all of them
were scanned it goes straight to the job pages (table `meta`, see run_rounds).

Commands
  python -X utf8 scraper/jobthai_harvester.py run       # loop forever: discover -> fetch -> sleep
  python -X utf8 scraper/jobthai_harvester.py discover  # one pass over province x jobtype listings
  python -X utf8 scraper/jobthai_harvester.py fetch     # fetch details for all pending job ids
  python -X utf8 scraper/jobthai_harvester.py stats     # progress summary
  python -X utf8 scraper/jobthai_harvester.py export    # write data/jobthai_jobs.csv + .jsonl

Options (env vars): JT_DELAY=5 (seconds between requests, min 5 per AGENTS.md), JT_DB=data/jobthai.sqlite,
  JT_REDISCOVER_HOURS=12 (how often `run` rescans listings for new postings),
  JT_EMPTY_RESCAN_DAYS=3 (listings that had 0 postings are rescanned only this often)

Also kept (no extra requests): N_h per listing, each job's province/job type and a few
listing flags (urgent, near BTS/MRT, industrial estate, ...), and from the job page the
number of positions and the salary text -> stored in jsonld under "x_jobthai".

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
from html.parser import HTMLParser
from datetime import datetime, timedelta, timezone

import requests

DELAY = max(5.0, float(os.environ.get("JT_DELAY", "5")))  # AGENTS.md: >= 5 s
DB = os.environ.get("JT_DB", "data/jobthai.sqlite")
REDISCOVER_HOURS = float(os.environ.get("JT_REDISCOVER_HOURS", "12"))
EMPTY_RESCAN_DAYS = float(os.environ.get("JT_EMPTY_RESCAN_DAYS", "3"))
JITTER = 1.0  # seconds of random extra wait on top of DELAY (DELAY itself never goes below 5 s)
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
    CREATE TABLE IF NOT EXISTS ref (kind TEXT, id TEXT, name TEXT, PRIMARY KEY (kind, id));
    CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);  -- round state, see run_rounds
    """)
    # added 2026-11-21 for stratified sampling: N_h per listing + each job's own stratum
    for table, column in (("listing", "total INTEGER"), ("job", "province_id TEXT"), ("job", "jobtype_id TEXT"),
                          ("job", "listing_meta TEXT")):
        have = {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
        if column.split()[0] not in have:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {column}")
    con.commit()
    return con


def polite_get(url):
    """GET with delay; returns text or None (404/expired). Pauses on blocks."""
    global blocks_in_a_row
    time.sleep(DELAY + random.uniform(0, JITTER))
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


LISTING_DATA = re.compile(r'\{"data":\{"total":\d+,"data":\[')


def _ref_id(obj):
    """{'id': '59', 'name': 'สมุทรปราการ'} -> ('59', 'สมุทรปราการ'); missing -> (None, None)."""
    if not isinstance(obj, dict) or obj.get("id") in (None, ""):
        return None, None
    return str(obj["id"]), obj.get("name")


def listing_flags(item):
    """Small, non-personal facts the listing shows for a job (no company name, no address)."""
    tags = " ".join(str(t) for t in (item.get("tags") or [])).lower()
    industrial = item.get("industrial") or {}
    disabled = item.get("disabledPerson") or {}
    return {
        "urgent": bool((item.get("urgent") or {}).get("id")),
        "updated_at": item.get("updatedAt"),
        "near_transit": bool(item.get("transitStations")),
        "industrial_estate": industrial.get("name") if industrial.get("id") else None,
        "disabled_person": disabled.get("name"),
        "online_interview": "online" in tags or "ออนไลน์" in tags,
        "district_id": str((item.get("district") or {}).get("id") or "") or None,
        "salary_text_listing": item.get("salary"),
        # every field the listing shows for this job (company-level only, no personal data)
        "listing": scrub_obj(item),
    }


def parse_listing(body):
    """Read one listing page (no extra request).

    Returns (total, jobs, refs, flags):
      total = how many postings match this listing's filter (N_h for the stratum),
      jobs  = [(job_id, province_id, jobtype_id)] - each job's own province and job type,
      refs  = {('province'|'jobtype', id): name},
      flags = {job_id: listing_flags(...)}.
    Company names and other fields are ignored.
    """
    total, jobs, refs, flags = None, [], {}, {}
    m = LISTING_DATA.search(body)
    if m:
        try:
            data = json.JSONDecoder().raw_decode(body, m.start())[0]["data"]
            total = int(data["total"])
            for item in data.get("data") or []:
                if not isinstance(item, dict) or item.get("id") is None:
                    continue
                prov, prov_name = _ref_id(item.get("province"))
                jt, jt_name = _ref_id(item.get("jobType"))
                if prov:
                    refs[("province", prov)] = prov_name
                if jt:
                    refs[("jobtype", jt)] = jt_name
                jobs.append((str(item["id"]), prov, jt))
                flags[str(item["id"])] = listing_flags(item)
        except (ValueError, KeyError, TypeError):
            total, jobs, refs, flags = None, [], {}, {}
    if total is None:
        mt = re.search(r'"total"\s*:\s*(\d+)', body)
        total = int(mt.group(1)) if mt else None
    known = {j for j, _, _ in jobs}
    for jid in dict.fromkeys(re.findall(r"/th/company/job/(\d+)", body)):
        if jid not in known:
            jobs.append((jid, None, None))
    return total, jobs, refs, flags


# --- rounds ---------------------------------------------------------------------------------
# One round = scan the listings (discover) -> fetch the new job pages -> export -> pause.
# Table `meta` remembers how far the current round got, so a harvester that is restarted
# (crash, sleep, reboot, closed window) continues that round instead of starting over:
#   round_started  discover of this round began; rows scanned after it count as done
#   discover_done  discover finished             -> after a restart go straight to fetch
#   round_done     fetch + export finished       -> after a restart wait out the pause
# Shared with jobbkk_harvester.py (same keys in its own SQLite file).

def meta_get(con, key):
    row = con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row[0] if row else None


def meta_set(con, **values):
    for key, value in values.items():
        if value is None:
            con.execute("DELETE FROM meta WHERE key=?", (key,))
        else:
            con.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?,?)", (key, value))
    con.commit()


def local_time(ts):
    """UTC timestamp written by now() -> local 'YYYY-MM-DD HH:MM' for log lines."""
    return f"{datetime.fromisoformat(ts).astimezone():%Y-%m-%d %H:%M}"


def begin_discover(con):
    """Continue the round whose discover was cut off, or start a new round.
    Returns (round_started, resumed)."""
    started = meta_get(con, "round_started")
    if started and not meta_get(con, "discover_done"):
        return started, True
    started = now()
    meta_set(con, round_started=started, discover_done=None, round_done=None)
    return started, False


def next_step(con, rediscover_hours, at=None):
    """What `run` does first: ("discover", 0), ("fetch", 0) or ("wait", seconds left)."""
    if not meta_get(con, "round_started") or not meta_get(con, "discover_done"):
        return "discover", 0.0
    done = meta_get(con, "round_done")
    if not done:
        return "fetch", 0.0
    at = at or datetime.now(timezone.utc)
    left = rediscover_hours * 3600 - (at - datetime.fromisoformat(done)).total_seconds()
    return ("wait", left) if left > 0 else ("discover", 0.0)


def run_rounds(con, discover_fn, fetch_fn, export_fn, stats_fn, rediscover_hours, log_fn):
    """The `run` loop of both harvesters, resuming the current round after a restart."""
    while True:
        step, left = next_step(con, rediscover_hours)
        if step == "wait":
            log_fn(f"last round finished {local_time(meta_get(con, 'round_done'))}; "
                   f"next round in {left / 3600:.1f} h")
            time.sleep(left)
            continue
        if step == "fetch":
            log_fn(f"listings of the round started {local_time(meta_get(con, 'round_started'))} "
                   "were all scanned before the restart - continuing with job pages")
        else:
            discover_fn(con)
        fetch_fn(con)
        export_fn(con)
        stats_fn(con)
        meta_set(con, round_done=now())
        log_fn(f"round done - sleeping {rediscover_hours} h before the next round")
        time.sleep(rediscover_hours * 3600)


def discover(con):
    load_listing_urls(con)
    started, resumed = begin_discover(con)
    # listings still missing their total (N_h) first, then the least recently scanned;
    # listings already scanned in this round (before a restart) are not requested again
    rows = con.execute(
        "SELECT url, total, last_scanned FROM listing ORDER BY (total IS NULL) DESC, COALESCE(last_scanned,'') ASC"
    ).fetchall()
    if resumed:
        todo = [r for r in rows if (r[2] or "") < started]
        log(f"continuing the round started {local_time(started)}: {len(rows) - len(todo)} listings already "
            f"scanned, {len(todo)} to go")
        rows = todo
    # listings that were empty (N_h = 0) a short while ago are not worth a request every round
    empty_cutoff = (datetime.now(timezone.utc) - timedelta(days=EMPTY_RESCAN_DAYS)).isoformat(timespec="seconds")
    new_total = skipped = 0
    for i, (url, last_total, last_scanned) in enumerate(rows, 1):
        if last_total == 0 and last_scanned and last_scanned > empty_cutoff:
            skipped += 1
            continue
        body = polite_get(url)
        if body is None:
            continue
        total, jobs, refs, flags = parse_listing(body)
        t = now()
        for jid, prov, jt in jobs:
            meta = json.dumps(flags[jid], ensure_ascii=False) if jid in flags else None
            cur = con.execute(
                "UPDATE job SET last_seen=?, province_id=COALESCE(?, province_id), "
                "jobtype_id=COALESCE(?, jobtype_id), listing_meta=COALESCE(?, listing_meta) WHERE job_id=?",
                (t, prov, jt, meta, jid),
            )
            if cur.rowcount == 0:
                con.execute(
                    "INSERT INTO job(job_id, first_seen, last_seen, seen_in, province_id, jobtype_id, listing_meta) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (jid, t, t, url, prov, jt, meta),
                )
                new_total += 1
        con.executemany("INSERT OR REPLACE INTO ref(kind, id, name) VALUES (?,?,?)",
                        [(k, rid, name) for (k, rid), name in refs.items()])
        con.execute("UPDATE listing SET last_scanned=?, last_count=?, total=COALESCE(?, total) WHERE url=?",
                    (t, len(jobs), total, url))
        con.commit()
        if i % 10 == 0:
            log(f"discover {i}/{len(rows)} listings | new ids so far {new_total}")
    con.commit()
    meta_set(con, discover_done=now())
    log(f"discover done: {new_total} new job ids ({skipped} recently empty listings skipped)")


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


class _JobFields(HTMLParser):
    """Text of every element whose id starts with "job-" (nested markup handled);
    "job-card-*" are other postings shown on the page and are skipped."""

    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.open, self.fields = [], [], {}

    def handle_starttag(self, tag, attrs):
        if tag in self.VOID:
            return
        self.stack.append(tag)
        el_id = dict(attrs).get("id") or ""
        if (el_id.startswith("job-") and not el_id.startswith("job-card-")
                and not re.search(r"-\d+$", el_id)  # job-position-3, job-detail-1987020 = other postings
                and el_id not in self.fields):
            self.fields[el_id] = []
            self.open.append((el_id, len(self.stack)))

    def handle_endtag(self, tag):
        if tag in self.VOID or tag not in self.stack:
            return
        while self.stack:
            if self.stack.pop() == tag:
                break
        self.open = [(k, d) for k, d in self.open if d <= len(self.stack)]

    def handle_data(self, data):
        for k, _ in self.open:
            self.fields[k].append(data)
EMAIL_RX = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RX = re.compile(r"(?<!\d)(?:\+?66[\s-]?|0)\d{1,2}[\s-]?\d{3}[\s-]?\d{3,4}(?!\d)")
LINE_RX = re.compile(r"(?i)(line\s*(?:id)?\s*[:：]?\s*)@?[\w.-]{3,}")


def scrub_text(text):
    """PDPA: drop e-mail addresses, phone numbers and LINE ids from free text."""
    if not isinstance(text, str):
        return text
    text = EMAIL_RX.sub("[email]", text)
    text = LINE_RX.sub(r"\1[line]", text)
    return PHONE_RX.sub("[phone]", text)


def scrub_obj(o):
    if isinstance(o, dict):
        return {k: scrub_obj(v) for k, v in o.items() if k not in PII_KEYS}
    if isinstance(o, list):
        return [scrub_obj(v) for v in o]
    return scrub_text(o)


def parse_detail_extras(html):
    """All job-* fields of the job page (salary text, positions, update date, company
    detail, directions, ...) as plain text, PDPA-scrubbed; positions also as a number."""
    parser = _JobFields()
    try:
        parser.feed(html)
    except Exception:  # never let one odd page stop the harvest
        pass
    out = {}
    for key, parts in parser.fields.items():
        name = key[4:].replace("-", "_")  # job-number-of-position -> number_of_position
        if name == "title":
            continue
        text = re.sub(r"\s+", " ", " ".join(parts)).strip()
        if text:
            out[name] = scrub_text(text)
    if "number_of_position" in out:
        out["positions_text"] = out.pop("number_of_position")
        m = re.search(r"\d+", out["positions_text"].replace(",", ""))
        out["positions"] = int(m.group()) if m else None
    if "salary" in out:
        out["salary_text"] = out.pop("salary")
    if "detail" in out:
        out["company_detail"] = out.pop("detail")   # "about the company" block
    if "direction" in out:
        out["directions"] = out.pop("direction")    # how to get there (transport), scrubbed
    return out


def strip_pii(o):
    if isinstance(o, dict):
        return {k: strip_pii(v) for k, v in o.items() if k not in PII_KEYS}
    if isinstance(o, list):
        return [strip_pii(v) for v in o]
    return o


def fetch(con, limit=None):
    q = ("SELECT job_id FROM job WHERE status='pending' OR (status='error' AND attempts<3) "
         # rows fetched before 2026-11-21 lack x_jobthai -> fetch again so all rows have the same columns
         "OR (status='ok' AND instr(COALESCE(jsonld,''), '\"x_jobthai\"') = 0) "
         "ORDER BY (status='ok') DESC, first_seen DESC")
    ids = [r[0] for r in con.execute(q).fetchall()][: limit or None]
    log(f"fetching {len(ids)} job pages (about {len(ids) * DELAY * 1.25 / 3600:.1f} h)")
    for i, jid in enumerate(ids, 1):
        html = polite_get(f"https://www.jobthai.com/th/company/job/{jid}")
        was_ok = con.execute("SELECT status FROM job WHERE job_id=?", (jid,)).fetchone()[0] == "ok"
        rec = extract_jobposting(html) if html is not None else None
        if rec is None and was_ok:
            # re-fetch failed (posting closed): keep the data we already have, mark the extras unavailable
            con.execute("UPDATE job SET jsonld=json_set(jsonld, '$.x_jobthai', json('{\"unavailable\": true}')), "
                        "attempts=attempts+1 WHERE job_id=?", (jid,))
        elif html is None:
            con.execute("UPDATE job SET status='gone', attempts=attempts+1 WHERE job_id=?", (jid,))
        else:
            if rec:
                fill_stratum_from_posting(con, jid, rec)
                row = con.execute("SELECT listing_meta FROM job WHERE job_id=?", (jid,)).fetchone()
                listing_meta = json.loads(row[0]) if row and row[0] else {}
                rec["x_jobthai"] = {**listing_meta, **parse_detail_extras(html)}
                con.execute("UPDATE job SET status='ok', fetched_at=?, jsonld=?, attempts=attempts+1 WHERE job_id=?",
                            (now(), json.dumps(rec, ensure_ascii=False), jid))
            else:
                con.execute("UPDATE job SET status='error', attempts=attempts+1 WHERE job_id=?", (jid,))
        if i % 20 == 0:
            con.commit()
            log(f"fetch {i}/{len(ids)}")
    con.commit()


def fill_stratum_from_posting(con, jid, rec):
    """Province / job type ids from the posting's own addressRegion / occupationalCategory names
    (for ids found before listing data was kept, or seen only as links)."""
    loc = rec.get("jobLocation") or {}
    loc = loc[0] if isinstance(loc, list) and loc else loc
    region = ((loc or {}).get("address") or {}).get("addressRegion")
    cat = rec.get("occupationalCategory")
    cat = cat[0] if isinstance(cat, list) and cat else cat
    pid = con.execute("SELECT id FROM ref WHERE kind='province' AND name=?", (region,)).fetchone()
    tid = con.execute("SELECT id FROM ref WHERE kind='jobtype' AND name=?", (cat,)).fetchone()
    con.execute("UPDATE job SET province_id=COALESCE(province_id, ?), jobtype_id=COALESCE(jobtype_id, ?) "
                "WHERE job_id=?", (pid[0] if pid else None, tid[0] if tid else None, jid))


def stats(con):
    print(dict(con.execute("SELECT status, COUNT(*) FROM job GROUP BY status").fetchall()))
    print("listings scanned:", con.execute("SELECT COUNT(*) FROM listing WHERE last_scanned IS NOT NULL").fetchone()[0],
          "/", con.execute("SELECT COUNT(*) FROM listing").fetchone()[0])
    print("listings with total (N_h):", con.execute("SELECT COUNT(*) FROM listing WHERE total IS NOT NULL").fetchone()[0],
          "| jobs with province+jobtype:",
          con.execute("SELECT COUNT(*) FROM job WHERE province_id IS NOT NULL AND jobtype_id IS NOT NULL").fetchone()[0])


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
        "positions": (rec.get("x_jobthai") or {}).get("positions"),
        "salary_text": (rec.get("x_jobthai") or {}).get("salary_text"),
        "urgent": (rec.get("x_jobthai") or {}).get("urgent"),
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
    run_rounds(con, discover, fetch, export, stats, REDISCOVER_HOURS, log)


def keep_awake():
    """Ask Windows not to go to sleep while this process runs (released automatically on exit).
    Same request a video player makes; it does not change any power setting. Closing the
    laptop lid can still put it to sleep."""
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)  # CONTINUOUS | SYSTEM_REQUIRED
        except Exception:
            pass


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "run":
        keep_awake()
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
