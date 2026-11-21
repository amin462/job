"""Data cleaning and normalization for Thai/English job postings (T2.1, T2.2).

Rules follow ARCHITECTURE.md §5.1 and migration 002_dw_dimensions_and_seed.sql:
- Salary: monthly THB in [5000, 500000]; DAY * 26, HOUR * 8 * 26; open-max flagged.
- Location: 77 provinces + 'หลายจังหวัด' + 'ต่างประเทศ', region + is_south14.
- Company: deterministic normalization for GroupKFold grouping (never ML feature).
- Education & Experience: regex/structured mapping to canonical DW bands.
- Gender & Age: boolean flags ONLY for DQ/fairness reporting (D6), never ML features.
"""
from __future__ import annotations

import html as htmllib
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

SALARY_MIN_THB = 5_000.0
SALARY_MAX_THB = 500_000.0
DAYS_PER_MONTH = 26.0
HOURS_PER_DAY = 8.0

SOUTH14_PROVINCES: frozenset[str] = frozenset(
    {
        "กระบี่",
        "ชุมพร",
        "ตรัง",
        "นครศรีธรรมราช",
        "นราธิวาส",
        "ปัตตานี",
        "พังงา",
        "พัทลุง",
        "ภูเก็ต",
        "ยะลา",
        "ระนอง",
        "สงขลา",
        "สตูล",
        "สุราษฎร์ธานี",
    }
)

