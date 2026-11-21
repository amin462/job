"""Unit tests for salary, location, company, education, and experience cleaning (T2.1, T2.2)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline.etl.clean import (
    CANONICAL_PROVINCES,
    SOUTH14_PROVINCES,
    contains_hr_pii,
    detect_gender_age_mentions,
    extract_education,
    extract_experience,
    normalize_company,
    normalize_district,
    normalize_province,
    normalize_salary,
    scrub_hr_pii,
)


# >= 30 realistic Thai/EN salary strings (ranges, k-notation, open-min, daily, hourly, negotiable, out-of-range, edge)
SALARY_CASES = [
    # Ranges
    ("15,000-20,000", None, None, None, None, (15000.0, 20000.0, 17500.0, False, "MONTH", False)),
    ("15,000 - 25,000 บาท", None, None, None, None, (15000.0, 25000.0, 20000.0, False, "MONTH", False)),
    ("18,000 – 30,000 บาท/เดือน", None, None, None, None, (18000.0, 30000.0, 24000.0, False, "MONTH", False)),
    ("12000 ถึง 16000 บาท", None, None, None, None, (12000.0, 16000.0, 14000.0, False, "MONTH", False)),
    ("15k-25k", None, None, None, None, (15000.0, 25000.0, 20000.0, False, "MONTH", False)),
    ("15K - 20K", None, None, None, None, (15000.0, 20000.0, 17500.0, False, "MONTH", False)),
    ("15-25k", None, None, None, None, (15000.0, 25000.0, 20000.0, False, "MONTH", False)),
    ("15.5k-20k", None, None, None, None, (15500.0, 20000.0, 17750.0, False, "MONTH", False)),
    ("1.5 หมื่น - 2 หมื่น", None, None, None, None, (15000.0, 20000.0, 17500.0, False, "MONTH", False)),
    ("25,000 ~ 35,000 THB", None, None, None, None, (25000.0, 35000.0, 30000.0, False, "MONTH", False)),
    # Open-min
    ("15,000 ขึ้นไป", None, None, None, None, (15000.0, None, 15000.0, True, "MONTH", False)),
    ("ตั้งแต่ 18,000 บาท", None, None, None, None, (18000.0, None, 18000.0, True, "MONTH", False)),
    ("เริ่มต้น 16,000 บาท/เดือน", None, None, None, None, (16000.0, None, 16000.0, True, "MONTH", False)),
    ("ไม่ต่ำกว่า 20,000 บาท", None, None, None, None, (20000.0, None, 20000.0, True, "MONTH", False)),
    ("18,000+", None, None, None, None, (18000.0, None, 18000.0, True, "MONTH", False)),
    ("18k+ ต่อเดือน", None, None, None, None, (18000.0, None, 18000.0, True, "MONTH", False)),
    ("25,000 ++", None, None, None, None, (25000.0, None, 25000.0, True, "MONTH", False)),
    (">= 22,000", None, None, None, None, (22000.0, None, 22000.0, True, "MONTH", False)),
    ("15,000 - ตามตกลง", None, None, None, None, (15000.0, None, 15000.0, True, "MONTH", False)),
    (None, 18000, None, None, "MONTH", (18000.0, None, 18000.0, True, "MONTH", False)),
    # Fixed
    ("15,000 บาท/เดือน", None, None, None, None, (15000.0, 15000.0, 15000.0, False, "MONTH", False)),
    (None, None, None, 15000, "MONTH", (15000.0, 15000.0, 15000.0, False, "MONTH", False)),
    # Daily (* 26)
    ("450 บาท/วัน", None, None, None, None, (11700.0, 11700.0, 11700.0, False, "DAY", False)),
    ("450-/วัน", None, None, None, None, (11700.0, 11700.0, 11700.0, False, "DAY", False)),
    ("วันละ 500 บาท", None, None, None, None, (13000.0, 13000.0, 13000.0, False, "DAY", False)),
    ("400 - 500 บาท/วัน", None, None, None, None, (10400.0, 13000.0, 11700.0, False, "DAY", False)),
    (None, 400, 600, None, "DAY", (10400.0, 15600.0, 13000.0, False, "DAY", False)),
    # Hourly (* 8 * 26 = * 208)
    ("50 บาท/ชม.", None, None, None, None, (10400.0, 10400.0, 10400.0, False, "HOUR", False)),
    ("ชม.ละ 75 บาท", None, None, None, None, (15600.0, 15600.0, 15600.0, False, "HOUR", False)),
    ("60-80 บาท/ชั่วโมง", None, None, None, None, (12480.0, 16640.0, 14560.0, False, "HOUR", False)),
    (None, 100, None, None, "HOUR", (20800.0, None, 20800.0, True, "HOUR", False)),
    # Negotiable / undisclosed
    ("ตามตกลง", None, None, None, None, (None, None, None, False, None, False)),
    ("ตามโครงสร้างบริษัท", None, None, None, None, (None, None, None, False, None, False)),
    ("ตามประสบการณ์และความสามารถ", None, None, None, None, (None, None, None, False, None, False)),
    ("Negotiable", None, None, None, None, (None, None, None, False, None, False)),
    ("ไม่ระบุ", None, None, None, None, (None, None, None, False, None, False)),
    ("", None, None, None, None, (None, None, None, False, None, False)),
    (None, 0, 0, None, "MONTH", (None, None, None, False, None, False)),
    # Out-of-range / invalid
    ("3,000 บาท/เดือน", None, None, None, None, (None, None, None, False, "MONTH", True)),
    ("15 บาท/ชม.", None, None, None, None, (None, None, None, False, "HOUR", True)),
    ("600,000 บาท/เดือน", None, None, None, None, (None, None, None, False, "MONTH", True)),
    (None, 14000, 25000, None, "DAY", (None, None, None, False, "DAY", True)),
    ("25,000 - 15,000", None, None, None, None, (None, None, None, False, "MONTH", True)),
    # Cap-only
    ("ไม่เกิน 30,000 บาท", None, None, None, None, (None, 30000.0, 30000.0, False, "MONTH", False)),
]


@pytest.mark.parametrize("text,s_min,s_max,s_val,unit,expected", SALARY_CASES)
def test_salary_normalization(text, s_min, s_max, s_val, unit, expected):
    assert len(SALARY_CASES) >= 30
    res = normalize_salary(
        salary_text=text,
        salary_min=s_min,
        salary_max=s_max,
        salary_value=s_val,
        salary_unit=unit,
    )
    assert (
        res.salary_min,
        res.salary_max,
        res.salary_mid,
        res.salary_open_max,
        res.salary_unit_orig,
        res.salary_out_of_range,
    ) == expected


def test_province_and_district_normalization():
    assert len(CANONICAL_PROVINCES) == 79
    assert len(SOUTH14_PROVINCES) == 14

    p1 = normalize_province("จังหวัดสงขลา")
    assert p1["province_th"] == "สงขลา"
    assert p1["region"] == "ใต้"
    assert p1["is_south14"] is True

    p2 = normalize_province("กทม.")
    assert p2["province_th"] == "กรุงเทพมหานคร"
    assert p2["region"] == "กลาง"
    assert p2["is_south14"] is False

    p3 = normalize_province("หลาย")
    assert p3["province_th"] == "หลายจังหวัด"
    assert p3["region"] == "ไม่ระบุ"

    p4 = normalize_province("ต่างประเทศ")
    assert p4["province_th"] == "ต่างประเทศ"

    # Decomposed Thai Sara Am (ล + ํ + า + ป + า + ง)
    p5 = normalize_province("ล\u0e4d\u0e32ปาง")
    assert p5["province_th"] == "ลำปาง"
    assert p5["region"] == "เหนือ"

    assert normalize_district("อ.หาดใหญ่") == "หาดใหญ่"
    assert normalize_district("เขตวัฒนา") == "วัฒนา"
    assert normalize_district(None) == ""


def test_company_normalization_deterministic():
    c1 = normalize_company("บริษัท ไทยเบฟเวอเรจ จำกัด (มหาชน)")
    c2 = normalize_company("ไทยเบฟเวอเรจ จำกัด (มหาชน)")
    assert c1 == c2 == "ไทยเบฟเวอเรจ"

    c3 = normalize_company("MANGKASON INDUSTRY（THAILAND）CO.,LTD.")
    assert c3 == "mangkason industry thailand"

    c4 = normalize_company("บริษัท สุรพลซูพรีมฟู้ดส์ จำกัด (สาขาที่ 00001)")
    assert c4 == "สุรพลซูพรีมฟู้ดส์"

    assert normalize_company(None) == "unknown"


# >= 50 education + experience assertions verifying >= 90% accuracy
EDUCATION_CASES = [
    ("วุฒิการศึกษา ปริญญาตรี สาขาบัญชี", None, None, "ปริญญาตรี"),
    ("จบ ป.ตรี ทุกสาขา", None, None, "ปริญญาตรี"),
    ("Bachelor's degree in Computer Science", None, None, "ปริญญาตรี"),
    ("B.Eng. in Mechanical Engineering", None, None, "ปริญญาตรี"),
    ("วุฒิ ป.ตรีขึ้นไป", None, None, "ปริญญาตรี"),
    ("ปริญญาตรี หรือ ปริญญาโท", None, None, "ปริญญาตรี"),
    ("จบปริญญาโท สาขาวิศวกรรมศาสตร์", None, None, "ปริญญาโท+"),
    ("Master degree in Data Science or MBA", None, None, "ปริญญาโท+"),
    ("ป.โท ขึ้นไป", None, None, "ปริญญาโท+"),
    ("วุฒิ ปวส. สาขาไฟฟ้ากำลัง", None, None, "ปวช./ปวส."),
    ("จบ ปวช. / ปวส. ช่างกลโรงงาน", None, None, "ปวช./ปวส."),
    ("High Vocational Certificate", None, None, "ปวช./ปวส."),
    ("อนุปริญญา หรือ ปวส.", None, None, "ปวช./ปวส."),
    ("วุฒิ ม.6 ขึ้นไป", None, None, "ม.3/ม.6"),
    ("จบ ม.3 ขึ้นไป", None, None, "ม.3/ม.6"),
    ("มัธยมศึกษาตอนปลาย (ม.6)", None, None, "ม.3/ม.6"),
    ("วุฒิ ม.3 / ม.6 / กศน.", None, None, "ม.3/ม.6"),
    ("High school graduate", None, None, "ม.3/ม.6"),
    ("วุฒิ ม.6 - ปริญญาตรี", None, None, "ม.3/ม.6"),
    ("ไม่จำกัดวุฒิการศึกษา", None, None, "ไม่ระบุ"),
    ("ขยัน อดทน ซื่อสัตย์", None, None, "ไม่ระบุ"),
    ("รายละเอียดงานทั่วไป", "วุฒิปวส.ขึ้นไป", None, "ปวช./ปวส."),
    ("ตำแหน่งขาย", "จบ ม.6 ขึ้นไป", None, "ม.3/ม.6"),
    ("นักวิเคราะห์ข้อมูล", None, "bachelor", "ปริญญาตรี"),
    ("ผู้จัดการโครงการ", None, "master", "ปริญญาโท+"),
    ("เจ้าหน้าที่บัญชี", "ปวช./ปวส./ป.ตรี", None, "ปวช./ปวส."),
]

EXPERIENCE_CASES = [
    ("ไม่จำกัดประสบการณ์", None, None, "0 ปี / จบใหม่"),
    ("ไม่มีประสบการณ์ ยินดีรับนักศึกษาจบใหม่", None, None, "0 ปี / จบใหม่"),
    ("ไม่จำเป็นต้องมีประสบการณ์การทำงาน", None, None, "0 ปี / จบใหม่"),
    ("Fresh graduate welcome", None, None, "0 ปี / จบใหม่"),
    ("No experience required", None, None, "0 ปี / จบใหม่"),
    ("ประสบการณ์ 0-1 ปี", None, None, "0 ปี / จบใหม่"),
    ("ประสบการณ์ทำงาน 1 ปี", None, None, "1-2 ปี"),
    ("ประสบการณ์ 1-2 ปี ด้านบัญชี", None, None, "1-2 ปี"),
    ("มีประสบการณ์อย่างน้อย 2 ปี", None, None, "1-2 ปี"),
    ("1-2 years experience in sales", None, None, "1-2 ปี"),
    ("Exp 2 yrs in logistics", None, None, "1-2 ปี"),
    ("ประสบการณ์ด้านการขาย 1-3 ปี", None, None, "1-2 ปี"),
    ("ประสบการณ์ทำงาน 3-5 ปี", None, None, "3-5 ปี"),
    ("มีประสบการณ์อย่างน้อย 3 ปี", None, None, "3-5 ปี"),
    ("3-5 years of experience in QA", None, None, "3-5 ปี"),
    ("Experience 4 years", None, None, "3-5 ปี"),
    ("ประสบการณ์ 5 ปีขึ้นไป", None, None, "5+ ปี"),
    ("ประสบการณ์ทำงาน 5+ years", None, None, "5+ ปี"),
    ("มีประสบการณ์อย่างน้อย 7 ปีในระดับผู้จัดการ", None, None, "5+ ปี"),
    ("ประสบการณ์ 10 ปีด้านวิศวกรรม", None, None, "5+ ปี"),
    ("อายุ 22-35 ปี ขยันทำงาน", None, None, "ไม่ระบุ/ไม่จำเป็น"),
    ("สัญญาจ้าง 1 ปี ประจำหาดใหญ่", None, None, "ไม่ระบุ/ไม่จำเป็น"),
    ("หน้าที่รับผิดชอบ ขายสินค้าหน้าร้าน", None, None, "ไม่ระบุ/ไม่จำเป็น"),
    ("ทำงาน 6 วันต่อสัปดาห์", "ประสบการณ์ 2 ปีขึ้นไป", None, "1-2 ปี"),
    ("เจ้าหน้าที่จัดซื้อ", None, 12, "1-2 ปี"),
    ("ผู้จัดการ", None, 72, "5+ ปี"),
]


def test_education_and_experience_accuracy():
    total = len(EDUCATION_CASES) + len(EXPERIENCE_CASES)
    assert total >= 50

    edu_correct = sum(
        1
        for text, qual, struct, exp in EDUCATION_CASES
        if extract_education(text=text, qual_text=qual, edu_structured=struct) == exp
    )
    exp_correct = sum(
        1
        for text, qual, struct, exp in EXPERIENCE_CASES
        if extract_experience(text=text, qual_text=qual, exp_months_structured=struct) == exp
    )
    accuracy = (edu_correct + exp_correct) / total
    assert accuracy >= 0.90, f"Expected >= 90%, got {accuracy:.1%} ({edu_correct}/{len(EDUCATION_CASES)}, {exp_correct}/{len(EXPERIENCE_CASES)})"
    assert edu_correct == len(EDUCATION_CASES)
    assert exp_correct == len(EXPERIENCE_CASES)


def test_gender_age_detection_for_dq_only():
    g, a = detect_gender_age_mentions("เพศชาย/หญิง อายุ 22-35 ปี")
    assert g is True and a is True

    g2, a2 = detect_gender_age_mentions("รับสมัคร Data Analyst ใช้งาน Python และ SQL")
    assert g2 is False and a2 is False


def test_scrub_hr_pii_removes_inline_contacts_and_provincial_phones():
    t1 = scrub_hr_pii("Sales Executive ประจำพื้นที่ ระนอง ติดต่อ 098-250-6742 คุณกุ๊ก")
    assert t1 == "Sales Executive ประจำพื้นที่ ระนอง"
    assert not contains_hr_pii(t1)

    t2 = scrub_hr_pii("ธุรการ ติดต่อคุณสมชาย โทร. 074-123-456 Line ID: @hrdept hr@acme.co.th")
    assert "074" not in t2 and "สมชาย" not in t2 and "@" not in t2 and "Line" not in t2
    assert not contains_hr_pii(t2)

    t3 = scrub_hr_pii("ออฟฟิศโทร 02-123-4567 หรือ +66 81 234 5678")
    assert not contains_hr_pii(t3)

    # Normal business verbs and English words ending in -line must NOT be stripped/flagged
    t4 = scrub_hr_pii("เจ้าหน้าที่ประสานงานและติดต่อลูกค้า เงินเดือน 15,000 บาท")
    assert "ติดต่อลูกค้า" in t4
    assert not contains_hr_pii(t4)

    t5 = "บริการลูกค้าทางโทรศัพท์ premium airline call center & online marketing"
    assert scrub_hr_pii(t5) == t5
    assert not contains_hr_pii(t5)

