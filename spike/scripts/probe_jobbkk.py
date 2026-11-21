"""Open JobBKK listing pages in Chromium and report job links + paging behaviour."""
import re, sys
from playwright.sync_api import sync_playwright
URL = "https://www.jobbkk.com/jobs/lists/{p}/%E0%B8%AB%E0%B8%B2%E0%B8%87%E0%B8%B2%E0%B8%99,%E0%B8%97%E0%B8%B8%E0%B8%81%E0%B8%95%E0%B8%B3%E0%B9%81%E0%B8%AB%E0%B8%99%E0%B9%88%E0%B8%87,%E0%B8%97%E0%B8%B8%E0%B8%81%E0%B8%88%E0%B8%B1%E0%B8%87%E0%B8%AB%E0%B8%A7%E0%B8%B1%E0%B8%94,%E0%B8%97%E0%B8%B1%E0%B9%89%E0%B8%87%E0%B8%AB%E0%B8%A1%E0%B8%94.html"
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(user_agent="Mozilla/5.0 (compatible; student-capstone-research/1.0)")
    seen = []
    for n in (1, 2, 50):
        pg.goto(URL.format(p=n), wait_until="networkidle", timeout=60000)
        html = pg.content()
        ids = list(dict.fromkeys(re.findall(r"/jobs/detail/(\d+)/(\d+)", html)))
        total = re.findall(r"([\d,]{3,})\s*(?:ตำแหน่ง|รายการ|งาน)", pg.inner_text("body"))[:5]
        print(f"page {n}: {len(ids)} jobs | first {ids[:2]} | counts on page {total}")
        seen.append(set(ids))
        pg.wait_for_timeout(4000)
    print("overlap p1/p2:", len(seen[0] & seen[1]), "| p1/p50:", len(seen[0] & seen[2]))
    b.close()
