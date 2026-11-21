"""Analyze the job-posting sample: field completeness, salary, location,
skill extraction coverage and requirement fields.

Usage: python -I -X utf8 analyze_sample.py <out_csv> <html_dir> [<html_dir> ...]
"""
import glob
import html as htmllib
import os
import re
import sys
from collections import Counter

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parse_jobposting import extract  # noqa: E402

SOUTH = {"ชุมพร", "ระนอง", "สุราษฎร์ธานี", "พังงา", "ภูเก็ต", "กระบี่", "นครศรีธรรมราช",
         "ตรัง", "พัทลุง", "สตูล", "สงขลา", "ปัตตานี", "ยะลา", "นราธิวาส"}
DEEP_SOUTH = {"สงขลา", "ปัตตานี", "ยะลา", "นราธิวาส"}

# Seed skill dictionary for the spike only: canonical -> regex of aliases (TH/EN).
SKILLS = {
    "Microsoft Excel": r"excel|เอ็กเซล|เอกเซล",
    "Microsoft Word": r"\bword\b|เวิร์ด",
    "Microsoft PowerPoint": r"power ?point|พาวเวอร์พอยท์",
    "Microsoft Office": r"ms ?office|microsoft office|โปรแกรม ?office|ไมโครซอฟท์ ?ออฟฟิศ",
    "SAP / ERP": r"\bsap\b|\berp\b",
    "Express (บัญชี)": r"express",
    "AutoCAD": r"auto ?cad",
    "SolidWorks": r"solid ?works",
    "Photoshop": r"photoshop",
    "Illustrator": r"illustrator",
    "Canva": r"canva",
    "Video Editing": r"premiere|capcut|final cut|ตัดต่อ",
    "Power BI": r"power ?bi",
    "Tableau": r"tableau",
    "SQL": r"\bsql\b",
    "Python": r"python",
    "Java": r"\bjava\b",
    "JavaScript": r"javascript|\bjs\b|react|vue|angular|node\.?js",
    "PHP": r"\bphp\b|laravel",
    "C# / .NET": r"c#|\.net",
    "Network / IT Support": r"network|เครือข่าย|it support|ซ่อมคอม",
    "English": r"english|ภาษาอังกฤษ|toeic|ielts",
    "Chinese": r"chinese|ภาษาจีน|mandarin",
    "Japanese": r"japanese|ภาษาญี่ปุ่น|jlpt",
    "Driving licence (car)": r"ใบขับขี่รถยนต์|ใบอนุญาตขับขี่|ขับรถยนต์|driving licen[cs]e|driver.s licen[cs]e",
    "Driving licence (motorcycle)": r"ใบขับขี่รถจักรยานยนต์|ขับรถจักรยานยนต์|ขับมอเตอร์ไซค์",
    "Truck licence (ท.2/บ.2)": r"ท\.?\s?2|บ\.?\s?2|ท\.?\s?3|บ\.?\s?3",
    "Forklift": r"forklift|โฟล์?คลิ?ฟ|รถยก",
    "Accounting": r"บัญชี|accounting",
    "Tax": r"ภาษี|\btax\b",
    "Purchasing": r"จัดซื้อ|purchas",
    "Sales": r"ขาย|sales",
    "Digital Marketing": r"digital marketing|การตลาดออนไลน์|facebook ads?|tiktok|seo|google ads|content",
    "Customer Service": r"บริการลูกค้า|customer service|call ?center",
    "ISO / GMP / HACCP": r"\biso\b|\bgmp\b|haccp",
    "Lean / Kaizen / 5S": r"lean|kaizen|ไคเซ็น|5ส|\b5s\b|six sigma",
    "PLC / Automation": r"\bplc\b|automation|scada",
    "Electrical": r"ไฟฟ้า|electric",
    "Mechanical / Maintenance": r"เครื่องกล|mechanic|ซ่อมบำรุง|maintenance",
    "Welding": r"เชื่อม|weld",
    "CNC / Machining": r"\bcnc\b|กลึง|มิลลิ่ง",
    "QC / QA": r"\bqc\b|\bqa\b|ควบคุมคุณภาพ|quality",
    "Warehouse / Logistics": r"คลังสินค้า|warehouse|logistic|โลจิสติก|ขนส่ง|\bwms\b",
    "HR / Payroll": r"บุคคล|\bhr\b|payroll|เงินเดือนพนักงาน|สรรหา",
    "Labour law": r"กฎหมายแรงงาน",
    "Communication": r"การสื่อสาร|สื่อสาร|communication",
    "Teamwork": r"ทำงานเป็นทีม|teamwork|team work",
    "Leadership": r"ภาวะผู้นำ|leadership|บริหารทีม",
    "Problem solving": r"แก้ปัญหา|problem.solving",
    "Negotiation": r"ต่อรอง|negotiat",
    "Cooking / Kitchen": r"ทำอาหาร|ครัว|cook|chef|บาริสต้า|barista",
    "Nursing / Healthcare": r"พยาบาล|nurse|เภสัช|pharmac",
    "Teaching": r"สอน|teach|ครู|tutor",
}
SKILL_RX = {k: re.compile(v, re.I) for k, v in SKILLS.items()}

