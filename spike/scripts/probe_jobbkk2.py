import re, json
from playwright.sync_api import sync_playwright
from probe_jobbkk import URL
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    xhr = []
    pg.on("response", lambda r: xhr.append((r.request.method, r.url[:160], r.headers.get("content-type",""))) if r.request.resource_type in ("xhr","fetch") else None)
    pg.goto(URL.format(p=1), wait_until="networkidle", timeout=60000)
    pg.mouse.wheel(0, 4000); pg.wait_for_timeout(3000)
    for x in xhr[:15]: print("XHR", x)
    body = pg.inner_text("body")
    print("body chars", len(body)); print(body[1500:2600])
    links = pg.eval_on_selector_all("a", "els => els.map(e => e.getAttribute('href')).filter(h => h && /detail|job/.test(h))")
    print("job-ish links:", len(links), links[:8])
    b.close()
