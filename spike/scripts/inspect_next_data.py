"""Print the shape of a Next.js __NEXT_DATA__ blob from a saved HTML file."""
import json, re, sys

def walk(o, path="", depth=0, maxdepth=5):
    if depth > maxdepth:
        return
    if isinstance(o, dict):
        for k, v in o.items():
            t = type(v).__name__
            preview = ""
            if isinstance(v, (str, int, float, bool)) or v is None:
                preview = repr(v)[:80]
            elif isinstance(v, list):
                preview = f"list[{len(v)}]"
            print("  " * depth + f"{path}.{k}: {t} {preview}")
            walk(v, f"{path}.{k}", depth + 1, maxdepth)
    elif isinstance(o, list) and o:
        walk(o[0], path + "[0]", depth + 1, maxdepth)

html = open(sys.argv[1], encoding="utf-8", errors="ignore").read()
m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
if not m:
    sys.exit("no __NEXT_DATA__")
data = json.loads(m.group(1))
walk(data, "", 0, int(sys.argv[2]) if len(sys.argv) > 2 else 4)