# Authoritative lookup matching supabase/migrations/002_dw_dimensions_and_seed.sql
PROVINCE_META: dict[str, tuple[str, str, str, bool]] = {
    "กรุงเทพมหานคร": ("01", "Bangkok", "กลาง", False),
    "กระบี่": ("02", "Krabi", "ใต้", True),
    "กาญจนบุรี": ("03", "Kanchanaburi", "ตะวันตก", False),
    "กาฬสินธุ์": ("04", "Kalasin", "อีสาน", False),
    "กำแพงเพชร": ("05", "Kamphaeng Phet", "กลาง", False),
    "ขอนแก่น": ("06", "Khon Kaen", "อีสาน", False),
    "จันทบุรี": ("07", "Chanthaburi", "ตะวันออก", False),
    "ฉะเชิงเทรา": ("08", "Chachoengsao", "ตะวันออก", False),
    "ชลบุรี": ("09", "Chon Buri", "ตะวันออก", False),
    "ชัยนาท": ("10", "Chai Nat", "กลาง", False),
    "ชัยภูมิ": ("11", "Chaiyaphum", "อีสาน", False),
    "ชุมพร": ("12", "Chumphon", "ใต้", True),
    "เชียงราย": ("13", "Chiang Rai", "เหนือ", False),
    "เชียงใหม่": ("14", "Chiang Mai", "เหนือ", False),
    "ตรัง": ("15", "Trang", "ใต้", True),
    "ตราด": ("16", "Trat", "ตะวันออก", False),
    "ตาก": ("17", "Tak", "ตะวันตก", False),
    "นครนายก": ("18", "Nakhon Nayok", "กลาง", False),
    "นครปฐม": ("19", "Nakhon Pathom", "กลาง", False),
    "นครพนม": ("20", "Nakhon Phanom", "อีสาน", False),
    "นครราชสีมา": ("21", "Nakhon Ratchasima", "อีสาน", False),
    "นครศรีธรรมราช": ("22", "Nakhon Si Thammarat", "ใต้", True),
    "นครสวรรค์": ("23", "Nakhon Sawan", "กลาง", False),
    "นนทบุรี": ("24", "Nonthaburi", "กลาง", False),
    "นราธิวาส": ("25", "Narathiwat", "ใต้", True),
    "น่าน": ("26", "Nan", "เหนือ", False),
    "บุรีรัมย์": ("27", "Buri Ram", "อีสาน", False),
    "ปทุมธานี": ("28", "Pathum Thani", "กลาง", False),
    "ประจวบคีรีขันธ์": ("29", "Prachuap Khiri Khan", "ตะวันตก", False),
    "ปราจีนบุรี": ("30", "Prachin Buri", "ตะวันออก", False),
    "ปัตตานี": ("31", "Pattani", "ใต้", True),
    "พระนครศรีอยุธยา": ("32", "Phra Nakhon Si Ayutthaya", "กลาง", False),
    "พะเยา": ("33", "Phayao", "เหนือ", False),
    "พังงา": ("34", "Phangnga", "ใต้", True),
    "พัทลุง": ("35", "Phatthalung", "ใต้", True),
    "พิจิตร": ("36", "Phichit", "กลาง", False),
    "พิษณุโลก": ("37", "Phitsanulok", "กลาง", False),
    "เพชรบุรี": ("38", "Phetchaburi", "ตะวันตก", False),
    "เพชรบูรณ์": ("39", "Phetchabun", "กลาง", False),
    "แพร่": ("40", "Phrae", "เหนือ", False),
    "ภูเก็ต": ("41", "Phuket", "ใต้", True),
    "มหาสารคาม": ("42", "Maha Sarakham", "อีสาน", False),
    "มุกดาหาร": ("43", "Mukdahan", "อีสาน", False),
    "แม่ฮ่องสอน": ("44", "Mae Hong Son", "เหนือ", False),
    "ยโสธร": ("45", "Yasothon", "อีสาน", False),
    "ยะลา": ("46", "Yala", "ใต้", True),
    "ร้อยเอ็ด": ("47", "Roi Et", "อีสาน", False),
    "ระนอง": ("48", "Ranong", "ใต้", True),
    "ระยอง": ("49", "Rayong", "ตะวันออก", False),
    "ราชบุรี": ("50", "Ratchaburi", "ตะวันตก", False),
    "ลพบุรี": ("51", "Lop Buri", "กลาง", False),
    "ลำปาง": ("52", "Lampang", "เหนือ", False),
    "ลำพูน": ("53", "Lamphun", "เหนือ", False),
    "เลย": ("54", "Loei", "อีสาน", False),
    "ศรีสะเกษ": ("55", "Si Sa Ket", "อีสาน", False),
    "สกลนคร": ("56", "Sakon Nakhon", "อีสาน", False),
    "สงขลา": ("57", "Songkhla", "ใต้", True),
    "สตูล": ("58", "Satun", "ใต้", True),
    "สมุทรปราการ": ("59", "Samut Prakan", "กลาง", False),
    "สมุทรสงคราม": ("60", "Samut Songkhram", "กลาง", False),
    "สมุทรสาคร": ("61", "Samut Sakhon", "กลาง", False),
    "สระแก้ว": ("62", "Sa Kaeo", "ตะวันออก", False),
    "สระบุรี": ("63", "Saraburi", "กลาง", False),
    "สิงห์บุรี": ("64", "Sing Buri", "กลาง", False),
    "สุโขทัย": ("65", "Sukhothai", "กลาง", False),
    "สุพรรณบุรี": ("66", "Suphan Buri", "กลาง", False),
    "สุราษฎร์ธานี": ("67", "Surat Thani", "ใต้", True),
    "สุรินทร์": ("68", "Surin", "อีสาน", False),
    "หนองคาย": ("69", "Nong Khai", "อีสาน", False),
    "หนองบัวลำภู": ("70", "Nong Bua Lam Phu", "อีสาน", False),
    "อ่างทอง": ("71", "Ang Thong", "กลาง", False),
    "อำนาจเจริญ": ("72", "Amnat Charoen", "อีสาน", False),
    "อุดรธานี": ("73", "Udon Thani", "อีสาน", False),
    "อุตรดิตถ์": ("74", "Uttaradit", "เหนือ", False),
    "อุทัยธานี": ("75", "Uthai Thani", "กลาง", False),
    "อุบลราชธานี": ("76", "Ubon Ratchathani", "อีสาน", False),
    "บึงกาฬ": ("77", "Bueng Kan", "อีสาน", False),
    "หลายจังหวัด": ("98", "Multiple Provinces", "ไม่ระบุ", False),
    "ต่างประเทศ": ("99", "Overseas", "ไม่ระบุ", False),
}

CANONICAL_PROVINCES: frozenset[str] = frozenset(PROVINCE_META.keys())

