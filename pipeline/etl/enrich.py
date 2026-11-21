"""Derived columns from data we already collect (no extra scraping) — "B" in docs/data-dictionary.md.

All rules are plain keyword/regex rules (no LLM, AGENTS.md D7/D18). Inputs are the posting's
title, description, qualifications, the (PDPA-scrubbed) JSON-LD payload and its `x_jobthai`
block written by scraper/jobthai_harvester.py, plus first/last seen dates.

Nothing here reads or produces gender, age, company name or HR contact data.

Usage:
    from pipeline.etl.enrich import enrich_fields, ENRICH_COLUMNS
    row.update(enrich_fields(title=..., description=..., qualifications=..., payload=...,
                             first_seen="2026-11-19", last_seen="2026-11-28"))
"""
from __future__ import annotations

import datetime as dt
import re
from typing import Any, Mapping

# --------------------------------------------------------------------------- benefits
# flag -> keywords (Thai / English); matched in jobBenefits (+ description for a few)
BENEFIT_RULES: dict[str, tuple[str, ...]] = {
    "benefit_social_security": ("ประกันสังคม", "social security"),
    "benefit_bonus": ("โบนัส", "bonus"),
    "benefit_provident_fund": ("กองทุนสำรองเลี้ยงชีพ", "provident fund"),
    "benefit_health_insurance": ("ประกันสุขภาพ", "ประกันชีวิต", "ประกันอุบัติเหตุ", "ประกันกลุ่ม",
                                 "health insurance", "life insurance", "accident insurance", "medical"),
    "benefit_annual_checkup": ("ตรวจสุขภาพ", "health check"),
    "benefit_overtime": ("ค่าล่วงเวลา", "โอที", "overtime"),
    "benefit_commission": ("คอมมิชชั่น", "คอมมิชชัน", "commission", "incentive", "อินเซนทีฟ", "ค่าคอม"),
    "benefit_transport": ("รถรับส่ง", "ค่าเดินทาง", "ค่าน้ำมัน", "shuttle", "transportation", "fuel"),
    "benefit_housing": ("ที่พัก", "หอพัก", "ค่าเช่าบ้าน", "accommodation", "housing"),
    "benefit_meal": ("ค่าอาหาร", "อาหารกลางวัน", "อาหารฟรี", "meal"),
    "benefit_annual_leave": ("วันหยุดพักผ่อน", "ลาพักร้อน", "พักร้อน", "annual leave"),
    "benefit_training": ("ฝึกอบรม", "อบรม", "training"),
    "benefit_uniform": ("ยูนิฟอร์ม", "เครื่องแบบ", "uniform"),
    "benefit_salary_raise": ("ปรับเงินเดือน", "salary increase", "salary adjustment"),
}

# --------------------------------------------------------------------------- seniority
# checked top-down; first match wins (assistant manager must be checked before manager)
SENIORITY_RULES: tuple[tuple[str, int, tuple[str, ...]], ...] = (
    ("director", 6, ("ผู้อำนวยการ", "กรรมการผู้จัดการ", r"\bdirector\b", r"\bhead of\b", r"\bvp\b",
                     "vice president", r"\bchief\b", r"\bc[eft]o\b")),
    ("supervisor", 4, ("ผู้ช่วยผู้จัดการ", r"\bassistant manager\b", r"\basst\.? manager\b")),
    ("manager", 5, ("ผู้จัดการ", r"\bmanager\b", r"\bmgr\b")),
    ("supervisor", 4, ("หัวหน้า", "ผู้ควบคุม", "โฟร์แมน", r"\bsupervisor\b", r"\bforeman\b",
                       r"\bteam lead", r"\bleader\b", r"\blead\b")),
    ("senior", 3, ("อาวุโส", r"\bsenior\b", r"\bsr\.?\b", r"\bsnr\.?\b")),
    ("intern", 0, ("ฝึกงาน", "นักศึกษาฝึก", r"\bintern", r"\btrainee\b")),
    ("junior", 1, (r"\bjunior\b", r"\bjr\.?\b")),
    ("officer", 2, ("เจ้าหน้าที่", "วิศวกร", "นักวิเคราะห์", "นักบัญชี", "นักพัฒนา", "นักออกแบบ",
                    "โปรแกรมเมอร์", "เภสัชกร", "พยาบาล", r"\bofficer\b", r"\bspecialist\b", r"\bexecutive\b",
                    r"\bengineer\b", r"\banalyst\b", r"\bcoordinator\b", r"\baccountant\b", r"\bdeveloper\b",
                    r"\bprogrammer\b", r"\bdesigner\b", r"\bconsultant\b", "ล่าม", "ที่ปรึกษา",
                    r"\binterpreter\b", r"\bpharmacist\b", r"\brepresentative\b", r"\badvisor\b",
                    r"\bplanner\b", r"\beditor\b", r"\bcreator\b", r"\bmerchandiser\b", r"\bimplementer\b")),
    ("staff", 1, ("พนักงาน", "ผู้ช่วย", "ช่าง", "แม่บ้าน", "คนขับ", "ขับรถ", "รปภ", "บาริสต้า", "ธุรการ", "แอดมิน",
                  r"\badmin\b", r"\bbarista\b", r"\bstaff\b", r"\boperator\b",
                  r"\bassistant\b", r"\bclerk\b", r"\btechnician\b", r"\bdriver\b", r"\bhelper\b")),
)
SENIORITY_UNKNOWN = "ไม่ระบุ"

