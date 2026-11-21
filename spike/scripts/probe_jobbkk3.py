import re
from playwright.sync_api import sync_playwright
U = ["https://www.jobbkk.com/jobs/lists/1/หางาน,โปรแกรมเมอร์,ทุกจังหวัด,ทั้งหมด.html?keyword_type=3",
     "https://www.jobbkk.com/jobs/lists/2/หางาน,โปรแกรมเมอร์,ทุกจังหวัด,ทั้งหมด.html?keyword_type=3"]
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    api = []
    pg.on("response", lambda r: api.append(r.url[:200]) if "smartapi" in r.url else None)
    for u in U:
        pg.goto(u, wait_until="networkidle", timeout=60000); pg.wait_for_timeout(2000)
        links = set(re.findall(r"/jobs/detail/(\d+)/(\d+)", pg.content()))
        txt = pg.inner_text("body")
        print(u[-60:], "| detail links:", len(links), "| totals:", re.findall(r"[\d,]{2,}\s*(?:ตำแหน่ง|รายการ)", txt)[:4])
        pg.wait_for_timeout(4000)
    print("smartapi calls:", *api[:8], sep="\n  ")
    b.close()