_PROVINCE_SYNONYMS: dict[str, str] = {
    "กทม": "กรุงเทพมหานคร",
    "กทม.": "กรุงเทพมหานคร",
    "กรุงเทพ": "กรุงเทพมหานคร",
    "กรุงเทพฯ": "กรุงเทพมหานคร",
    "bangkok": "กรุงเทพมหานคร",
    "bkk": "กรุงเทพมหานคร",
    "อยุธยา": "พระนครศรีอยุธยา",
    "โคราช": "นครราชสีมา",
    "พังงา": "พังงา",
    "ศรีษะเกษ": "ศรีสะเกษ",
    "หลาย": "หลายจังหวัด",
    "หลายพื้นที่": "หลายจังหวัด",
    "ทุกจังหวัด": "หลายจังหวัด",
    "ทั่วประเทศ": "หลายจังหวัด",
    "หลายจังหวัด": "หลายจังหวัด",
    "multiple provinces": "หลายจังหวัด",
    "ต่างประเทศ": "ต่างประเทศ",
    "overseas": "ต่างประเทศ",
    "abroad": "ต่างประเทศ",
}
for _p_th, (_c, _p_en, _reg, _s14) in PROVINCE_META.items():
    _PROVINCE_SYNONYMS[_p_en.lower()] = _p_th
    _PROVINCE_SYNONYMS[_p_en.lower().replace(" ", "")] = _p_th

_ZERO_WIDTH_RX = re.compile(r"[\u200b-\u200f\ufeff\u202a-\u202e]")
_HTML_TAG_RX = re.compile(r"<[^>]+>")
_PHONE_CORE = r"(?:02(?:[-.\s]?\d){7}|0[3-9]\d(?:[-.\s]?\d){6,7}|\+66(?:[-.\s]?\d){8,9})"
_PHONE_SCRUB_RX = re.compile(rf"(?<!\d){_PHONE_CORE}(?!\d)")
_EMAIL_SCRUB_RX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_LINE_SCRUB_RX = re.compile(
    r"(?i)(?:"
    r"(?:(?<![A-Za-z])id\s*line|(?<![A-Za-z])line\s*id|ไอดี\s*ไลน์|แอด\s*ไลน์|ทัก\s*ไลน์)\s*[:：=@\-]?\s*@?[A-Za-z0-9._-]{2,}"
    r"|(?<![A-Za-z])line\s*(?:official|oa)?\s*[:：=@]\s*@?[A-Za-z0-9._-]{2,}"
    r"|(?<![A-Za-z])line\s+@[A-Za-z0-9._-]{2,}"
    r")"
)
_HR_CONTACT_PHRASE_RX = re.compile(
    rf"(?i)(?:สนใจ)?(?:ติดต่อ(?:สอบถาม)?|สอบถาม(?:เพิ่มเติม)?|โทร\.?|tel\.?|mobile|มือถือ|สายด่วน)\s*[:：]?\s*(?:(?:คุณ|k\.?|mr\.?|ms\.?|mrs\.?)\s*[^\s,()/]+(?:\s*(?:โทร\.?|tel\.?)?\s*[:：]?\s*{_PHONE_CORE})?|{_PHONE_CORE}(?:\s*(?:คุณ|k\.?|mr\.?|ms\.?|mrs\.?)\s*[^\s,()/]+)?)"
)

# Salary parsing regexes
_HOUR_RX = re.compile(r"(?i)(?:ชั่วโมงละ|ชม\.?\s*ละ|/\s*ชั่วโมง|/\s*ชม\.?|ต่อชั่วโมง|รายชั่วโมง|/\s*h(?:ou)?r|per\s+hour|hourly)")
_DAY_RX = re.compile(r"(?i)(?:วันละ|/\s*วัน|ต่อวัน|รายวัน|/\s*day|per\s+day|daily)")
_YEAR_RX = re.compile(r"(?i)(?:ปีละ|/\s*ปี|ต่อปี|รายปี|/\s*yr|/\s*year|per\s+year|annual)")
_NEGOTIABLE_RX = re.compile(
    r"(?i)(?:ตามตกลง|ตามโครงสร้าง|ตามประสบการณ์|ตามความสามารถ|ตามวุฒิ|ไม่ระบุ|negotiable|nego\b|competitive|n/a)"
)
_OPEN_MIN_RX = re.compile(
    r"(?i)(?:ขึ้นไป|เป็นต้นไป|อย่างน้อย|ไม่ต่ำกว่า|ขั้นต่ำ|ตั้งแต่|เริ่มต้น|เริ่มต้นที่|มากกว่า|(?:\d|k|หมื่น)\s*\+\+?|>=\s*|and\s+up|\bfrom\s+\d|\bupward)"
)
_OPEN_MAX_RX = re.compile(r"(?i)(?:ไม่เกิน|สูงสุด|up\s*to|<=\s*)")
_SAL_TOKEN_RX = re.compile(
    r"(?i)(\d+(?:,\d{3})*(?:\.\d+)?)\s*(k|หมื่น)?"
)
_RANGE_CONNECTOR_RX = re.compile(
    r"(?i)(\d+(?:,\d{3})*(?:\.\d+)?)\s*(k|หมื่น)?\s*(?:-|–|—|~|ถึง|to)\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*(k|หมื่น)?"
)

