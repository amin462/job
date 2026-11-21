"""Print lines of a saved terms page that mention copying, automated collection or IP."""
import html as h, re, sys
raw = open(sys.argv[1], encoding="utf-8", errors="ignore").read()
txt = h.unescape(re.sub(r"<[^>]+>", "\n", re.sub(r"<script.*?</script>|<style.*?</style>", " ", raw, flags=re.S)))
keys = ["ทำซ้ำ", "คัดลอก", "ดัดแปลง", "อัตโนมัติ", "robot", "spider", "crawl", "scrap", "ดึงข้อมูล", "ลิขสิทธิ์", "ทรัพย์สินทางปัญญา", "เชิงพาณิชย์"]
for line in (l.strip() for l in txt.split("\n")):
    if line and any(k.lower() in line.lower() for k in keys):
        print("-", line[:350])
