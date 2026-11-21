"""Polite sample fetcher for the job-posting data spike.

Fetches a small sample of public job pages (robots.txt allows these paths),
one request at a time with a fixed delay, and saves the raw HTML for parsing.
Stops immediately on HTTP 403/429 or a CAPTCHA page instead of retrying.

Usage:
  python -I -X utf8 fetch_sample.py jobthai   <out_dir> <pages comma-separated> [delay_s]
  python -I -X utf8 fetch_sample.py jobtopgun <out_dir> <listing_html_file>    [delay_s]
"""
import os
import re
import sys
import time

import requests

UA = "Mozilla/5.0 (compatible; student-research-probe/0.1; academic data spike)"
SESSION = requests.Session()
SESSION.headers["User-Agent"] = UA


def get(url):
    r = SESSION.get(url, timeout=30)
    body = r.text
    if r.status_code in (403, 429) or "captcha" in body[:5000].lower():
        sys.exit(f"STOP: blocked or rate-limited at {url} (HTTP {r.status_code})")
    r.raise_for_status()
    return body


def save(out_dir, name, body):
    with open(os.path.join(out_dir, name), "w", encoding="utf-8") as f:
        f.write(body)


def jobthai(out_dir, pages, delay):
    ids = []
    for p in pages:
        url = f"https://www.jobthai.com/%E0%B8%AB%E0%B8%B2%E0%B8%87%E0%B8%B2%E0%B8%99/%E0%B8%87%E0%B8%B2%E0%B8%99%E0%B8%97%E0%B8%B1%E0%B9%89%E0%B8%87%E0%B8%AB%E0%B8%A1%E0%B8%94/{p}"
        body = get(url)
        save(out_dir, f"list_p{p}.html", body)
        found = sorted(set(re.findall(r"/th/company/job/(\d+)", body)))
        print(f"list page {p}: {len(found)} jobs", flush=True)
        ids.extend(i for i in found if i not in ids)
        time.sleep(delay)
    for n, jid in enumerate(ids, 1):
        path = os.path.join(out_dir, f"job_{jid}.html")
        if os.path.exists(path):
            continue
        save(out_dir, f"job_{jid}.html", get(f"https://www.jobthai.com/th/company/job/{jid}"))
        print(f"[{n}/{len(ids)}] job {jid}", flush=True)
        time.sleep(delay)


def jobtopgun(out_dir, listing_file, delay):
    html = open(listing_file, encoding="utf-8", errors="ignore").read()
    slugs = sorted(set(re.findall(r'href="/th/jobs/(j\d+-\d+)"', html)))
    print(f"{len(slugs)} jobs on listing", flush=True)
    for n, slug in enumerate(slugs, 1):
        path = os.path.join(out_dir, f"job_{slug}.html")
        if os.path.exists(path):
            continue
        save(out_dir, f"job_{slug}.html", get(f"https://www.jobtopgun.com/th/jobs/{slug}"))
        print(f"[{n}/{len(slugs)}] job {slug}", flush=True)
        time.sleep(delay)


DEEP_SOUTH = {"สงขลา", "ปัตตานี", "ยะลา", "นราธิวาส"}


def jobthai_provinces(out_dir, codes, delay, deep_n=20, other_n=1):
    """Fetch each province listing (total + newest 20 ids), then a stratified detail sample."""
    import csv
    summary, picks = [], []
    for code in codes:
        body = get(f"https://www.jobthai.com/th/jobs?province={code}")
        title = re.search(r"<title>([^<]*)</title>", body)
        name = re.sub(r"^งาน หางาน สมัครงาน\s*|\s*-\s*JobThai$", "", title.group(1)).strip() if title else ""
        total = re.search(r'"total":(\d+)', body)
        ids = list(dict.fromkeys(re.findall(r"/th/company/job/(\d+)", body)))
        summary.append({"code": code, "province": name, "total": int(total.group(1)) if total else None})
        n = deep_n if name in DEEP_SOUTH else other_n
        picks.extend(ids[:n])
        print(f"province {code} {name}: total {summary[-1]['total']} | picked {min(n, len(ids))}", flush=True)
        time.sleep(delay)
    with open(os.path.join(out_dir, "province_totals.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["code", "province", "total"])
        w.writeheader()
        w.writerows(summary)
    picks = list(dict.fromkeys(picks))
    for n, jid in enumerate(picks, 1):
        path = os.path.join(out_dir, f"job_{jid}.html")
        if os.path.exists(path):
            continue
        save(out_dir, f"job_{jid}.html", get(f"https://www.jobthai.com/th/company/job/{jid}"))
        print(f"[{n}/{len(picks)}] job {jid}", flush=True)
        time.sleep(delay)


if __name__ == "__main__":
    site, out_dir = sys.argv[1], sys.argv[2]
    delay = float(sys.argv[4]) if len(sys.argv) > 4 else 5.0
    os.makedirs(out_dir, exist_ok=True)
    if site == "jobthai":
        jobthai(out_dir, [int(x) for x in sys.argv[3].split(",")], delay)
    elif site == "jobthai_provinces":
        jobthai_provinces(out_dir, sys.argv[3].split(","), delay)
    elif site == "jobtopgun":
        jobtopgun(out_dir, sys.argv[3], delay)
    print("DONE", flush=True)