# Company wrappers to normalize deterministically
_COMPANY_PREFIX_RX = re.compile(r"^(?:บริษัท|ห้างหุ้นส่วนจำกัด|ห้างหุ้นส่วน|หจก\.?|บมจ\.?|บจก\.?|กลุ่มบริษัท)\s*")
_COMPANY_SUFFIX_RX = re.compile(
    r"(?i)(?:\s*(?:จำกัด\s*\(มหาชน\)|\(มหาชน\)|จำกัด|มหาชน|public\s+company\s+limited|company\s+limited|co\.,?\s*ltd\.?|co\.\s*ltd\.?|ltd\.?|inc\.?|pcl\.?|corp\.?))+"
)
_BRANCH_SUFFIX_RX = re.compile(r"\((?:สาขา[^)]*|head\s*office|สำนักงานใหญ่)\)", re.I)

# Education regexes (ordered from lowest level to highest so minimum accepted level wins)
_EDU_NONE_RX = re.compile(r"(?i)(?:ไม่จำกัดวุฒิ|ไม่จำกัดการศึกษา|ไม่ระบุวุฒิ|ไม่จำกัดระดับการศึกษา)")
_EDU_LEVELS: list[tuple[str, int, re.Pattern[str]]] = [
    (
        "ม.3/ม.6",
        1,
        re.compile(
            r"(?i)(?:ม\.\s*[36]|มัธยมศึกษา(?:ปีที่\s*[36]|ตอนต้น|ตอนปลาย)?|ม\.\s*ต้น|ม\.\s*ปลาย|มัธยม(?:ต้น|ปลาย)|กศน\.?|high\s*school|secondary(?:\s+school)?)"
        ),
    ),
    (
        "ปวช./ปวส.",
        2,
        re.compile(
            r"(?i)(?:ปวช\.?|ปวส\.?|อนุปริญญา|ประกาศนียบัตรวิชาชีพ(?:ชั้นสูง)?|high\s*vocational|vocational|diploma|associate\s*degree)"
        ),
    ),
    (
        "ปริญญาตรี",
        3,
        re.compile(
            r"(?i)(?:ปริญญาตรี|ป\.\s*ตรี|ตรีขึ้นไป|bachelor(?:'s)?(?:\s*degree)?|\bb\.?\s*(?:s|a|eng|acc|ba|sc)\b|undergraduate)"
        ),
    ),
    (
        "ปริญญาโท+",
        4,
        re.compile(
            r"(?i)(?:ปริญญาโท|ป\.\s*โท|ปริญญาเอก|ป\.\s*เอก|master(?:'s)?(?:\s*degree)?|\bmba\b|\bm\.?\s*(?:s|sc|a|eng)\b|ph\.?\s*d|doctorate|postgraduate)"
        ),
    ),
]
_EDU_STRUCT_MAP: dict[str, str] = {
    "bachelor": "ปริญญาตรี",
    "bachelor's degree": "ปริญญาตรี",
    "master": "ปริญญาโท+",
    "master's degree": "ปริญญาโท+",
    "doctorate": "ปริญญาโท+",
    "high_vocational": "ปวช./ปวส.",
    "vocational": "ปวช./ปวส.",
    "associate": "ปวช./ปวส.",
    "upper_secondary": "ม.3/ม.6",
    "lower_secondary": "ม.3/ม.6",
    "high school": "ม.3/ม.6",
}

