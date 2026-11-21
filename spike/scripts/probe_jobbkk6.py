from playwright.sync_api import sync_playwright
U = "https://www.jobbkk.com/jobs/lists/1/หางาน,โปรแกรมเมอร์,ทุกจังหวัด,ทั้งหมด.html?keyword_type=3"
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1366, "height": 900})
    pg.goto(U, wait_until="networkidle", timeout=60000)
    for _ in range(6): pg.mouse.wheel(0, 1500); pg.wait_for_timeout(1200)
    print(pg.eval_on_selector_all("[data-id]", "els => els.slice(0,6).map(e => e.tagName+' '+e.getAttribute('data-id')+' | '+e.outerHTML.slice(0,160))"))
    btn = pg.get_by_text("อ่านรายละเอียดงาน").first
    print("button html:", btn.evaluate("e => e.outerHTML.slice(0,300)"))
    card = btn.evaluate("e => { let c=e; for (let i=0;i<6;i++) c=c.parentElement; return c.outerHTML.slice(0,800) }")
    print("card:", card)
    with pg.expect_navigation(timeout=30000):
        btn.click()
    print("navigated to:", pg.url)
    b.close()
