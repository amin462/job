"""End-to-end offline & Postgres ETL pipeline runner (T3.7).

Usage:
  py -I -X utf8 -m pipeline.etl.run_pipeline \
    --raw-dirs spike/raw/jobthai/sample spike/raw/jobthai/by_province \
    --out-dir data/processed
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

from pipeline.etl.build_marts import build_all_marts, write_seed_marts
from pipeline.etl.clean import (
    clean_html_text,
    detect_gender_age_mentions,
    extract_education,
    extract_experience,
    normalize_company,
    normalize_district,
    normalize_province,
    normalize_salary,
    normalize_thai_text,
    scrub_hr_pii,
)
from pipeline.etl.extract_skills import SkillExtractor
from pipeline.etl.load_dw import (
    DEFAULT_PROVINCE_TOTALS,
    compute_weights_and_seen_dates,
    upsert_dw_to_postgres,
)
from pipeline.etl.map_taxonomy import OccupationMapper
from pipeline.etl.validate import run_dq_checks

REPO_ROOT = Path(__file__).resolve().parents[2]
PII_KEYS_LOWER: frozenset[str] = frozenset(
    {
        "telephone",
        "email",
        "contactpoint",
        "applicationcontact",
        "faxnumber",
        "contact",
        "contactperson",
        "contactname",
        "line",
        "lineid",
        "line_id",
    }
)
_LD_SCRIPT_RX = re.compile(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.S | re.I)
_NEXT_MARKER = "(self.__next_s=self.__next_s||[]).push([0,"

CLEAN_CSV_COLUMNS: list[str] = [
    "source",
    "source_job_id",
    "source_url",
    "title_short",
    "company_name_norm",
    "province_code",
    "province_th",
    "province_en",
    "district_th",
    "region",
    "is_south14",
    "occupational_category",
    "occupation_cluster",
    "occupation_slug",
    "industry",
    "employment_type",
    "date_posted",
    "valid_through",
    "first_seen_date_key",
    "last_seen_date_key",
    "salary_min",
    "salary_max",
    "salary_mid",
    "salary_open_max",
    "salary_unit_orig",
    "salary_out_of_range",
    "has_salary",
    "education_level",
    "experience_band",
    "n_skills",
    "skills",
    "sample_stratum",
    "sample_weight",
    "mentions_gender",
    "mentions_age",
    "content_hash",
]


def _strip_pii(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _strip_pii(v) for k, v in obj.items() if str(k).lower() not in PII_KEYS_LOWER}
    if isinstance(obj, list):
        return [_strip_pii(v) for v in obj]
    return obj


def extract_jobposting_from_html(html_path: Path) -> dict[str, Any] | None:
    """Extract schema.org JobPosting JSON-LD from HTML with HR contact fields stripped."""
    html = html_path.read_text(encoding="utf-8", errors="ignore")
    pos = 0
    while True:
        idx = html.find(_NEXT_MARKER, pos)
        if idx == -1:
            break
        start = idx + len(_NEXT_MARKER)
        end = html.find("])</script>", start)
        if end == -1:
            break
        pos = end
        try:
            obj = json.loads(html[start:end])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("type") == "application/ld+json" and "children" in obj:
            try:
                data = json.loads(obj["children"])
            except json.JSONDecodeError:
                continue
            for item in data if isinstance(data, list) else [data]:
                if isinstance(item, dict) and item.get("@type") == "JobPosting":
                    return _strip_pii(item)

    for m in _LD_SCRIPT_RX.finditer(html):
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        for item in data if isinstance(data, list) else [data]:
            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                return _strip_pii(item)
    return None


def _parse_job_id_from_path(path: Path, item: dict[str, Any]) -> str:
    stem = path.stem
    if stem.startswith("job_"):
        return stem[4:]
    ident = item.get("identifier")
    if isinstance(ident, dict) and ident.get("value"):
        return str(ident["value"])
    return stem


def parse_raw_directories(raw_dirs: list[Path]) -> tuple[list[dict[str, Any]], int, int]:
    """Parse HTML files across raw_dirs and deduplicate by (source, source_job_id)."""
    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    n_files = 0
    n_failed = 0

    for raw_dir in raw_dirs:
        if not raw_dir.exists():
            continue
        for html_file in sorted(raw_dir.glob("job_*.html")):
            n_files += 1
            item = extract_jobposting_from_html(html_file)
            if not item:
                n_failed += 1
                continue

            source = "jobthai"
            source_job_id = _parse_job_id_from_path(html_file, item)
            source_url = item.get("url") or f"https://www.jobthai.com/th/company/job/{source_job_id}"

            title = clean_html_text(item.get("title"), scrub_pii=True)
            desc = clean_html_text(item.get("description"), scrub_pii=True)
            qual = clean_html_text(item.get("qualifications"), scrub_pii=True)
            company_raw = scrub_hr_pii((item.get("hiringOrganization") or {}).get("name"))

            loc = item.get("jobLocation") or {}
            if isinstance(loc, list):
                loc = loc[0] if loc else {}
            addr = (loc or {}).get("address") or {}

            base_sal = item.get("baseSalary") or {}
            sal_val = base_sal.get("value") if isinstance(base_sal, dict) else {}
            if not isinstance(sal_val, dict):
                sal_val = {}

            edu_struct = item.get("educationRequirements")
            edu_cred = edu_struct.get("credentialCategory") if isinstance(edu_struct, dict) else None
            exp_struct = item.get("experienceRequirements")
            exp_months = exp_struct.get("monthsOfExperience") if isinstance(exp_struct, dict) else None

            hash_payload = json.dumps(
                {
                    "title": title,
                    "company": company_raw,
                    "desc": desc,
                    "qual": qual,
                    "sal": sal_val,
                    "region": addr.get("addressRegion"),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            content_hash = hashlib.sha256(hash_payload.encode("utf-8")).hexdigest()

            deduped[(source, source_job_id)] = {
                "source": source,
                "source_job_id": source_job_id,
                "source_url": source_url,
                "title": title,
                "description": desc,
                "qualifications": qual,
                "company_raw": company_raw,
                "province_raw": addr.get("addressRegion"),
                "district_raw": addr.get("addressLocality"),
                "occupational_category": normalize_thai_text(item.get("occupationalCategory")),
                "industry": normalize_thai_text(item.get("industry")),
                "employment_type": str(item.get("employmentType") or "FULL_TIME").strip() or "FULL_TIME",
                "date_posted": str(item.get("datePosted") or "")[:10] or None,
                "valid_through": str(item.get("validThrough") or "")[:10] or None,
                "salary_min_raw": sal_val.get("minValue"),
                "salary_max_raw": sal_val.get("maxValue"),
                "salary_value_raw": sal_val.get("value"),
                "salary_unit_raw": sal_val.get("unitText"),
                "edu_structured": edu_cred,
                "exp_months_structured": exp_months,
                "content_hash": content_hash,
            }

    return list(deduped.values()), n_files, n_failed


def process_postings(
    raw_records: list[dict[str, Any]],
    extractor: SkillExtractor,
    mapper: OccupationMapper,
    province_totals_csv: Path | str = DEFAULT_PROVINCE_TOTALS,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, float]]:
    """Clean, extract skills, map occupations, and compute stratified weights."""
    cleaned_rows: list[dict[str, Any]] = []
    corpus_texts: list[str] = []

    for rec in raw_records:
        title = rec.get("title") or ""
        desc = rec.get("description") or ""
        qual = rec.get("qualifications") or ""
        full_text = f"{title} {desc} {qual}".strip()
        corpus_texts.append(full_text)

        prov_meta = normalize_province(rec.get("province_raw"))
        dist_norm = normalize_district(rec.get("district_raw"))
        company_norm = normalize_company(rec.get("company_raw"))

        sal = normalize_salary(
            salary_text=rec.get("salary_text"),
            salary_min=rec.get("salary_min_raw"),
            salary_max=rec.get("salary_max_raw"),
            salary_value=rec.get("salary_value_raw"),
            salary_unit=rec.get("salary_unit_raw"),
        )
        edu_band = extract_education(full_text, qual_text=qual, edu_structured=rec.get("edu_structured"))
        exp_band = extract_experience(full_text, qual_text=qual, exp_months_structured=rec.get("exp_months_structured"))
        mentions_gender, mentions_age = detect_gender_age_mentions(full_text)

        matched_map = extractor.extract_with_matches(full_text)
        skills_list = sorted(matched_map.keys(), key=lambda name: extractor.skills_by_name[name].skill_key)
        occ_info = mapper.map_posting(title, rec.get("occupational_category"))

        cleaned_rows.append(
            {
                "source": rec["source"],
                "source_job_id": rec["source_job_id"],
                "source_url": rec["source_url"],
                "title_short": occ_info["title_short"],
                "job_title_norm": occ_info["job_title_norm"],
                "company_raw": rec.get("company_raw"),
                "company_name_norm": company_norm,
                "province_code": prov_meta["province_code"],
                "province_th": prov_meta["province_th"],
                "province_en": prov_meta["province_en"],
                "district_th": dist_norm,
                "region": prov_meta["region"],
                "is_south14": prov_meta["is_south14"],
                "occupational_category": rec.get("occupational_category") or "",
                "occupation_cluster": occ_info["occupation_cluster"],
                "occupation_slug": occ_info["occupation_slug"],
                "occupation_name_th": occ_info["occupation_name_th"],
                "onet_ref": occ_info["onet_ref"],
                "occupation_mapped": occ_info["mapped"],
                "industry": rec.get("industry") or "",
                "employment_type": rec.get("employment_type") or "FULL_TIME",
                "date_posted": rec.get("date_posted"),
                "valid_through": rec.get("valid_through"),
                "salary_min": sal.salary_min,
                "salary_max": sal.salary_max,
                "salary_mid": sal.salary_mid,
                "salary_open_max": sal.salary_open_max,
                "salary_unit_orig": sal.salary_unit_orig,
                "salary_out_of_range": sal.salary_out_of_range,
                "has_salary": sal.salary_mid is not None,
                "education_level": edu_band,
                "experience_band": exp_band,
                "n_skills": len(skills_list),
                "skills": "|".join(skills_list),
                "skills_list": skills_list,
                "matched_aliases": matched_map,
                "mentions_gender": mentions_gender,
                "mentions_age": mentions_age,
                "content_hash": rec["content_hash"],
            }
        )

    dates = [r["date_posted"] for r in cleaned_rows if r.get("date_posted")]
    default_seen = max(dates) if dates else dt.date.today().isoformat()
    stratum_pop = compute_weights_and_seen_dates(
        cleaned_rows,
        province_totals_csv=province_totals_csv,
        default_seen_date=default_seen,
    )
    pending_aliases = extractor.discover_pending_aliases(corpus_texts, top_n=100, min_freq=2, min_similarity=0.4)
    return cleaned_rows, pending_aliases, stratum_pop


def write_clean_postings_csv(rows: list[dict[str, Any]], out_csv: Path) -> Path:
    """Export clean_postings.csv strictly WITHOUT description/qualifications or HR PII."""
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CLEAN_CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return out_csv


def write_dq_report(
    out_md: Path,
    postings: list[dict[str, Any]],
    dq_results: list[dict[str, Any]],
    pending_aliases: list[dict[str, Any]],
    n_files: int,
    n_failed: int,
    marts: dict[str, Any],
) -> Path:
    """Generate docs/dq-report.md summarizing pipeline metrics and 8-dimension DQ results."""
    n = len(postings)
    ps = marts["public_summary"]
    occ_mapped = sum(1 for p in postings if p.get("occupation_mapped"))
    edu_found = sum(1 for p in postings if p.get("education_level") != "ไม่ระบุ")
    exp_found = sum(1 for p in postings if p.get("experience_band") != "ไม่ระบุ/ไม่จำเป็น")
    gender_pct = 100.0 * sum(1 for p in postings if p.get("mentions_gender")) / n if n else 0.0
    age_pct = 100.0 * sum(1 for p in postings if p.get("mentions_age")) / n if n else 0.0

    reg_counts = Counter(p["region"] for p in postings)
    occ_counts = Counter(p["occupation_cluster"] for p in postings)
    sk_counts = Counter(s for p in postings for s in p.get("skills_list", []))

    lines: list[str] = [
        "# รายงานคุณภาพข้อมูล (Data Quality Report — T3.3 / T8.2)",
        "",
        f"> **แหล่งข้อมูล:** JobThai HTML Snapshot · **ไฟล์ที่อ่าน:** {n_files} ไฟล์ (ล้มเหลว {n_failed}) · **ประกาศหลังหักซ้ำ (Unique Postings):** {n} ประกาศ",
        "",
        "## 1. สรุปภาพรวม (Summary Metrics)",
        "",
        "| ตัวชี้วัด | ค่า | เกณฑ์เป้าหมาย |",
        "|---|---|---|",
        f"| จำนวนประกาศที่ไม่ซ้ำ (`fact_job_posting`) | {n} | — |",
        f"| ครอบคลุมจังหวัด | {ps['n_provinces']} จังหวัด | — |",
        f"| ระบุเงินเดือนตัวเลขถูกต้อง `[5,000–500,000]` | {ps['n_with_salary']}/{n} ({ps['pct_with_salary']}%) | — |",
        f"| ดึงทักษะได้ `>= 1` ทักษะ | {ps['n_with_skills']}/{n} ({ps['pct_with_skills']}%) | >= 90% |",
        f"| ค่าเฉลี่ยทักษะต่อประกาศ | {ps['avg_skills_per_posting']} | — |",
        f"| จัดกลุ่ม Occupation Cluster ได้ | {occ_mapped}/{n} ({100.0 * occ_mapped / n:.1f}%) | >= 85% |",
        f"| ดึงวุฒิการศึกษาได้ | {edu_found}/{n} ({100.0 * edu_found / n:.1f}%) | >= 80% |",
        f"| ดึงประสบการณ์ทำงานได้ | {exp_found}/{n} ({100.0 * exp_found / n:.1f}%) | รายงานตรงตามข้อมูล |",
        f"| ระบุเพศ / อายุ (ติดตามเพื่อ Fairness เท่านั้น, ห้ามเข้า ML) | {gender_pct:.1f}% / {age_pct:.1f}% | 0% ใน ML features |",
        "",
        "## 2. ผลการตรวจสอบคุณภาพข้อมูล 8 ด้าน (Data Quality Checks)",
        "",
        "| ด้าน (Dimension) | Check | ตาราง | จำนวนตรวจ | ไม่ผ่าน | ผลลัพธ์ | รายละเอียด |",
        "|---|---|---|---:|---:|:---:|---|",
    ]
    for dq in dq_results:
        badge = "PASS" if dq["pass"] else "FAIL"
        lines.append(
            f"| {dq['dimension']} | `{dq['check_name']}` | `{dq['table_name']}` | {dq['n_total']} | {dq['n_fail']} | **{badge}** | {dq['details']} |"
        )

    lines.extend(
        [
            "",
            "## 3. การกระจายตามภูมิภาคและกลุ่มอาชีพ",
            "",
            "### ภูมิภาค (Region)",
            "| ภูมิภาค | จำนวนประกาศ |",
            "|---|---:|",
        ]
    )
    for reg, cnt in reg_counts.most_common():
        lines.append(f"| {reg} | {cnt} |")

    lines.extend(
        [
            "",
            "### กลุ่มอาชีพ (Top 15 Occupation Clusters)",
            "| กลุ่มอาชีพ | จำนวนประกาศ |",
            "|---|---:|",
        ]
    )
    for occ, cnt in occ_counts.most_common(15):
        lines.append(f"| {occ} | {cnt} |")

    lines.extend(
        [
            "",
            "## 4. ทักษะยอดนิยมที่สกัดได้และคิว Alias Pending",
            "",
            "### Top 15 Skills",
            "| ทักษะ | จำนวนประกาศ |",
            "|---|---:|",
        ]
    )
    for sk, cnt in sk_counts.most_common(15):
        lines.append(f"| {sk} | {cnt} |")

    lines.extend(
        [
            "",
            f"### ตัวอย่างคำใหม่ในคิว Alias Pending (Top 15 จากทั้งหมด {len(pending_aliases)} คำ — ใช้กฎ `pg_trgm similarity >= 0.4` ไม่ใช้ AI)",
            "| คำที่พบ | ความถี่ (ประกาศ) | ทักษะที่กฎเสนอ | Alias ที่คล้ายที่สุด | Similarity |",
            "|---|---:|---|---|---:|",
        ]
    )
    for item in pending_aliases[:15]:
        sim_str = f"{item['similarity_score']:.3f}" if item.get("similarity_score") is not None else "-"
        lines.append(
            f"| `{item['alias']}` | {item['freq']} | {item.get('suggested_skill_canonical') or '-'} | {item.get('suggested_matched_alias') or '-'} | {sim_str} |"
        )

    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_md


def run_pipeline(
    raw_dirs: list[Path],
    out_dir: Path,
    province_totals_csv: Path = DEFAULT_PROVINCE_TOTALS,
    dq_report_path: Path = REPO_ROOT / "docs" / "dq-report.md",
    database_url: str | None = None,
) -> dict[str, Any]:
    """Run full offline ETL + optional Postgres upsert."""
    extractor = SkillExtractor()
    mapper = OccupationMapper()

    raw_records, n_files, n_failed = parse_raw_directories(raw_dirs)
    postings, pending_aliases, stratum_pop = process_postings(
        raw_records, extractor, mapper, province_totals_csv=province_totals_csv
    )

    dq_results = run_dq_checks(
        postings,
        stratum_population=stratum_pop,
        pending_aliases=pending_aliases,
    )

    clean_csv = write_clean_postings_csv(postings, out_dir / "clean_postings.csv")
    marts = build_all_marts(postings, dq_results, pending_aliases, extractor, mapper)
    seed_json = write_seed_marts(marts, out_dir / "seed_marts.json")
    report_path = write_dq_report(dq_report_path, postings, dq_results, pending_aliases, n_files, n_failed, marts)

    db_counts = None
    if database_url:
        db_counts = upsert_dw_to_postgres(
            database_url=database_url,
            postings=postings,
            dq_results=dq_results,
            pending_aliases=pending_aliases,
            extractor=extractor,
            mapper=mapper,
            scrape_run_meta={
                "source": "jobthai",
                "scope": "etl_pipeline",
                "status": "done",
                "n_discovered": n_files,
                "n_fetched": len(postings),
                "n_failed": n_failed,
            },
        )

    return {
        "n_files": n_files,
        "n_failed": n_failed,
        "n_unique": len(postings),
        "clean_csv": str(clean_csv),
        "seed_json": str(seed_json),
        "dq_report": str(report_path),
        "dq_results": dq_results,
        "marts": marts,
        "postings": postings,
        "pending_aliases": pending_aliases,
        "db_counts": db_counts,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Skill Demand Intelligence ETL pipeline.")
    parser.add_argument(
        "--raw-dirs",
        nargs="+",
        default=["spike/raw/jobthai/sample", "spike/raw/jobthai/by_province"],
        help="Directories containing raw job_*.html files.",
    )
    parser.add_argument("--out-dir", default="data/processed", help="Output directory for processed artifacts.")
    parser.add_argument(
        "--province-totals",
        default=str(DEFAULT_PROVINCE_TOTALS),
        help="Reference province_totals.csv for stratified weights.",
    )
    parser.add_argument("--dq-report", default="docs/dq-report.md", help="Output path for Markdown DQ report.")
    parser.add_argument("--load-db", action="store_true", help="Load into Postgres using DATABASE_URL env var.")
    parser.add_argument("--database-url", default=None, help="Explicit Postgres connection string.")
    args = parser.parse_args()

    db_url = args.database_url or (os.getenv("DATABASE_URL") if args.load_db else None)
    res = run_pipeline(
        raw_dirs=[Path(d) for d in args.raw_dirs],
        out_dir=Path(args.out_dir),
        province_totals_csv=Path(args.province_totals),
        dq_report_path=Path(args.dq_report),
        database_url=db_url,
    )
    ps = res["marts"]["public_summary"]
    occ_cov = 100.0 * sum(1 for p in res["postings"] if p["occupation_mapped"]) / max(1, res["n_unique"])
    print(
        f"ETL done: files={res['n_files']} unique={res['n_unique']} "
        f"skill_cov={ps['pct_with_skills']}% occ_cov={occ_cov:.1f}% "
        f"with_salary={ps['n_with_salary']} ({ps['pct_with_salary']}%) "
        f"pending_aliases={len(res['pending_aliases'])}"
    )
    for dq in res["dq_results"]:
        print(f"  [{'PASS' if dq['pass'] else 'FAIL'}] {dq['check_name']}: {dq['details']}")


if __name__ == "__main__":
    main()