# --------------------------------------------------------------------------- employment
EMPLOYMENT_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("internship", ("ฝึกงาน", "นักศึกษาฝึก", "internship", r"\bintern\b")),
    ("part_time", ("พาร์ทไทม์", "พาร์ตไทม์", "part time", "part-time", "parttime", "รายชั่วโมง")),
    ("freelance", ("ฟรีแลนซ์", "freelance")),
    ("contract", ("สัญญาจ้าง", "ชั่วคราว", "contract", "temporary", "fixed term", "fixed-term", "outsource",
                  "เอาท์ซอร์ส", "รายวัน")),
)

FRESH_GRAD_RX = re.compile(
    r"จบใหม่|นักศึกษาจบใหม่|ผู้ไม่มีประสบการณ์|ไม่มีประสบการณ์(?:ก็ได้|ก็สามารถ|สามารถ)?|ไม่จำเป็นต้องมีประสบการณ์"
    r"|new grad|fresh grad|no experience required",
    re.I,
)
REMOTE_RX = re.compile(r"work from home|\bwfh\b|\bremote\b|ทำงานที่บ้าน|ทำงานจากที่บ้าน|hybrid|ไฮบริด", re.I)
SHIFT_RX = re.compile(r"เข้ากะ|ทำงานเป็นกะ|หมุนเวียนกะ|\bกะ\s*(?:เช้า|ดึก|บ่าย|กลางคืน)|shift", re.I)
WORKDAY_RX = (
    (6, re.compile(r"จันทร์\s*[-–ถึง]+\s*เสาร์|monday\s*[-–to]+\s*saturday|6\s*วัน\s*(?:/|ต่อ)?\s*สัปดาห์|สัปดาห์ละ\s*6\s*วัน", re.I)),
    (5, re.compile(r"จันทร์\s*[-–ถึง]+\s*ศุกร์|monday\s*[-–to]+\s*friday|5\s*วัน\s*(?:/|ต่อ)?\s*สัปดาห์|สัปดาห์ละ\s*5\s*วัน", re.I)),
)

SALARY_POLICY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("negotiable", ("ตามตกลง", "ตกลงกัน", "negotiable")),
    ("company_structure", ("ตามโครงสร้าง", "structure")),
    ("by_experience", ("ตามประสบการณ์", "ตามความสามารถ", "ตามวุฒิ", "ขึ้นอยู่กับประสบการณ์", "experience")),
)

ENRICH_COLUMNS: tuple[str, ...] = (
    "seniority_level", "seniority_rank", "employment_type_derived", "accepts_fresh_grad", "is_remote",
    "shift_work", "work_days_per_week", "positions", "positions_many", "salary_disclosure",
    "n_benefit_types", *BENEFIT_RULES.keys(),
    "urgent", "near_transit", "in_industrial_estate", "online_interview", "days_listed",
)

# Features that can safely go into the salary model: a user can state them on the Salary page,
# so inference does not depend on posting-only facts.
ML_CATEGORICAL_ENRICH: tuple[str, ...] = ("seniority_level", "employment_type_derived")
ML_NUMERIC_ENRICH: tuple[str, ...] = ()


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return " ".join(_text(v) for v in value)
    return str(value)


