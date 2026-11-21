import re
from playwright.sync_api import sync_playwright
U = "https://www.jobbkk.com/jobs/lists/1/หางาน,โปรแกรมเมอร์,ทุกจังหวัด,ทั้งหมด.html?keyword_type=3"
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1366, "height": 900},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36 student-capstone-research")
    pg.goto(U, wait_until="networkidle", timeout=60000)
    for _ in range(6):
        pg.mouse.wheel(0, 1500); pg.wait_for_timeout(1500)
    txt = pg.inner_text("body")
    print("body chars:", len(txt))
    i = txt.find("140"); print(txt[i:i+1200])
    print("detail links:", len(set(re.findall(r"/jobs/detail/(\d+)/(\d+)", pg.content()))))
    pg.screenshot(path="../out/jobbkk_list.png", full_page=False)
    b.close()