# Experience regexes
_FRESH_RX = re.compile(
    r"(?i)(?:ไม่มีประสบการณ์|ไม่จำเป็นต้องมีประสบการณ์|ไม่ต้องมีประสบการณ์|ไม่เน้นประสบการณ์|ไม่จำกัดประสบการณ์|ยินดี(?:รับ)?(?:นักศึกษา)?จบใหม่|นักศึกษาจบใหม่|จบใหม่|fresh\s*grad(?:uate)?|no\s+experience(?:\s+required)?|entry[\s-]level)"
)
_EXP_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"(?i)(?:ประสบการณ์(?:การทำงาน|ทำงาน|ด้าน[^0-9\n]{0,25})?|exp(?:erience)?(?:\s+of)?)\s*(?:อย่างน้อย|ไม่น้อยกว่า|ขั้นต่ำ|at\s+least|min(?:imum)?|:|-)?\s*(\d{1,2})\s*(?:(?:-|–|—|ถึง|~|to)\s*(\d{1,2}))?\s*(\+|ขึ้นไป)?\s*(?:ปี|years?|yrs?)"
    ),
    re.compile(
        r"(?i)(\d{1,2})\s*(?:(?:-|–|—|ถึง|~|to)\s*(\d{1,2}))?\s*(\+|ขึ้นไป)?\s*(?:ปี|years?|yrs?)\s*(?:of\s+)?(?:working\s+)?(?:experience|exp\b|ขึ้นไป\s*(?:ในสายงาน|ด้าน))"
    ),
    re.compile(
        r"(?i)(?:อย่างน้อย|ไม่น้อยกว่า|ขั้นต่ำ)\s*(\d{1,2})\s*(?:(?:-|–|—|ถึง|~|to)\s*(\d{1,2}))?\s*(\+|ขึ้นไป)?\s*ปี"
    ),
]

# Fairness/DQ monitoring flags ONLY (D6: NEVER pass into ML features)
_GENDER_RX = re.compile(
    r"(?i)(?:เพศ\s*(?:ชาย|หญิง)|เพศชาย|เพศหญิง|ไม่จำกัดเพศ|\bmale\b|\bfemale\b|ชาย\s*/\s*หญิง|หญิง\s*/\s*ชาย)"
)
_AGE_RX = re.compile(
    r"(?i)(?:อายุ\s*(?:ไม่เกิน|ระหว่าง|ตั้งแต่)?\s*\d{2}|\bage\s*\d{2}\s*[-–~]\s*\d{2})"
)


@dataclass(frozen=True)
class SalaryResult:
    salary_min: float | None
    salary_max: float | None
    salary_mid: float | None
    salary_open_max: bool
    salary_unit_orig: str | None
    salary_out_of_range: bool


def normalize_thai_text(text: str | None) -> str:
    """Fix Thai Sara Am decomposition (Nikhahit + Sara Aa -> Sara Am) and NFC-normalize."""
    if not text:
        return ""
    text = text.replace("\u0e4d\u0e32", "\u0e33")
    text = unicodedata.normalize("NFC", text)
    text = _ZERO_WIDTH_RX.sub("", text).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def scrub_hr_pii(text: str | None) -> str:
    """Remove HR phone numbers, emails, LINE IDs, and inline contact phrases (PDPA)."""
    norm = normalize_thai_text(text)
    if not norm:
        return ""
    norm = _HR_CONTACT_PHRASE_RX.sub(" ", norm)
    norm = _EMAIL_SCRUB_RX.sub(" ", norm)
    norm = _PHONE_SCRUB_RX.sub(" ", norm)
    norm = _LINE_SCRUB_RX.sub(" ", norm)
    return re.sub(r"\s+", " ", norm).strip()


def contains_hr_pii(text: str | None) -> bool:
    """Detect whether text contains HR phone, email, LINE ID, or inline contact phrase."""
    norm = normalize_thai_text(text)
    if not norm:
        return False
    return bool(
        _HR_CONTACT_PHRASE_RX.search(norm)
        or _EMAIL_SCRUB_RX.search(norm)
        or _PHONE_SCRUB_RX.search(norm)
        or _LINE_SCRUB_RX.search(norm)
    )


def clean_html_text(text: str | None, scrub_pii: bool = True) -> str:
    """Strip HTML tags, decode entities, fix Thai encoding, and optionally scrub HR PII."""
    if not isinstance(text, str) or not text:
        return ""
    stripped = htmllib.unescape(_HTML_TAG_RX.sub(" ", text))
    norm = normalize_thai_text(stripped)
    if scrub_pii:
        return scrub_hr_pii(norm)
    return norm


