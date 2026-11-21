"""Unit & integration tests for taxonomy, skill extraction, DQ checks, and eval (T2.3-T2.7, T3.3, T3.7)."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from eval.evaluate_skills import compute_cohens_kappa, evaluate_predictions
from eval.prepare_gold_set import TEMPLATE_COLUMNS, stratified_sample_rows
from pipeline.etl.clean import contains_hr_pii
from pipeline.etl.extract_skills import SkillExtractor, trigram_similarity
from pipeline.etl.map_taxonomy import OccupationMapper
from pipeline.etl.run_pipeline import run_pipeline
from pipeline.etl.validate import (
    FORBIDDEN_HR_COLUMNS,
    FORBIDDEN_ML_COLUMNS,
    FORBIDDEN_PUBLIC_TEXT_COLUMNS,
    run_dq_checks,
)


def test_taxonomy_files_meet_thresholds():
    with open(REPO_ROOT / "taxonomy" / "skills.csv", encoding="utf-8") as f:
        skills = list(csv.DictReader(f))
    with open(REPO_ROOT / "taxonomy" / "aliases.csv", encoding="utf-8") as f:
        aliases = list(csv.DictReader(f))
    with open(REPO_ROOT / "taxonomy" / "occupations.csv", encoding="utf-8") as f:
        occupations = list(csv.DictReader(f))

    assert len(skills) >= 110
    assert {"tool", "technical", "soft", "language", "licence"} == {s["skill_type"] for s in skills}
    assert len(aliases) >= 250
    assert len({a["alias"] for a in aliases}) == len(aliases), "Aliases must be globally unique"
    assert 18 <= len(occupations) <= 22
    for occ in occupations:
        assert None not in occ, f"Malformed CSV row in occupations.csv: {occ}"
        assert occ["occupation_slug"].replace("-", "").isalnum() and occ["occupation_slug"] == occ["occupation_slug"].lower()


def test_word_boundaries_and_false_positive_guards():
    ext = SkillExtractor()

    # Word should match MS Word but NOT keyword/password/forward
    assert "Microsoft Word" in ext.extract_skills("ใช้งาน Microsoft Excel และ Word ได้คล่อง")
    assert "Microsoft Word" not in ext.extract_skills("Check password, keyword, and forward emails")

    # R should match R programming but NOT HR, R&D, A/R, Car
    assert "R Programming" in ext.extract_skills("Required: Python, R, SQL")
    assert "R Programming" not in ext.extract_skills("ติดต่อ HR หรือ R&D และดูแลบัญชี A/R ด้วย Car")

    # C should match C programming but NOT C#, C++, PC, QC
    assert "C Programming" in ext.extract_skills("พัฒนาโปรแกรมด้วยภาษา C และ Python")
    assert "C Programming" not in ext.extract_skills("PC ขายสินค้า และตรวจสอบ QC ด้วยระบบ C# / C++")

    # Go should match Golang/Go language but NOT "go to"
    assert "Go (Golang)" in ext.extract_skills("Backend using Golang and Docker")
    assert "Go (Golang)" not in ext.extract_skills("Willing to go to customer sites")

    # SQL word boundary should NOT falsely trigger on MySQL alone
    skills_mysql = ext.extract_skills("บริหารฐานข้อมูล MySQL")
    assert "MySQL" in skills_mysql
    assert "SQL" not in skills_mysql
    assert "SQL" in ext.extract_skills("เขียนคำสั่ง SQL และ Power BI")

    # Thai ambiguity guards
    assert "Sales & Closing" not in ext.extract_skills("สรุปรายงานยอดขายประจำวันและกระทบยอดบัญชี")
    assert "Sales & Closing" in ext.extract_skills("พนักงานขาย เสนอขายและปิดการขายสินค้า")
    assert "Electrical Systems" not in ext.extract_skills("ออฟฟิศติดรถไฟฟ้า BTS เดินทางสะดวก")
    assert "Nursing & Clinical Care" not in ext.extract_skills("สวัสดิการประกันสังคมและค่ารักษาพยาบาล")
    assert "Heavy Truck Licence (ท.2/บ.2)" not in ext.extract_skills("เปิดรับ 2 อัตรา ประจำสาขา")
    assert "Heavy Truck Licence (ท.2/บ.2)" in ext.extract_skills("มีใบอนุญาตขับขี่ ท.2 หรือ บ.2")


SPIKE_SAMPLE_DIR = REPO_ROOT / "spike" / "raw" / "jobthai" / "sample"
FIXTURE_POSTINGS_DIR = REPO_ROOT / "pipeline" / "tests" / "fixtures" / "jobthai_postings"
FIXTURE_PROVINCE_TOTALS = REPO_ROOT / "pipeline" / "tests" / "fixtures" / "province_totals.csv"


@pytest.mark.skipif(not SPIKE_SAMPLE_DIR.exists(), reason="spike/raw/jobthai not present in clean git clone")
def test_pipeline_end_to_end_on_131_sample_postings(tmp_path):
    res = run_pipeline(
        raw_dirs=[
            REPO_ROOT / "spike" / "raw" / "jobthai" / "sample",
            REPO_ROOT / "spike" / "raw" / "jobthai" / "by_province",
        ],
        out_dir=tmp_path / "processed",
        dq_report_path=tmp_path / "dq-report.md",
    )
    postings = res["postings"]
    n = len(postings)
    assert res["n_files"] == 131
    assert res["n_failed"] == 0
    assert n == 126  # 5 job IDs appear in both sample and by_province

    skill_cov = sum(1 for p in postings if p["n_skills"] >= 1) / n
    occ_cov = sum(1 for p in postings if p["occupation_mapped"]) / n
    assert skill_cov >= 0.90, f"Skill coverage {skill_cov:.1%} < 90%"
    assert occ_cov >= 0.85, f"Occupation coverage {occ_cov:.1%} < 85%"

    # Pending alias queue uses pg_trgm similarity >= 0.4 and caps at <= 100
    pending = res["pending_aliases"]
    assert 0 < len(pending) <= 100
    assert trigram_similarity("เอ็กเซลล", "เอ็กเซล") >= 0.4

    # All 8 DQ checks pass
    dq = res["dq_results"]
    assert len({d["dimension"] for d in dq}) == 8
    assert all(d["pass"] for d in dq), f"Failed DQ: {[d for d in dq if not d['pass']]}"

    # ToS & PDPA verification on CSV and seed_marts.json (columns AND value-level PII check)
    with open(res["clean_csv"], encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        cols = set(reader.fieldnames or [])
        assert not (cols & FORBIDDEN_HR_COLUMNS)
        assert not (cols & FORBIDDEN_PUBLIC_TEXT_COLUMNS)
        for row in reader:
            for col in ("title_short", "company_name_norm", "source_url"):
                assert not contains_hr_pii(row.get(col)), f"PII leak in {col}: {row.get(col)}"

    marts = json.loads(Path(res["seed_json"]).read_text(encoding="utf-8"))
    for key in (
        "public_summary",
        "skill_demand_weekly",
        "skill_cooccurrence",
        "occupation_skill_profile",
        "salary_stats",
        "posting_volume_daily",
        "curriculum_coverage_ref",
        "pipeline_status",
        "dq_summary",
        "top_links",
        "pending_aliases",
        "dim_skills",
        "dim_occupations",
        "dim_locations",
    ):
        assert key in marts

    # Zero raw description/qualifications and zero HR PII in top_links or pending_aliases
    for link in marts["top_links"]:
        assert not (set(link.keys()) & FORBIDDEN_PUBLIC_TEXT_COLUMNS)
        assert not contains_hr_pii(link.get("title_short")), f"PII leak in top_links: {link.get('title_short')}"
        assert link["n_postings"] >= 5
    for pa in marts["pending_aliases"]:
        assert "description" not in pa and "qualifications" not in pa and "sample_context" not in pa

    # Verify n < 5 suppression on occupation_skill_profile
    for row in marts["occupation_skill_profile"]:
        if row["n_postings"] < 5 or row["n_occ_postings"] < 5:
            assert row["is_suppressed"] is True
            assert row["weighted_share"] is None
            assert row["raw_share"] is None


def test_pipeline_end_to_end_on_fixtures(tmp_path):
    res = run_pipeline(
        raw_dirs=[FIXTURE_POSTINGS_DIR],
        out_dir=tmp_path / "processed",
        province_totals_csv=FIXTURE_PROVINCE_TOTALS,
        dq_report_path=tmp_path / "dq-report.md",
        strata_csv=None,
    )
    postings = res["postings"]
    assert res["n_files"] == 21
    assert res["n_failed"] == 0
    assert len(postings) == 21
    assert all(p["n_skills"] >= 1 for p in postings)
    assert all(d["pass"] for d in res["dq_results"])

    marts = json.loads(Path(res["seed_json"]).read_text(encoding="utf-8"))
    for key in ("public_summary", "skill_demand_weekly", "occupation_skill_profile", "salary_stats", "top_links"):
        assert key in marts
    for link in marts["top_links"]:
        assert not (set(link.keys()) & FORBIDDEN_PUBLIC_TEXT_COLUMNS)
        assert link["n_postings"] >= 5


def test_dq_compliance_flags_forbidden_columns():
    fake_postings = [
        {
            "source": "jobthai",
            "source_job_id": "1",
            "title_short": "Sales ติดต่อ 098-250-6742 คุณกุ๊ก",
            "province_th": "สงขลา",
            "occupational_category": "งานขาย",
            "company_name_norm": "abc",
            "has_salary": True,
            "salary_min": 20000,
            "salary_max": 25000,
            "salary_mid": 22500,
            "date_posted": "2026-11-18",
            "occupation_mapped": True,
            "occupation_cluster": "Data & Analytics",
            "n_skills": 2,
            "sample_stratum": "p=57|c=all",
            "sample_weight": 1.0,
            "content_hash": "h1",
            "telephone": "0812345678",  # Forbidden HR PII leak
        }
    ]
    dq = run_dq_checks(fake_postings, ml_feature_columns=["occupation_cluster", "gender", "age"])
    comp = next(d for d in dq if d["dimension"] == "Compliance")
    assert comp["pass"] is False
    assert comp["n_fail"] >= 4  # telephone + title_short phone value + gender + age
    assert "gender" in FORBIDDEN_ML_COLUMNS and "age" in FORBIDDEN_ML_COLUMNS


def test_gold_set_template_and_evaluation_metrics():
    sample_rows = [
        {
            "source_job_id": f"id_{i}",
            "source_url": f"https://www.jobthai.com/th/company/job/{i}",
            "title_short": f"Role {i}",
            "occupational_category": "งานขาย",
            "occupation_cluster": "Sales & Business Development" if i % 2 == 0 else "Data & Analytics",
            "province_th": "กรุงเทพมหานคร",
            "description": "SHOULD_NOT_APPEAR",
        }
        for i in range(20)
    ]
    tpl = stratified_sample_rows(sample_rows, target_n=12, overlap_n=4, seed=42)
    assert len(tpl) == 12
    assert sum(1 for r in tpl if r["annotator_group"] == "overlap_50") >= 1
    assert set(tpl[0].keys()) == set(TEMPLATE_COLUMNS)
    assert "description" not in tpl[0]

    # Precision, recall (within taxonomy), F1 per skill_group, OOV rate, and Cohen's kappa
    gold_rows = [
        {
            "source_job_id": "1",
            "gold_skills_a": "Microsoft Excel|SQL|UnknownToolXYZ",
            "gold_skills_b": "Microsoft Excel|SQL",
            "out_of_taxonomy_skills": "UnknownToolXYZ",
        },
        {
            "source_job_id": "2",
            "gold_skills_a": "Python|English",
            "gold_skills_b": "Python|English",
            "out_of_taxonomy_skills": "",
        },
    ]
    pred_by_id = {
        "1": "Microsoft Excel|Power BI",  # TP=Excel, FP=Power BI, FN=SQL (UnknownToolXYZ is OOV, not penalized in recall)
        "2": "Python|English",  # TP=Python, English
    }
    report = evaluate_predictions(gold_rows, pred_by_id)
    assert report["overall"]["tp"] == 3
    assert report["overall"]["fp"] == 1
    assert report["overall"]["fn"] == 1
    assert report["overall"]["precision"] == 0.75
    assert report["overall"]["recall"] == 0.75
    assert report["overall"]["f1"] == 0.75
    assert "Data & BI" in report["per_group"]
    assert report["oov_mentions"] == 1
    assert report["oov_rate"] == 0.2  # 1 OOV / (4 in-tax + 1 OOV)
    assert 0.7 < report["cohens_kappa"] <= 1.0
    assert compute_cohens_kappa(
        [{"gold_skills_a": "SQL|Python", "gold_skills_b": "SQL|Python"}],
        canonical_skills={"SQL", "Python", "Microsoft Excel"},
    ) == 1.0