EDU = [("master", r"ปริญญาโท|ป\.\s?โท|master"),
       ("bachelor", r"ปริญญาตรี|ป\.\s?ตรี|bachelor"),
       ("high_vocational", r"ปวส|high vocational"),
       ("vocational", r"ปวช"),
       ("upper_secondary", r"ม\.\s?6|มัธยมศึกษาปีที่ ?6|ม\.ปลาย|มัธยมปลาย"),
       ("lower_secondary", r"ม\.\s?3|มัธยมศึกษาปีที่ ?3|ม\.ต้น")]
EXP_RX = re.compile(r"ประสบการณ์[^0-9\n]{0,40}?(\d{1,2})\s*(?:-|–|ถึง)?\s*(\d{1,2})?\s*ปี")
FRESH_RX = re.compile(r"ไม่มีประสบการณ์|ไม่จำเป็นต้องมีประสบการณ์|จบใหม่|นักศึกษาจบใหม่|fresh ?grad", re.I)
GENDER_RX = re.compile(r"เพศ\s?(ชาย|หญิง)|เพศชาย|เพศหญิง|male|female", re.I)
AGE_RX = re.compile(r"อายุ\s?(ไม่เกิน|ระหว่าง|ตั้งแต่)?\s?\d{2}")


def clean(text):
    if not isinstance(text, str):
        return ""
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", text))).strip()


def row(rec, site):
    loc = (rec.get("jobLocation") or {})
    loc = loc[0] if isinstance(loc, list) and loc else loc
    addr = (loc or {}).get("address") or {}
    sal = ((rec.get("baseSalary") or {}).get("value")) or {}
    edu_struct = (rec.get("educationRequirements") or {})
    exp_struct = (rec.get("experienceRequirements") or {})
    desc, qual = clean(rec.get("description")), clean(rec.get("qualifications"))
    text = f"{rec.get('title','')} {desc} {qual}"
    skills = [k for k, rx in SKILL_RX.items() if rx.search(text)]
    edu = next((name for name, rx in EDU if re.search(rx, text, re.I)), None)
    m = EXP_RX.search(text)
    exp_years = int(m.group(1)) if m else (0 if FRESH_RX.search(text) else None)
    return {
        "site": site,
        "title": rec.get("title"),
        "company": (rec.get("hiringOrganization") or {}).get("name"),
        "province": (addr.get("addressRegion") or "").replace("จังหวัด", "").strip() or None,
        "district": addr.get("addressLocality"),
        "occupational_category": rec.get("occupationalCategory"),
        "industry": rec.get("industry"),
        "employment_type": rec.get("employmentType"),
        "date_posted": (rec.get("datePosted") or "")[:10] or None,
        "valid_through": (rec.get("validThrough") or "")[:10] or None,
        "salary_min": sal.get("minValue"),
        "salary_max": sal.get("maxValue"),
        "salary_unit": sal.get("unitText"),
        "edu_structured": edu_struct.get("credentialCategory") if isinstance(edu_struct, dict) else None,
        "exp_months_structured": exp_struct.get("monthsOfExperience") if isinstance(exp_struct, dict) else None,
        "edu_regex": edu,
        "exp_years_regex": exp_years,
        "mentions_gender": bool(GENDER_RX.search(text)),
        "mentions_age": bool(AGE_RX.search(text)),
        "desc_chars": len(desc),
        "qual_chars": len(qual),
        "n_skills": len(skills),
        "skills": "|".join(skills),
        "description_preview": desc[:200],
    }


