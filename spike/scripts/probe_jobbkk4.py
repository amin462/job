import re
from playwright.sync_api import sync_playwright
U = "https://www.jobbkk.com/jobs/lists/1/หางาน,โปรแกรมเมอร์,ทุกจังหวัด,ทั้งหมด.html?keyword_type=3"
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    pg.goto(U, wait_until="networkidle", timeout=60000); pg.wait_for_timeout(2000)
    h = pg.content()
    print("jobpost_id:", len(set(re.findall(r'jobpost_id\?"?\s*[:=]\s*\?"?(\d+)', h))))
    print("data attrs:", sorted(set(re.findall(r'data-[a-z\-]*(?:job|id)[a-z\-]*', h)))[:15])
    i = h.find("โปรแกรมเมอร์", h.find("140"))
    print(h[i-1500:i+300])
    b.close()
