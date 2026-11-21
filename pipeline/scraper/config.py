"""Centralized scraper configuration, selectors, province/category tables, and safety rules.

Enforces ToS/PDPA guardrails:
- Allowed sources: JobThai (primary), JobBKK (secondary Could).
- Forbidden sources: JobTopGun, JobsDB, Indeed (and SEEK).
- Polite scraping: sequential (concurrency=1) with delay >= 5.0 seconds.
"""
from __future__ import annotations

import os
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Source Governance & Polite Scraping Rules (AGENTS.md §1, CONTEXT.md §5)
# ---------------------------------------------------------------------------

FORBIDDEN_SOURCES: frozenset[str] = frozenset({"jobtopgun", "jobsdb", "indeed"})
FORBIDDEN_DOMAINS: tuple[str, ...] = (
    "jobtopgun.com",
    "jobsdb.com",
    "indeed.com",
    "seek.com",
)
ALLOWED_SOURCES: frozenset[str] = frozenset({"jobthai", "jobbkk"})

MIN_DELAY_SEC: float = 5.0
DEFAULT_CONCURRENCY: int = 1
DEFAULT_JITTER_SEC: float = 1.5
DEFAULT_TIMEOUT_SEC: float = 30.0
DEFAULT_USER_AGENT: str = (
    "SkillDemandIntelligence-StudentProject/1.0 "
    "(+academic-noncommercial-research; polite-readonly; contact: student-project@university.ac.th)"
)
USER_AGENT: str = os.getenv("SCRAPER_USER_AGENT", DEFAULT_USER_AGENT)


class ForbiddenSourceError(ValueError):
    """Raised when a forbidden or unsupported job source/domain is requested."""


def get_configured_delay(override_sec: float | None = None) -> float:
    """Return configured delay in seconds, refusing values below MIN_DELAY_SEC."""
    if override_sec is not None:
        delay = float(override_sec)
    else:
        raw = os.getenv("SCRAPER_MIN_DELAY_SEC", str(MIN_DELAY_SEC))
        delay = float(raw)
    return enforce_delay(delay)


def enforce_delay(delay_sec: float) -> float:
    """Validate that the request delay obeys the >= 5.0s polite scraping floor."""
    delay = float(delay_sec)
    if delay < MIN_DELAY_SEC:
        raise ValueError(
            f"Polite scraping requires delay >= {MIN_DELAY_SEC:.1f}s; got {delay:.2f}s"
        )
    return delay


def validate_source(source: str) -> str:
    """Validate source name against FORBIDDEN_SOURCES and ALLOWED_SOURCES."""
    norm = (source or "").strip().lower()
    if norm in FORBIDDEN_SOURCES:
        raise ForbiddenSourceError(
            f"Source '{source}' is strictly forbidden by project ToS policy."
        )
    if norm not in ALLOWED_SOURCES:
        raise ForbiddenSourceError(
            f"Unsupported source '{source}'. Allowed sources: {sorted(ALLOWED_SOURCES)}"
        )
    return norm


def validate_url(url: str) -> str:
    """Reject any URL targeting a forbidden job portal domain."""
    parsed = urlparse(url or "")
    host = (parsed.netloc or "").lower()
    for domain in FORBIDDEN_DOMAINS:
        if domain in host or domain in (url or "").lower():
            raise ForbiddenSourceError(
                f"URL '{url}' targets forbidden domain '{domain}'."
            )
    return url


# ---------------------------------------------------------------------------
# JobThai URLs & Centralized Selectors (ARCHITECTURE.md §4)
# ---------------------------------------------------------------------------

JOBTHAI_BASE_URL: str = "https://www.jobthai.com"
JOBTHAI_PROVINCE_LIST_URL: str = (
    "https://www.jobthai.com/th/jobs?province={province_code}"
)
JOBTHAI_PROVINCE_PAGE_URL: str = (
    "https://www.jobthai.com/th/jobs?province={province_code}&page={page}"
)
JOBTHAI_PROVINCE_CATEGORY_URL: str = (
    "https://www.jobthai.com/th/jobs?province={province_code}&jobtype={jobtype_code}"
)
JOBTHAI_PROVINCE_CATEGORY_PAGE_URL: str = (
    "https://www.jobthai.com/th/jobs?province={province_code}&jobtype={jobtype_code}&page={page}"
)
JOBTHAI_DETAIL_URL: str = "https://www.jobthai.com/th/company/job/{job_id}"