def pct(s):
    return f"{100 * s.mean():.0f}%"


def main(out_csv, dirs):
    rows, failed = [], 0
    for d in dirs:
        site = os.path.basename(os.path.dirname(os.path.normpath(d))) if os.path.basename(os.path.normpath(d)) == "sample" else os.path.basename(os.path.normpath(d))
        for f in sorted(glob.glob(os.path.join(d, "job_*.html"))):
            rec = extract(f)
            if rec is None:
                failed += 1
                continue
            rows.append(row(rec, site))
    df = pd.DataFrame(rows)
    df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    n = len(df)
    print(f"parsed {n} postings, failed {failed}\n")
    print("== by site:", df["site"].value_counts().to_dict())

    print("\n== field completeness")
    for c in ["title", "company", "province", "district", "occupational_category", "industry",
              "employment_type", "date_posted", "valid_through", "salary_min", "edu_structured",
              "exp_months_structured", "edu_regex", "exp_years_regex"]:
        print(f"  {c:24s} {pct(df[c].notna() & (df[c].astype(str) != ''))}")

    print("\n== salary")
    has_sal = df["salary_min"].notna() | df["salary_max"].notna()
    print(f"  has numeric salary: {pct(has_sal)} | units: {df.loc[has_sal,'salary_unit'].value_counts().to_dict()}")
    m = df.loc[has_sal & (df["salary_unit"] == "MONTH")]
    if len(m):
        mid = (m["salary_min"].fillna(m["salary_max"]) + m["salary_max"].fillna(m["salary_min"])) / 2
        print(f"  monthly midpoint THB: median {mid.median():,.0f} | p10 {mid.quantile(.1):,.0f} | p90 {mid.quantile(.9):,.0f}")
    by_site = df.assign(has_sal=has_sal).groupby("site")["has_sal"].mean().map(lambda v: f"{100*v:.0f}%")
    print(f"  salary present by site: {by_site.to_dict()}")

    print("\n== location")
    print(f"  Bangkok share: {pct(df['province'].fillna('').str.contains('กรุงเทพ'))}"
          f" | South (14 prov.): {pct(df['province'].isin(SOUTH))}"
          f" | Songkhla/Pattani/Yala/Narathiwat: {int(df['province'].isin(DEEP_SOUTH).sum())} rows")
    print("  top provinces:", df["province"].value_counts().head(8).to_dict())

    print("\n== categories")
    print("  distinct occupational_category:", df["occupational_category"].nunique())
    print("  top:", df["occupational_category"].value_counts().head(6).to_dict())

    print("\n== text & skills")
    print(f"  desc chars median {df['desc_chars'].median():.0f} | qualification chars median {df['qual_chars'].median():.0f}")
    print(f"  postings with >=1 skill: {pct(df['n_skills'] > 0)} | skills per posting median {df['n_skills'].median():.0f} mean {df['n_skills'].mean():.1f}")
    c = Counter(s for v in df["skills"] if v for s in v.split("|"))
    print("  top skills:", dict(c.most_common(15)))

    print("\n== requirements")
    print(f"  education found (structured or regex): {pct(df['edu_structured'].notna() | df['edu_regex'].notna())}"
          f" | experience found: {pct(df['exp_months_structured'].notna() | df['exp_years_regex'].notna())}")
    print(f"  mentions gender: {pct(df['mentions_gender'])} | mentions age: {pct(df['mentions_age'])}")
    print(f"\n  date_posted range: {df['date_posted'].min()} .. {df['date_posted'].max()}")
    print(f"\nCSV written: {out_csv}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