def _apply_unit_multiplier(unit: str) -> float:
    if unit == "DAY":
        return DAYS_PER_MONTH
    if unit == "HOUR":
        return HOURS_PER_DAY * DAYS_PER_MONTH
    if unit == "YEAR":
        return 1.0 / 12.0
    return 1.0


def _detect_unit(text: str, structured_unit: str | None) -> str | None:
    if structured_unit:
        u = str(structured_unit).strip().upper()
        if u in {"MONTH", "DAY", "HOUR", "YEAR"}:
            return u
    if _HOUR_RX.search(text):
        return "HOUR"
    if _DAY_RX.search(text):
        return "DAY"
    if _YEAR_RX.search(text):
        return "YEAR"
    return "MONTH"


def _scale_token(num_str: str, suffix: str | None) -> float:
    val = float(num_str.replace(",", ""))
    if suffix:
        s = suffix.lower()
        if s == "k":
            val *= 1_000.0
        elif s == "หมื่น":
            val *= 10_000.0
    return val


def _validate_salary_bounds(
    s_min: float | None,
    s_max: float | None,
    s_mid: float | None,
    open_max: bool,
    unit_orig: str | None,
) -> SalaryResult:
    if s_mid is None:
        return SalaryResult(None, None, None, False, unit_orig, False)
    if s_min is not None and s_max is not None and s_min > s_max:
        return SalaryResult(None, None, None, False, unit_orig, True)
    bounds = [v for v in (s_min, s_max, s_mid) if v is not None]
    if any(v < SALARY_MIN_THB or v > SALARY_MAX_THB for v in bounds):
        return SalaryResult(None, None, None, False, unit_orig, True)
    return SalaryResult(
        salary_min=round(s_min, 2) if s_min is not None else None,
        salary_max=round(s_max, 2) if s_max is not None else None,
        salary_mid=round(s_mid, 2),
        salary_open_max=open_max,
        salary_unit_orig=unit_orig,
        salary_out_of_range=False,
    )


def normalize_salary(
    salary_text: str | None = None,
    salary_min: float | int | None = None,
    salary_max: float | int | None = None,
    salary_value: float | int | None = None,
    salary_unit: str | None = None,
) -> SalaryResult:
    """Normalize salary to monthly THB per ARCHITECTURE.md §5.1."""
    raw_text = normalize_thai_text(unicodedata.normalize("NFKC", salary_text or ""))

    # 1. Handle structured JSON-LD fields first if present
    has_struct = any(v is not None and str(v).strip() != "" for v in (salary_min, salary_max, salary_value))
    if has_struct:
        unit_orig = _detect_unit(raw_text, salary_unit) or "MONTH"
        mult = _apply_unit_multiplier(unit_orig)

        def _to_float(v: Any) -> float | None:
            if v is None or str(v).strip() == "":
                return None
            return float(v)

        s_min = _to_float(salary_min)
        s_max = _to_float(salary_max)
        s_val = _to_float(salary_value)

        # Some sites encode undisclosed salary as 0
        if (s_min == 0 or s_min is None) and (s_max == 0 or s_max is None) and (s_val == 0 or s_val is None):
            return SalaryResult(None, None, None, False, None, False)

        if s_val is not None and s_min is None and s_max is None:
            scaled = s_val * mult
            if _OPEN_MIN_RX.search(raw_text):
                return _validate_salary_bounds(scaled, None, scaled, True, unit_orig)
            return _validate_salary_bounds(scaled, scaled, scaled, False, unit_orig)

        if s_min is not None and s_max is not None:
            if s_min > s_max:
                return SalaryResult(None, None, None, False, unit_orig, True)
            lo, hi = s_min * mult, s_max * mult
            return _validate_salary_bounds(lo, hi, (lo + hi) / 2.0, False, unit_orig)

        if s_min is not None and s_max is None:
            lo = s_min * mult
            return _validate_salary_bounds(lo, None, lo, True, unit_orig)

        if s_max is not None and s_min is None:
            hi = s_max * mult
            return _validate_salary_bounds(None, hi, hi, False, unit_orig)

    # 2. Free-text parsing
    if not raw_text:
        return SalaryResult(None, None, None, False, None, False)

    # Range expression e.g. "15,000 - 20,000", "15k-25k", "15-25k", "1.5 หมื่น - 2 หมื่น"
    m_range = _RANGE_CONNECTOR_RX.search(raw_text)
    if m_range:
        unit_orig = _detect_unit(raw_text, salary_unit) or "MONTH"
        mult = _apply_unit_multiplier(unit_orig)
        n1, suf1, n2, suf2 = m_range.groups()
        # Handle "15-25k" where first number inherits suffix 'k' / 'หมื่น'
        eff_suf1 = suf1 or (suf2 if float(n1.replace(",", "")) < 1000 and suf2 else None)
        v1 = _scale_token(n1, eff_suf1) * mult
        v2 = _scale_token(n2, suf2) * mult
        if v1 > v2:
            return SalaryResult(None, None, None, False, unit_orig, True)
        return _validate_salary_bounds(v1, v2, (v1 + v2) / 2.0, False, unit_orig)

    # Pure negotiable text with no numeric tokens
    tokens = list(_SAL_TOKEN_RX.finditer(raw_text))
    if not tokens:
        return SalaryResult(None, None, None, False, None, False)

    # Ignore spurious small tokens if text is pure negotiable without numbers (already handled above)
    unit_orig = _detect_unit(raw_text, salary_unit) or "MONTH"
    mult = _apply_unit_multiplier(unit_orig)
    first_tok = tokens[0]
    val = _scale_token(first_tok.group(1), first_tok.group(2)) * mult

    if _OPEN_MIN_RX.search(raw_text) or (_NEGOTIABLE_RX.search(raw_text) and val > 0):
        return _validate_salary_bounds(val, None, val, True, unit_orig)

    if _OPEN_MAX_RX.search(raw_text):
        return _validate_salary_bounds(None, val, val, False, unit_orig)

    return _validate_salary_bounds(val, val, val, False, unit_orig)


