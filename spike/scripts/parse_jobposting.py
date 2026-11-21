"""Extract schema.org JobPosting JSON-LD from saved job-page HTML files.

Usage: python -I parse_jobposting.py <html_file> [<html_file> ...]
Prints one JSON object per line (JSONL) with the raw JobPosting fields.
Contact persons, phone numbers and e-mails are dropped (PDPA).
"""
import json
import re
import sys

NEXT_S = re.compile(
    r'\(self\.__next_s=self\.__next_s\|\|\[\]\)\.push\(\[0,(\{.*?\})\]\)</script>', re.S
)
LD_TAG = re.compile(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.S)
PII_KEYS = {"telephone", "email", "contactPoint", "applicationContact"}


def candidates(html):
    for m in NEXT_S.finditer(html):
        try:
            obj = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if obj.get("type") == "application/ld+json" and "children" in obj:
            yield obj["children"]
    for m in LD_TAG.finditer(html):
        yield m.group(1)


def strip_pii(o):
    if isinstance(o, dict):
        return {k: strip_pii(v) for k, v in o.items() if k not in PII_KEYS}
    if isinstance(o, list):
        return [strip_pii(v) for v in o]
    return o


def extract(path):
    html = open(path, encoding="utf-8", errors="ignore").read()
    for raw in candidates(html):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for item in data if isinstance(data, list) else [data]:
            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                item = strip_pii(item)
                item["_source_file"] = path.replace("\\", "/").split("/")[-1]
                return item
    return None


if __name__ == "__main__":
    for p in sys.argv[1:]:
        rec = extract(p)
        if rec:
            print(json.dumps(rec, ensure_ascii=False))
        else:
            print(json.dumps({"_source_file": p, "_error": "no JobPosting"}), file=sys.stderr)
