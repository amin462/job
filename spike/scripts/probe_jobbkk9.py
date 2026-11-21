import re
from playwright.sync_api import sync_playwright
U = "https://www.jobbkk.com/หางาน/กรุงเทพมหานคร"
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1366, "height": 900})
    pg.goto(U, wait_until="networkidle", timeout=60000)
    for _ in range(8): pg.mouse.wheel(0, 1500); pg.wait_for_timeout(800)
    h = pg.content()
    print("detail anchors:", len(set(re.findall(r"/jobs/detail(?:urgent)?/(\d+)/(\d+)", h))))
    print("paging links:", sorted(set(re.findall(r'href="([^"]*(?:page=|/lists/)\d+[^"]*)"', h)))[:6])
    btn = pg.locator("button, a").filter(has_text=re.compile("รายละเอียด|สมัคร"))
    print("buttons w/ รายละเอียด/สมัคร:", btn.count(), [btn.nth(i).inner_text()[:20] for i in range(min(3, btn.count()))])
    b.close()