def _has_any(text: str, patterns: tuple[str, ...]) -> bool:
    low = text.lower()
    for pat in patterns:
        if pat.startswith("\\b") or any(ch in pat for ch in "()[]|?+*"):
            if re.search(pat, low, re.I):
                return True
        elif pat.lower() in low:
            return True
    return False


def benefit_flags(job_benefits: Any) -> dict[str, Any]:
    text = _text(job_benefits)
    flags = {name: _has_any(text, pats) for name, pats in BENEFIT_RULES.items()}
    flags["n_benefit_types"] = sum(flags.values())
    return flags


def seniority(title: Any) -> tuple[str, int | None]:
    text = _text(title)
    for label, rank, pats in SENIORITY_RULES:
        if _has_any(text, pats):
            return label, rank
    return SENIORITY_UNKNOWN, None


def employment_type_derived(title: Any, text: Any) -> str:
    # the title is the strongest signal; the body may mention contracts in passing
    for label, pats in EMPLOYMENT_RULES:
        if _has_any(_text(title), pats):
            return label
    body = _text(text)
    for label, pats in EMPLOYMENT_RULES:
        if label != "contract" and _has_any(body, pats):
            return label
    return "full_time"


def salary_disclosure(has_numeric_salary: bool, salary_text: Any) -> str:
    if has_numeric_salary:
        return "numeric"
    text = _text(salary_text)
    if not text:
        return "unknown"
    for label, pats in SALARY_POLICY_RULES:
        if _has_any(text, pats):
            return label
    return "other"


def days_between(first_seen: Any, last_seen: Any) -> int | None:
    try:
        a = dt.date.fromisoformat(str(first_seen)[:10])
        b = dt.date.fromisoformat(str(last_seen)[:10])
    except ValueError:
        return None
    return (b - a).days + 1 if b >= a else None


def enrich_fields(
    *,
    title: Any = None,
    description: Any = None,
    qualifications: Any = None,
    payload: Mapping[str, Any] | None = None,
    has_numeric_salary: bool | None = None,
    first_seen: Any = None,
    last_seen: Any = None,
) -> dict[str, Any]:
    """All derived columns for one posting (see ENRICH_COLUMNS)."""
    payload = payload or {}
    x = payload.get("x_jobthai") or {}
    if not isinstance(x, Mapping):
        x = {}
    body = " ".join(_text(v) for v in (description, qualifications, payload.get("jobBenefits")))
    all_text = f"{_text(title)} {body}"

    level, rank = seniority(title)
    if has_numeric_salary is None:
        has_numeric_salary = bool(payload.get("baseSalary"))
    workdays = next((n for n, rx in WORKDAY_RX if rx.search(all_text)), None)
    remote = (
        str(payload.get("jobLocationType") or "").upper() == "TELECOMMUTE"
        or bool(payload.get("applicantLocationRequirements"))
        or bool(REMOTE_RX.search(all_text))
    )
    positions = x.get("positions")
    positions_text = _text(x.get("positions_text"))

    out: dict[str, Any] = {
        "seniority_level": level,
        "seniority_rank": rank,
        "employment_type_derived": employment_type_derived(title, body),
        "accepts_fresh_grad": bool(FRESH_GRAD_RX.search(all_text)),
        "is_remote": remote,
        "shift_work": bool(SHIFT_RX.search(all_text)),
        "work_days_per_week": workdays,
        "positions": int(positions) if isinstance(positions, (int, float)) and positions > 0 else None,
        "positions_many": "หลาย" in positions_text,
        "salary_disclosure": salary_disclosure(bool(has_numeric_salary), x.get("salary_text")),
        **benefit_flags(payload.get("jobBenefits")),
        # listing facts kept by the harvester (None = not seen on a listing page since 2026-11-21)
        "urgent": x.get("urgent"),
        "near_transit": x.get("near_transit"),
        "in_industrial_estate": (bool(x.get("industrial_estate")) if "industrial_estate" in x else None),
        "online_interview": x.get("online_interview"),
        "days_listed": days_between(first_seen, last_seen),
    }
    return out
