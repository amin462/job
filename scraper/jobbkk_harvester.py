"""JobBKK harvester: Playwright walks province listing pages to find job ids,
then plain HTTP fetches each job page and keeps its schema.org JobPosting.

State: data/jobbkk.sqlite (stop with Ctrl+C any time, run again to continue).

Commands
  python -X utf8 scraper/jobbkk_harvester.py run       # loop forever: discover -> fetch -> export -> sleep
  python -X utf8 scraper/jobbkk_harvester.py discover  # walk all province listing pages once
  python -X utf8 scraper/jobbkk_harvester.py fetch     # fetch pending job pages
  python -X utf8 scraper/jobbkk_harvester.py stats
  python -X utf8 scraper/jobbkk_harvester.py export    # data/jobbkk_jobs.csv + .jsonl

Env: BK_DELAY=5 (seconds, min 5 per AGENTS.md), BK_DB=data/jobbkk.sqlite, BK_REDISCOVER_HOURS=24,
     BK_MAX_PAGES=0 (0 = all pages per province; e.g. 5 for a quick test)
Needs: pip install playwright requests && python -m playwright install chromium

Same rules as the JobThai harvester: one request at a time with delay + jitter, pause
60 min on 403/429/challenge pages and stop after 3 in a row, contact data dropped,
no raw HTML kept, study use only (JobBKK terms forbid commercial copying).
"""
import json
import os
import random
import re
import sqlite3
import sys
import time
from urllib.parse import quote

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jobthai_harvester import extract_jobposting, flat, now  # noqa: E402

DELAY = max(5.0, float(os.environ.get("BK_DELAY", "5")))  # AGENTS.md: >= 5 s
DB = os.environ.get("BK_DB", "data/jobbkk.sqlite")
REDISCOVER_HOURS = float(os.environ.get("BK_REDISCOVER_HOURS", "24"))
MAX_PAGES = int(os.environ.get("BK_MAX_PAGES", "0"))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36 student-capstone-research/1.0"
PROVINCES = (
    "กรุงเทพมหานคร กระบี่ กาญจนบุรี กาฬสินธุ์ กำแพงเพชร ขอนแก่น จันทบุรี ฉะเชิงเทรา ชลบุรี ชัยนาท ชัยภูมิ ชุมพร "
    "เชียงราย เชียงใหม่ ตรัง ตราด ตาก นครนายก นครปฐม นครพนม นครราชสีมา นครศรีธรรมราช นครสวรรค์ นนทบุรี นราธิวาส "
    "น่าน บึงกาฬ บุรีรัมย์ ปทุมธานี ประจวบคีรีขันธ์ ปราจีนบุรี ปัตตานี พระนครศรีอยุธยา พะเยา พังงา พัทลุง พิจิตร "
    "พิษณุโลก เพชรบุรี เพชรบูรณ์ แพร่ ภูเก็ต มหาสารคาม มุกดาหาร แม่ฮ่องสอน ยโสธร ยะลา ร้อยเอ็ด ระนอง ระยอง ราชบุรี "
    "ลพบุรี ลำปาง ลำพูน เลย ศรีสะเกษ สกลนคร สงขลา สตูล สมุทรปราการ สมุทรสงคราม สมุทรสาคร สระแก้ว สระบุรี สิงห์บุรี "
    "สุโขทัย สุพรรณบุรี สุราษฎร์ธานี สุรินทร์ หนองคาย หนองบัวลำภู อ่างทอง อำนาจเจริญ อุดรธานี อุตรดิตถ์ อุทัยธานี อุบลราชธานี"
).split()
if os.environ.get("BK_PROVINCES"):  # e.g. BK_PROVINCES=สงขลา,ยะลา for a test run
    PROVINCES = [p.strip() for p in os.environ["BK_PROVINCES"].split(",") if p.strip()]
PER_PAGE = 25

http = requests.Session()
http.headers["User-Agent"] = UA
blocks = 0


def log(msg):
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} [jobbkk] {msg}"
    print(line, flush=True)
    with open(os.path.join(os.path.dirname(DB) or ".", "harvester_jobbkk.log"), "a", encoding="utf-8") as f:
        f.write(line + "\n")


def db():
    os.makedirs(os.path.dirname(DB) or ".", exist_ok=True)
    con = sqlite3.connect(DB)
    con.executescript("""
    CREATE TABLE IF NOT EXISTS province (name TEXT PRIMARY KEY, total INTEGER, last_page INTEGER DEFAULT 0, last_scanned TEXT);
    CREATE TABLE IF NOT EXISTS job (
        job_key TEXT PRIMARY KEY,                -- company_id/job_id
        first_seen TEXT, last_seen TEXT, seen_in TEXT,
        status TEXT DEFAULT 'pending', fetched_at TEXT, attempts INTEGER DEFAULT 0, jsonld TEXT);
    CREATE INDEX IF NOT EXISTS bk_status ON job(status);
    """)
    con.executemany("INSERT OR IGNORE INTO province(name) VALUES (?)", [(p,) for p in PROVINCES])
    con.commit()
    return con


def blocked_text(title, body):
    t = (title + " " + body[:3000]).lower()
    return "just a moment" in t or "captcha" in t or "access denied" in t or "attention required" in t


def on_block(where):
    global blocks
    blocks += 1
    if blocks >= 3:
        log("blocked 3 times in a row - stopping. Wait a day and raise BK_DELAY.")
        sys.exit(2)
    log(f"blocked at {where} - pausing 60 min")
    time.sleep(3600)


def pause():
    time.sleep(DELAY + random.uniform(0, DELAY * 0.5))


