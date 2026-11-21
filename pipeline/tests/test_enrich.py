"""Tests for pipeline.etl.enrich (derived columns, rule-based, no LLM)."""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest  # noqa: E402

from pipeline.etl.enrich import (  # noqa: E402
    ENRICH_COLUMNS,
    ML_CATEGORICAL_ENRICH,
    ML_NUMERIC_ENRICH,
    benefit_flags,
    employment_type_derived,
    enrich_fields,
    salary_disclosure,
    seniority,
)
from pipeline.ml.features import is_forbidden_feature_name  # noqa: E402


@pytest.mark.parametrize(
    "title,level",
    [
        ("Senior Accountant (Overseas Subsidiaries)", "senior"),
        ("Service Engineer Manager", "manager"),
        ("ผู้ช่วยผู้จัดการฝ่ายขาย", "supervisor"),
        ("Assistant Manager - HR", "supervisor"),
        ("กรรมการผู้จัดการ", "director"),
        ("หัวหน้าแผนกบัญชีและการเงิน", "supervisor"),
        ("เจ้าหน้าที่บัญชี (ประจำ กทม.)", "officer"),
        ("Sales Account Executive", "officer"),
        ("วิศวกร (ไฟฟ้า)", "officer"),
        ("พนักงานโกดัง (เดินบิล)", "staff"),
        ("ช่างซ่อมบำรุง สัญญาจ้าง3เดือน", "staff"),
        ("นักศึกษาฝึกงาน IT", "intern"),
        ("Junior Developer", "junior"),
        ("ธุรการการตลาดงานป้าย", "staff"),
        ("Brand Marketing", "ไม่ระบุ"),
    ],
)
def test_seniority_from_title(title: str, level: str) -> None:
    assert seniority(title)[0] == level


def test_seniority_rank_is_ordered() -> None:
    ranks = [seniority(t)[1] for t in ("ฝึกงาน", "พนักงานขาย", "เจ้าหน้าที่", "Senior Engineer",
                                        "หัวหน้างาน", "ผู้จัดการ", "Director of Sales")]
    assert ranks == sorted(ranks) and len(set(ranks)) == 7


def test_benefits_thai_run_together_and_english_bullets() -> None:
    th = "ประกันสังคมประกันอุบัติเหตุกองทุนสำรองเลี้ยงชีพโบนัสประจำปีปรับเงินเดือนประจำปีเสื้อยูนิฟอร์มการฝึกอบรม"
    f = benefit_flags(th)
    assert f["benefit_social_security"] and f["benefit_provident_fund"] and f["benefit_bonus"]
    assert f["benefit_health_insurance"] and f["benefit_salary_raise"] and f["benefit_uniform"] and f["benefit_training"]
    assert not f["benefit_housing"] and not f["benefit_commission"]
    en = "• Annual Leave (14 days/year)• Health Insurance• Provident Fund• Uniform• Fuel expense"
    g = benefit_flags(en)
    assert g["benefit_annual_leave"] and g["benefit_health_insurance"] and g["benefit_provident_fund"]
    assert g["benefit_transport"] and g["n_benefit_types"] == 5
    assert benefit_flags(None)["n_benefit_types"] == 0


def test_employment_type_from_title_beats_body() -> None:
    assert employment_type_derived("ช่างซ่อมบำรุง สัญญาจ้าง3เดือน", "") == "contract"
    assert employment_type_derived("พนักงานขาย Part Time", "") == "part_time"
    assert employment_type_derived("นักศึกษาฝึกงาน", "") == "internship"
    # a contract mentioned only in the body is not enough (often "ผ่านทดลองงานบรรจุ...สัญญาจ้าง")
    assert employment_type_derived("พนักงานบัญชี", "ทำสัญญาจ้างหลังผ่านทดลองงาน") == "full_time"


def test_salary_disclosure_categories() -> None:
    assert salary_disclosure(True, "13,500 - 28,000 บาท") == "numeric"
    assert salary_disclosure(False, "ตามโครงสร้างบริษัทฯ") == "company_structure"
    assert salary_disclosure(False, "ตามตกลง") == "negotiable"
    assert salary_disclosure(False, "ตามประสบการณ์และความสามารถ") == "by_experience"
    assert salary_disclosure(False, None) == "unknown"


def test_enrich_fields_full_row() -> None:
    payload = {
        "jobBenefits": "ประกันสังคม โบนัส ** ทำงานวันจันทร์ - ศุกร์ (หยุดวันเสาร์ - อาทิตย์)",
        "x_jobthai": {"positions": 3, "positions_text": "3 อัตรา", "salary_text": "ตามตกลง",
                      "urgent": True, "near_transit": False, "industrial_estate": "นิคมอมตะซิตี้",
                      "online_interview": True},
    }
    row = enrich_fields(
        title="Call Center (English Skill) ยินดีรับนักศึกษาจบใหม่",
        description="ทำงานเป็นกะ Work from home ได้บางวัน",
        payload=payload,
        has_numeric_salary=False,
        first_seen="2026-11-19",
        last_seen="2026-11-28",
    )
    assert set(row) == set(ENRICH_COLUMNS)
    assert row["accepts_fresh_grad"] and row["is_remote"] and row["shift_work"]
    assert row["work_days_per_week"] == 5
    assert row["positions"] == 3 and row["positions_many"] is False
    assert row["salary_disclosure"] == "negotiable"
    assert row["urgent"] is True and row["in_industrial_estate"] is True and row["online_interview"] is True
    assert row["days_listed"] == 10
    assert row["n_benefit_types"] == 2


def test_enrich_without_harvest_extras_gives_unknowns_not_errors() -> None:
    row = enrich_fields(title="พนักงานขาย", payload={"baseSalary": {"value": {"minValue": 1}}})
    assert row["urgent"] is None and row["positions"] is None and row["in_industrial_estate"] is None
    assert row["salary_disclosure"] == "numeric" and row["days_listed"] is None


def test_ml_enrich_features_pass_the_forbidden_guard() -> None:
    for col in (*ML_CATEGORICAL_ENRICH, *ML_NUMERIC_ENRICH):
        assert not is_forbidden_feature_name(col), col
    # salary_disclosure describes the target itself -> analysis column only, and the guard knows it
    assert is_forbidden_feature_name("salary_disclosure")
    assert "salary_disclosure" not in (*ML_CATEGORICAL_ENRICH, *ML_NUMERIC_ENRICH)
