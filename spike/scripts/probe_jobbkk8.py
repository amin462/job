import re
from playwright.sync_api import sync_playwright
HOME = "https://www.jobbkk.com/jobs/lists/1/หางาน,โปรแกรมเมอร์,ทุกจังหวัด,ทั้งหมด.html?keyword_type=3"
CAPTURE = "window.__opened=[];window.open=function(u){window.__opened.push(String(u));return null;};"
def ids_on(pg, url):
    pg.goto(url, wait_until="networkidle", timeout=60000)
    for _ in range(8): pg.mouse.wheel(0, 1500); pg.wait_for_timeout(800)
    btns = pg.get_by_text("อ่านรายละเอียดงาน")
    for i in range(btns.count()):
        btns.nth(i).click(); pg.wait_for_timeout(150)
    txt = pg.inner_text("body")
    return pg.evaluate("window.__opened"), re.findall(r"([\d,]+)\s*ตำแหน่ง", txt)[:1]
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = b.new_context(viewport={"width": 1366, "height": 900}); ctx.add_init_script(CAPTURE); pg = ctx.new_page()
    pg.goto(HOME, wait_until="networkidle")
    regions = pg.eval_on_selector_all("a", "els => els.filter(e => /หางาน (ภาคใต้|กรุงเทพมหานคร)/.test(e.innerText)).map(e => e.href)")
    print("region links:", regions[:3])
    base = regions[0]
    p1, t1 = ids_on(pg, base); pg.wait_for_timeout(3000)
    p2url = re.sub(r"/jobs/lists/1/", "/jobs/lists/2/", base)
    p2, t2 = ids_on(pg, p2url)
    print("total:", t1, "| page1:", len(p1), p1[:2], "| page2:", len(p2), p2[:2], "| overlap:", len(set(p1) & set(p2)))
    b.close()