# ---------------------------------------------------------------------------
# JobBKK URLs & Listing Configuration (Secondary Academic-Only Source, T1.9)
# ---------------------------------------------------------------------------

JOBBKK_BASE_URL: str = "https://www.jobbkk.com"
JOBBKK_REGIONAL_BASE_URL: str = "https://store.jobbkk.com"
JOBBKK_DETAIL_URL: str = "https://www.jobbkk.com/jobs/detail/{company_id}/{job_id}"
JOBBKK_LIST_URL: str = (
    "https://www.jobbkk.com/jobs/lists/{page}/หางาน,ทั้งหมด,{province},ทั้งหมด.html"
)
JOBBKK_CATEGORY_LIST_URL: str = (
    "https://www.jobbkk.com/jobs/lists/{page}/หางาน,{category},{province},ทั้งหมด.html"
)
JOBBKK_URGENT_URL: str = "https://www.jobbkk.com/jobs/urgent"
JOBBKK_REGION_URLS: dict[str, str] = {
    "central": "https://store.jobbkk.com/regional/jobregion/central",
    "eastern": "https://store.jobbkk.com/regional/jobregion/eastern",
    "northeastern": "https://store.jobbkk.com/regional/jobregion/northeastern",
    "northern": "https://store.jobbkk.com/regional/jobregion/northern",
    "southern": "https://store.jobbkk.com/regional/jobregion/southern",
    "western": "https://store.jobbkk.com/regional/jobregion/western",
}

SELECTORS: dict[str, object] = {
    "job_link": 'a[href*="/th/company/job/"]',
    "job_id_regex": r"/th/company/job/(\d+)",
    "jobbkk_job_link": 'a[href*="/jobs/detail/"]',
    "jobbkk_detail_path_regex": r"/jobs/detail/(\d+)/(\d+)",
    "total_count_regex": r'"total"\s*:\s*(\d+)',
    "title_regex": r"<title>([^<]*)</title>",
    "next_page_button": (
        'a[rel="next"], button[aria-label*="next" i], '
        'a[aria-label*="next" i], [data-testid="pagination-next"]'
    ),
    "job_card": '[data-testid*="job"], article, a[href*="/th/company/job/"]',
    "load_more_trigger": "window.scrollTo(0, document.body.scrollHeight)",
    "next_s_marker": "(self.__next_s=self.__next_s||[]).push([0,",
    "ld_json_script": r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    "captcha_keywords": (
        "captcha",
        "cf-challenge",
        "g-recaptcha",
        "hcaptcha",
        "turnstile",
        "verify you are human",
    ),
    "block_status_map": {
        403: "stopped_403",
        429: "stopped_429",
    },
}

# ---------------------------------------------------------------------------
# JobThai 77 Provinces + Multi-Province (98) + Abroad (99)
# Verified against spike/raw/jobthai/by_province/province_totals.csv
# ---------------------------------------------------------------------------

JOBTHAI_PROVINCES: dict[str, str] = {
    "01": "กรุงเทพมหานคร",
    "02": "กระบี่",
    "03": "กาญจนบุรี",
    "04": "กาฬสินธุ์",
    "05": "กำแพงเพชร",
    "06": "ขอนแก่น",
    "07": "จันทบุรี",
    "08": "ฉะเชิงเทรา",
    "09": "ชลบุรี",
    "10": "ชัยนาท",
    "11": "ชัยภูมิ",
    "12": "ชุมพร",
    "13": "เชียงราย",
    "14": "เชียงใหม่",
    "15": "ตรัง",
    "16": "ตราด",
    "17": "ตาก",
    "18": "นครนายก",
    "19": "นครปฐม",
    "20": "นครพนม",
    "21": "นครราชสีมา",
    "22": "นครศรีธรรมราช",
    "23": "นครสวรรค์",
    "24": "นนทบุรี",
    "25": "นราธิวาส",
    "26": "น่าน",
    "27": "บุรีรัมย์",
    "28": "ปทุมธานี",
    "29": "ประจวบคีรีขันธ์",
    "30": "ปราจีนบุรี",
    "31": "ปัตตานี",
    "32": "พระนครศรีอยุธยา",
    "33": "พะเยา",
    "34": "พังงา",
    "35": "พัทลุง",
    "36": "พิจิตร",
    "37": "พิษณุโลก",
    "38": "เพชรบุรี",
    "39": "เพชรบูรณ์",
    "40": "แพร่",
    "41": "ภูเก็ต",
    "42": "มหาสารคาม",
    "43": "มุกดาหาร",
    "44": "แม่ฮ่องสอน",
    "45": "ยโสธร",
    "46": "ยะลา",
    "47": "ร้อยเอ็ด",
    "48": "ระนอง",
    "49": "ระยอง",
    "50": "ราชบุรี",
    "51": "ลพบุรี",
    "52": "ลำปาง",
    "53": "ลำพูน",
    "54": "เลย",
    "55": "ศรีสะเกษ",
    "56": "สกลนคร",
    "57": "สงขลา",
    "58": "สตูล",
    "59": "สมุทรปราการ",
    "60": "สมุทรสงคราม",
    "61": "สมุทรสาคร",
    "62": "สระแก้ว",
    "63": "สระบุรี",
    "64": "สิงห์บุรี",
    "65": "สุโขทัย",
    "66": "สุพรรณบุรี",
    "67": "สุราษฎร์ธานี",
    "68": "สุรินทร์",
    "69": "หนองคาย",
    "70": "หนองบัวลำภู",
    "71": "อ่างทอง",
    "72": "อำนาจเจริญ",
    "73": "อุดรธานี",
    "74": "อุตรดิตถ์",
    "75": "อุทัยธานี",
    "76": "อุบลราชธานี",
    "77": "บึงกาฬ",
    "98": "หลายจังหวัด",
    "99": "ต่างประเทศ",
}

