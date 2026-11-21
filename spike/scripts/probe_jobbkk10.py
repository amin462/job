import re
from playwright.sync_api import sync_playwright
def ids(pg, u):
    pg.goto(u, wait_until="networkidle", timeout=60000)
    for _ in range(8): pg.mouse.wheel(0, 1500); pg.wait_for_timeout(700)
    return set(re.findall(r"/jobs/detail(?:urgent)?/(\d+/\d+)", pg.content()))
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1366, "height": 900})
    base = "https://www.jobbkk.com/หางาน/กรุงเทพมหานคร"
    a = ids(pg, base)
    nxt = pg.locator("a, button").filter(has_text=re.compile(r"^\s*(2|ถัดไป|>|›|»)\s*$"))
    print("next-like controls:", nxt.count(), [ (nxt.nth(i).evaluate("e=>e.tagName+' '+(e.getAttribute('href')||'')")) for i in range(min(4,nxt.count()))])
    for u in (base + "?page=2", base + "/2"):
        pg.wait_for_timeout(3000); s = ids(pg, u); print(u[-20:], len(s), "overlap with p1:", len(a & s))
    b.close()