def normalize_province(province: str | None) -> dict[str, Any]:
    """Normalize raw Thai/EN province into canonical dim_location fields."""
    cleaned = normalize_thai_text(province)
    if not cleaned:
        return {
            "province_code": "00",
            "province_th": "ไม่ระบุ",
            "province_en": "Unspecified",
            "region": "ไม่ระบุ",
            "is_south14": False,
        }

    # Strip prefixes like จังหวัด / จ.
    cleaned = re.sub(r"^(?:จังหวัด|จ\.)\s*", "", cleaned).strip()
    lowered = cleaned.lower()

    if cleaned in PROVINCE_META:
        canonical = cleaned
    elif lowered in _PROVINCE_SYNONYMS:
        canonical = _PROVINCE_SYNONYMS[lowered]
    elif cleaned in _PROVINCE_SYNONYMS:
        canonical = _PROVINCE_SYNONYMS[cleaned]
    else:
        # Substring fallback for strings like "อ.หาดใหญ่ จ.สงขลา"
        canonical = next((p for p in PROVINCE_META if p in cleaned), "")

    if canonical and canonical in PROVINCE_META:
        code, p_en, region, is_s14 = PROVINCE_META[canonical]
        return {
            "province_code": code,
            "province_th": canonical,
            "province_en": p_en,
            "region": region,
            "is_south14": is_s14,
        }

    return {
        "province_code": "00",
        "province_th": "ไม่ระบุ",
        "province_en": "Unspecified",
        "region": "ไม่ระบุ",
        "is_south14": False,
    }


def normalize_district(district: str | None) -> str:
    """Normalize district name; returns '' when empty to match dim_location unique key."""
    cleaned = normalize_thai_text(district)
    if not cleaned:
        return ""
    cleaned = re.sub(r"^(?:อำเภอ|อ\.|เขต)\s*", "", cleaned).strip()
    return cleaned


def normalize_company(company: str | None) -> str:
    """Deterministic company normalization for GroupKFold grouping (never an ML feature)."""
    if not company:
        return "unknown"
    text = unicodedata.normalize("NFKC", company)
    text = normalize_thai_text(text)
    if not text:
        return "unknown"
    norm = _BRANCH_SUFFIX_RX.sub(" ", text)
    norm = _COMPANY_PREFIX_RX.sub("", norm)
    norm = _COMPANY_SUFFIX_RX.sub("", norm)
    norm = re.sub(r"[()\[\],.\-_/]+", " ", norm)
    norm = re.sub(r"\s+", " ", norm).strip().lower()
    return norm or text.lower()


