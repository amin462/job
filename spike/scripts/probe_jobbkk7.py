from playwright.sync_api import sync_playwright
U = "https://www.jobbkk.com/jobs/lists/1/หางาน,โปรแกรมเมอร์,ทุกจังหวัด,ทั้งหมด.html?keyword_type=3"
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = b.new_context(viewport={"width": 1366, "height": 900}); pg = ctx.new_page()
    pg.goto(U, wait_until="networkidle", timeout=60000)
    for _ in range(6): pg.mouse.wheel(0, 1500); pg.wait_for_timeout(1200)
    btns = pg.get_by_text("อ่านรายละเอียดงาน")
    print("buttons:", btns.count())
    for i in range(2):
        with ctx.expect_page(timeout=20000) as info:
            btns.nth(i).click()
        newp = info.value; newp.wait_for_load_state("domcontentloaded")
        print("opened:", newp.url); newp.close(); pg.wait_for_timeout(3000)
    b.close()