def discover(con):
    global blocks
    from playwright.sync_api import sync_playwright
    new_total = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=UA, viewport={"width": 1366, "height": 900})
        provs = [r[0] for r in con.execute("SELECT name FROM province ORDER BY COALESCE(last_scanned,'') ASC")]
        for prov in provs:
            n, total, pages = 1, None, 1
            while n <= pages:
                url = f"https://www.jobbkk.com/{quote('หางาน')}/{quote(prov)}" + (f"/{n}" if n > 1 else "")
                pause()
                try:
                    page.goto(url, wait_until="networkidle", timeout=90000)
                    for _ in range(8):
                        page.mouse.wheel(0, 1500)
                        page.wait_for_timeout(600)
                    html, title = page.content(), page.title()
                except Exception as e:  # timeouts, network
                    log(f"{prov} p{n}: {e.__class__.__name__}; skipping page")
                    n += 1
                    continue
                if blocked_text(title, html):
                    on_block(url)
                    continue
                blocks = 0
                if total is None:
                    m = re.search(r"([\d,]+)\s*ตำแหน่ง", page.inner_text("body"))
                    total = int(m.group(1).replace(",", "")) if m else 0
                    pages = max(1, -(-total // PER_PAGE))
                    if MAX_PAGES:
                        pages = min(pages, MAX_PAGES)
                    con.execute("UPDATE province SET total=? WHERE name=?", (total, prov))
                keys = list(dict.fromkeys(f"{a}/{b}" for a, b in re.findall(r"/jobs/detail(?:urgent)?/(\d+)/(\d+)", html)))
                t = now()
                for k in keys:
                    if con.execute("UPDATE job SET last_seen=? WHERE job_key=?", (t, k)).rowcount == 0:
                        con.execute("INSERT INTO job(job_key, first_seen, last_seen, seen_in) VALUES (?,?,?,?)", (k, t, t, prov))
                        new_total += 1
                con.execute("UPDATE province SET last_page=? WHERE name=?", (n, prov))
                con.commit()
                if n % 10 == 0:
                    log(f"{prov}: page {n}/{pages} | new ids so far {new_total}")
                if not keys:
                    break
                n += 1
            con.execute("UPDATE province SET last_scanned=? WHERE name=?", (now(), prov))
            con.commit()
            log(f"{prov}: total {total} | pages scanned {n - 1} | new ids so far {new_total}")
        browser.close()
    log(f"discover done: {new_total} new job ids")


def fetch(con):
    global blocks
    keys = [r[0] for r in con.execute(
        "SELECT job_key FROM job WHERE status='pending' OR (status='error' AND attempts<3) ORDER BY first_seen DESC")]
    log(f"fetching {len(keys)} job pages (about {len(keys) * DELAY * 1.25 / 3600:.1f} h)")
    for i, k in enumerate(keys, 1):
        pause()
        try:
            r = http.get(f"https://www.jobbkk.com/jobs/detail/{k}", timeout=40)
        except requests.RequestException as e:
            log(f"network error {e.__class__.__name__}; waiting 5 min")
            time.sleep(300)
            continue
        if r.status_code in (403, 429) or blocked_text("", r.text):
            on_block(k)
            continue
        blocks = 0
        rec = extract_jobposting(r.text) if r.status_code == 200 else None
        if rec:
            con.execute("UPDATE job SET status='ok', fetched_at=?, jsonld=?, attempts=attempts+1 WHERE job_key=?",
                        (now(), json.dumps(rec, ensure_ascii=False), k))
        else:
            status = "gone" if r.status_code == 404 else "error"
            con.execute("UPDATE job SET status=?, attempts=attempts+1 WHERE job_key=?", (status, k))
        if i % 20 == 0:
            con.commit()
            log(f"fetch {i}/{len(keys)}")
    con.commit()


def stats(con):
    print(dict(con.execute("SELECT status, COUNT(*) FROM job GROUP BY status").fetchall()))
    print("provinces scanned:", con.execute("SELECT COUNT(*) FROM province WHERE last_scanned IS NOT NULL").fetchone()[0],
          "/", len(PROVINCES), "| site total (sum of province totals):",
          con.execute("SELECT SUM(total) FROM province").fetchone()[0])


def export(con):
    import csv
    os.makedirs("data", exist_ok=True)
    rows = con.execute("SELECT job_key, first_seen, last_seen, seen_in, jsonld FROM job WHERE status='ok'").fetchall()
    with open("data/jobbkk_jobs.jsonl", "w", encoding="utf-8") as fj, \
         open("data/jobbkk_jobs.csv", "w", encoding="utf-8-sig", newline="") as fc:
        w = None
        for k, fs, ls, prov, js in rows:
            rec = json.loads(js)
            fj.write(json.dumps({"job_key": k, "first_seen": fs, "last_seen": ls, **rec}, ensure_ascii=False) + "\n")
            # JobBKK JSON-LD address is often the company head office; the listing province is the work location
            row = {"job_key": k, "first_seen": fs, "last_seen": ls, "listing_province": prov, **flat(rec)}
            if w is None:
                w = csv.DictWriter(fc, fieldnames=list(row))
                w.writeheader()
            w.writerow(row)
    log(f"exported {len(rows)} postings to data/jobbkk_jobs.csv and .jsonl")


def run_forever(con):
    while True:
        discover(con)
        fetch(con)
        export(con)
        stats(con)
        log(f"sleeping {REDISCOVER_HOURS} h before the next round")
        time.sleep(REDISCOVER_HOURS * 3600)


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