def extract_education(
    text: str | None = None,
    qual_text: str | None = None,
    edu_structured: str | None = None,
) -> str:
    """Map structured or free-text education requirements into canonical DW bands."""
    if edu_structured:
        key = str(edu_structured).strip().lower()
        if key in _EDU_STRUCT_MAP:
            return _EDU_STRUCT_MAP[key]

    sources = [normalize_thai_text(qual_text), normalize_thai_text(text)]
    for src in sources:
        if not src:
            continue
        matched: list[tuple[int, str]] = []
        for label, rank, rx in _EDU_LEVELS:
            if rx.search(src):
                matched.append((rank, label))
        if matched:
            # Minimum accepted education level (e.g., "ม.6 - ป.ตรี" -> ม.3/ม.6, "ป.ตรี/โท" -> ปริญญาตรี)
            matched.sort(key=lambda item: item[0])
            return matched[0][1]
        if _EDU_NONE_RX.search(src):
            return "ไม่ระบุ"
    return "ไม่ระบุ"


def extract_experience(
    text: str | None = None,
    qual_text: str | None = None,
    exp_months_structured: float | int | None = None,
) -> str:
    """Map structured or free-text experience requirements into canonical DW bands."""
    if exp_months_structured is not None and str(exp_months_structured).strip() != "":
        months = float(exp_months_structured)
        if months <= 0:
            return "0 ปี / จบใหม่"
        if months <= 24:
            return "1-2 ปี"
        if months <= 60:
            return "3-5 ปี"
        return "5+ ปี"

    sources = [normalize_thai_text(qual_text), normalize_thai_text(text)]
    for src in sources:
        if not src:
            continue
        # Remove age snippets like "อายุ 20-35 ปี" and contract duration "สัญญาจ้าง 1 ปี" before scanning
        sanitized = re.sub(
            r"(?i)(?:อายุ|สัญญาจ้าง|fixed\s*term(?:\s*contract)?)\s*(?:ไม่เกิน|ระหว่าง|ตั้งแต่)?\s*\d{1,2}\s*(?:(?:-|–|ถึง|~)\s*\d{1,2})?\s*ปี",
            " ",
            src,
        )
        has_fresh = bool(_FRESH_RX.search(sanitized))
        years_hits: list[tuple[int, int | None, bool]] = []
        for rx in _EXP_PATTERNS:
            for m in rx.finditer(sanitized):
                y_min = int(m.group(1))
                y_max = int(m.group(2)) if m.group(2) else None
                has_plus = bool(m.group(3))
                # Sanity guard: working experience > 25 yrs is almost certainly a typo/age
                if 0 <= y_min <= 25:
                    years_hits.append((y_min, y_max, has_plus))

        if has_fresh and not years_hits:
            return "0 ปี / จบใหม่"
        if has_fresh and years_hits:
            # Phrases like "ไม่มีประสบการณ์ หรือ ประสบการณ์ 1-2 ปี" allow 0 yrs
            if any(
                k in sanitized
                for k in ("ไม่มีประสบการณ์", "ไม่จำเป็นต้องมีประสบการณ์", "ไม่ต้องมีประสบการณ์", "จบใหม่", "no experience")
            ):
                return "0 ปี / จบใหม่"

        if years_hits:
            y_min, y_max, has_plus = years_hits[0]
            if y_min == 0 and (y_max is None or y_max <= 1):
                return "0 ปี / จบใหม่"
            if y_min <= 2:
                return "1-2 ปี"
            if y_min <= 4 or (y_min == 5 and y_max == 5 and not has_plus):
                return "3-5 ปี"
            return "5+ ปี"
    return "ไม่ระบุ/ไม่จำเป็น"


def detect_gender_age_mentions(text: str | None) -> tuple[bool, bool]:
    """Detect whether posting text mentions gender or age (for DQ/fairness reporting ONLY)."""
    norm = normalize_thai_text(text)
    if not norm:
        return False, False
    return bool(_GENDER_RX.search(norm)), bool(_AGE_RX.search(norm))