PROVINCE_NAME_TO_CODE: dict[str, str] = {v: k for k, v in JOBTHAI_PROVINCES.items()}

# Provinces whose total exceeds single-listing scroll/page cap and must be
# discovered per province x jobtype category (T1.6: Bangkok & Chonburi).
LARGE_PROVINCE_CODES: frozenset[str] = frozenset({"01", "09"})
LARGE_PROVINCE_THRESHOLD: int = 3000

# ---------------------------------------------------------------------------
# JobThai JobType Category Filters (extracted from JobThai __NEXT_DATA__)
# ---------------------------------------------------------------------------

JOBTHAI_JOBTYPES: dict[int, str] = {
    1: "งานกฎหมาย",
    2: "งานการตลาด",
    3: "งานเกษตร-ปศุสัตว์-ประมง",
    4: "งานขาย",
    5: "งานเขียนแบบ",
    6: "งานขนส่งและคลังสินค้า",
    7: "งานคอมพิวเตอร์-ไอที",
    8: "งานบันเทิง-นักแสดง-นางแบบ-นักร้อง",
    9: "งานจัดซื้อ-งานธุรการ-ประสานงาน",
    10: "งานสิ่งแวดล้อม-ความปลอดภัย",
    11: "งานช่างเทคนิค",
    12: "งานเขียน-พิสูจน์อักษร-บรรณาธิการ",
    13: "งานนำเข้า-ส่งออก",
    14: "งานบริการลูกค้า",
    15: "งานบัญชี",
    16: "งานทรัพยากรบุคคล",
    17: "งานผลิต-ควบคุมคุณภาพ-โรงงาน",
    18: "งานผู้บริหาร",
    19: "งานรักษาความปลอดภัย",
    20: "งานบริการด้านการแพทย์",
    21: "งานภูมิศาสตร์-แผนที่-gis-ผังเมือง",
    22: "งานแม่บ้าน-พี่เลี้ยง-คนสวน",
    23: "งานก่อสร้างสถาปัตยกรรม",
    25: "งานล่าม-แปล",
    26: "งานเลขานุการ",
    27: "งานวิทยาศาสตร์",
    28: "งานวิศวกรรม",
    29: "งานนักวิจัย-วิเคราะห์-เศรษฐศาสตร์-หุ้น-ธนาคาร",
    30: "งานออกแบบ-กราฟิก-ช่างภาพ",
    31: "งานขับรถ",
    32: "งานสื่อสารมวลชน-งานโฆษณา",
    33: "งานด้านสุขภาพ-ฟิตเนส-สปา",
    34: "งานเสื้อผ้า-สิ่งทอ",
    36: "งานอัญมณีและเครื่องประดับ",
    37: "งานวิชาการ",
    38: "งานบริการอาหารและเครื่องดื่ม",
    39: "งานอื่นๆ",
    40: "งานพาร์ทไทม์-พนักงานชั่วคราว",
    41: "งานfreelance",
    42: "งานการเงิน-ธนาคาร",
    43: "งานประกันภัย",
    44: "งาน-e-commerce",
    45: "งาน-sustainability",
    50: "งานบริการท่องเที่ยว-การโรงแรม",
}
