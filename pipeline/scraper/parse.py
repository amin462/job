"""HTML / JSON-LD JobPosting parser with strict PDPA HR-contact stripping (T1.2).

Refactored from spike/scripts/parse_jobposting.py:
- Extracts schema.org JobPosting from Next.js `self.__next_s` payloads and
  `<script type="application/ld+json">` tags.
- Drops all HR contact keys (telephone, email, contactPoint, applicationContact,
  faxNumber, contact, etc.) recursively before any data is returned or saved.
- Scrubs phone numbers, email addresses, and LINE IDs from text fields and payload.
- Outputs records aligned with `staging.job_posting_raw`.
"""
from __future__ import annotations

import hashlib
import html as htmllib
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterator

from pipeline.scraper.config import (
    JOBBKK_DETAIL_URL,
    JOBTHAI_DETAIL_URL,
    SELECTORS,
    validate_source,
)

# Case-insensitive HR contact / PII keys stripped recursively from JSON-LD
HR_CONTACT_KEYS: frozenset[str] = frozenset(
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
    }
)

_LD_TAG_RX = re.compile(str(SELECTORS["ld_json_script"]), re.S | re.I)
_HTML_TAG_RX = re.compile(r"<[^>]+>")
_WHITESPACE_RX = re.compile(r"\s+")
_JOB_ID_FROM_PATH_RX = re.compile(r"(?:job[_-])?(\d+)\.html?$", re.I)
_JOB_ID_FROM_URL_RX = re.compile(str(SELECTORS["job_id_regex"]))
_JOBBKK_DETAIL_PATH_RX = re.compile(str(SELECTORS["jobbkk_detail_path_regex"]))
_CANONICAL_RX = re.compile(
    r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', re.I
)
_OG_URL_RX = re.compile(
    r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)["\']', re.I
)

# PII scrubbing regexes (applied in order: mailto/tel -> email -> LINE ID -> phone)
_MAILTO_TEL_RX = re.compile(r"(?:mailto|tel):[^\s\"'<>)\]]+", re.I)
_EMAIL_RX = re.compile(
    r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![A-Za-z0-9._-])"
)
_LINE_RX = re.compile(
    r"(?:"
    r"(?:id\s*line|line\s*id|ไอดี\s*ไลน์|แอด\s*ไลน์|ทัก\s*ไลน์)\s*[:=@\-]?\s*@?[A-Za-z0-9._-]{2,}"
    r"|line\s*(?:oa)?\s*[:=@]\s*@?[A-Za-z0-9._-]{2,}"
    r"|line\s+@[A-Za-z0-9._-]{2,}"
    r")",
    re.I,
)
_PHONE_RX = re.compile(
    r"(?<![\dA-Za-z])"
    r"(?:"
    r"\+66[\s\-.]*(?:\(0\)[\s\-.]*)?(?:[689]\d[\s\-.]?\d{3}[\s\-.]?\d{4}|[2-7][\s\-.]?\d{3,4}[\s\-.]?\d{3,4})"
    r"|\(?0[689]\d\)?[\s\-.]?\d{3}[\s\-.]?\d{4}"
    r"|\(?02\)?[\s\-.]?\d{3}[\s\-.]?\d{4}"
    r"|\(?0[3-7]\d\)?[\s\-.]?\d{3}[\s\-.]?\d{3,4}"
    r")"
    r"(?!\d)"
)
_HR_CONTACT_NAME_RX = re.compile(
    r"(?:(?<=REDACTED_PHONE\]\s)|(?<=REDACTED_LINE\]\s)|(?<=REDACTED_EMAIL\]\s))"
    r"(?:คุณ|K\.)\s*[ก-๙A-Za-z.]{2,25}"
    r"|(?:ติดต่อ\s*)?(?:คุณ|K\.)\s*[ก-๙A-Za-z.]{2,25}(?=\s*(?:\[REDACTED_(?:PHONE|LINE|EMAIL)\]))",
    re.I,
)
_URL_RX = re.compile(r"https?://[^\s\"'<>]+", re.I)


def iter_jsonld_candidates(html: str) -> Iterator[str]:
    """Yield raw JSON-LD strings from Next.js `self.__next_s` and `<script>` tags."""
    marker = str(SELECTORS["next_s_marker"])
    decoder = json.JSONDecoder()
    pos = 0
    while True:
        idx = html.find(marker, pos)
        if idx == -1:
            break
        start = idx + len(marker)
        try:
            obj, end = decoder.raw_decode(html, start)
        except json.JSONDecodeError:
            pos = start
            continue
        if isinstance(obj, dict) and obj.get("type") == "application/ld+json" and "children" in obj:
            children = obj["children"]
            if isinstance(children, str):
                yield children
            elif isinstance(children, (dict, list)):
                yield json.dumps(children, ensure_ascii=False)
        pos = end

    for match in _LD_TAG_RX.finditer(html):
        yield match.group(1)


def scrub_pii(text: str | None) -> str | None:
    """Scrub emails, LINE IDs, and Thai phone numbers from text while leaving non-PII URLs intact."""
    if text is None:
        return None
    if not isinstance(text, str):
        text = str(text)

    # Preserve non-PII http(s) URLs (e.g. company logo image timestamps) temporarily
    urls: list[str] = []

    def _hold_url(m: re.Match[str]) -> str:
        url = m.group(0)
        # If an email sneaked inside a URL query/path, scrub it too
        url = _EMAIL_RX.sub("[REDACTED_EMAIL]", url)
        idx = len(urls)
        urls.append(url)
        return f"__URL_PLACEHOLDER_{idx}__"

    cleaned = _URL_RX.sub(_hold_url, text)
    cleaned = _MAILTO_TEL_RX.sub("[REDACTED]", cleaned)
    cleaned = _EMAIL_RX.sub("[REDACTED_EMAIL]", cleaned)
    cleaned = _LINE_RX.sub("[REDACTED_LINE]", cleaned)
    cleaned = _PHONE_RX.sub("[REDACTED_PHONE]", cleaned)
    cleaned = _HR_CONTACT_NAME_RX.sub("[REDACTED_CONTACT]", cleaned)

    for idx, url in enumerate(urls):
        cleaned = cleaned.replace(f"__URL_PLACEHOLDER_{idx}__", url)
    return cleaned


def strip_hr_contacts(obj: Any) -> Any:
    """Recursively remove HR contact keys and scrub PII from all string values."""
    if isinstance(obj, dict):
        result: dict[str, Any] = {}
        for k, v in obj.items():
            if str(k).strip().lower() in HR_CONTACT_KEYS:
                continue
            result[k] = strip_hr_contacts(v)
        return result
    if isinstance(obj, list):
        return [strip_hr_contacts(v) for v in obj]
    if isinstance(obj, str):
        return scrub_pii(obj)
    return obj


def _clean_html_text(value: Any) -> str | None:
    """Convert HTML-containing field into scrubbed plain text."""
    if value is None:
        return None
    if isinstance(value, list):
        value = " ".join(str(x) for x in value if x is not None)
    if not isinstance(value, str):
        value = str(value)
    text = _HTML_TAG_RX.sub(" ", value)
    text = htmllib.unescape(text)
    text = _WHITESPACE_RX.sub(" ", text).strip()
    text = scrub_pii(text) or ""
    return text or None


def _to_float(val: Any) -> float | None:
    if val is None or isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        stripped = val.replace(",", "").strip()
        if not stripped:
            return None
        try:
            return float(stripped)
        except ValueError:
            return None
    return None


def _extract_salary(base_salary: Any) -> tuple[str | None, float | None, float | None]:
    """Extract (salary_text, salary_min, salary_max) from JobPosting.baseSalary."""
    if not base_salary:
        return None, None, None
    if isinstance(base_salary, str):
        return scrub_pii(base_salary.strip()) or None, None, None
    if not isinstance(base_salary, dict):
        return None, None, None

    currency = str(base_salary.get("currency") or "THB").strip()
    val_obj = base_salary.get("value")
    if isinstance(val_obj, dict):
        s_min = _to_float(val_obj.get("minValue"))
        s_max = _to_float(val_obj.get("maxValue"))
        single = _to_float(val_obj.get("value"))
        unit = str(val_obj.get("unitText") or "").strip().upper()
        if s_min is None and s_max is None and single is not None:
            s_min = single
            s_max = single
        if s_min is not None and s_max is not None:
            amount_str = f"{int(s_min) if s_min.is_integer() else s_min}-{int(s_max) if s_max.is_integer() else s_max}"
        elif s_min is not None:
            amount_str = f"{int(s_min) if s_min.is_integer() else s_min}+"
        elif s_max is not None:
            amount_str = f"up to {int(s_max) if s_max.is_integer() else s_max}"
        else:
            amount_str = ""
        parts = [p for p in (amount_str, currency if amount_str else "", unit) if p]
        salary_text = " ".join(parts) if parts else None
        return scrub_pii(salary_text), s_min, s_max

    scalar = _to_float(val_obj)
    if scalar is not None:
        unit = str(base_salary.get("unitText") or "").strip().upper()
        amt = str(int(scalar) if scalar.is_integer() else scalar)
        salary_text = " ".join(p for p in (amt, currency, unit) if p)
        return scrub_pii(salary_text), scalar, scalar

    return None, None, None


def _extract_jobbkk_detail(
    html: str,
    item: dict[str, Any],
    preferred_job_id: str | None = None,
) -> tuple[str | None, str | None]:
    """Extract (company_id, job_id) from JobBKK canonical/og:url/JSON-LD/HTML."""
    candidates: list[str] = []
    for rx in (_CANONICAL_RX, _OG_URL_RX):
        m = rx.search(html)
        if m:
            candidates.append(m.group(1))
    for cand in (item.get("url"), item.get("sameAs")):
        if isinstance(cand, str):
            candidates.append(cand)
    org = item.get("hiringOrganization")
    if isinstance(org, dict) and isinstance(org.get("sameAs"), str):
        candidates.append(org["sameAs"])

    matches: list[tuple[str, str]] = []
    for text in candidates:
        for cid, jid in _JOBBKK_DETAIL_PATH_RX.findall(text):
            matches.append((cid, jid))

    if not matches:
        for cid, jid in _JOBBKK_DETAIL_PATH_RX.findall(html):
            matches.append((cid, jid))

    if not matches:
        return None, None
    if preferred_job_id:
        for cid, jid in matches:
            if jid == preferred_job_id:
                return cid, jid
    return matches[0]


def _extract_job_id(
    html: str,
    item: dict[str, Any],
    source: str = "jobthai",
    source_job_id: str | None = None,
    file_path: str | Path | None = None,
) -> str | None:
    """Resolve numeric job id from argument, file path, source URLs, JSON-LD, or HTML."""
    if source_job_id:
        return str(source_job_id).strip()

    if file_path is not None:
        name = Path(file_path).name
        m = _JOB_ID_FROM_PATH_RX.search(name)
        if m:
            return m.group(1)

    if source == "jobbkk":
        _, jid = _extract_jobbkk_detail(html, item)
        if jid:
            return jid

    for candidate in (item.get("url"), item.get("sameAs")):
        if isinstance(candidate, str):
            m = _JOB_ID_FROM_URL_RX.search(candidate)
            if m:
                return m.group(1)

    for rx in (_CANONICAL_RX, _OG_URL_RX):
        m = rx.search(html)
        if m:
            jm = _JOB_ID_FROM_URL_RX.search(m.group(1))
            if jm:
                return jm.group(1)

    jm = _JOB_ID_FROM_URL_RX.search(html)
    if jm:
        return jm.group(1)

    ident = item.get("identifier")
    if isinstance(ident, dict) and ident.get("value"):
        return str(ident["value"]).strip()
    if isinstance(ident, (str, int)):
        return str(ident).strip()

    return None


def _compute_content_hash(record_fields: dict[str, Any]) -> str:
    """Compute deterministic SHA-256 hex digest over scrubbed content fields."""
    canonical = json.dumps(record_fields, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _normalize_date(value: Any) -> str | None:
    if not value or not isinstance(value, str):
        return None
    val = value.strip()
    if len(val) >= 10 and re.match(r"^\d{4}-\d{2}-\d{2}", val):
        return val[:10]
    return None


def _normalize_province(raw_province: Any) -> str | None:
    if not raw_province or not isinstance(raw_province, str):
        return None
    cleaned = raw_province.replace("จังหวัด", "").strip()
    if cleaned in {"กรุงเทพ", "กรุงเทพฯ", "กทม", "กทม.", "Bangkok"}:
        return "กรุงเทพมหานคร"
    return scrub_pii(cleaned) or None


def extract_jobposting_jsonld(html: str) -> dict[str, Any] | None:
    """Find and return the first schema.org JobPosting dict from HTML (unstripped)."""
    for raw in iter_jsonld_candidates(html):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                return item
    return None


def parse_html(
    html: str,
    source: str = "jobthai",
    source_job_id: str | None = None,
    source_url: str | None = None,
    file_path: str | Path | None = None,
) -> dict[str, Any] | None:
    """Parse a job posting HTML string into a PDPA-clean `staging.job_posting_raw` record."""
    raw_item = extract_jobposting_jsonld(html)
    if raw_item is None:
        return None
    return parse_jobposting_item(
        raw_item,
        source=source,
        source_job_id=source_job_id,
        source_url=source_url,
        html=html,
        file_path=file_path,
    )


def parse_jobposting_item(
    raw_item: dict[str, Any],
    source: str = "jobthai",
    source_job_id: str | None = None,
    source_url: str | None = None,
    html: str = "",
    file_path: str | Path | None = None,
) -> dict[str, Any] | None:
    """Turn one schema.org JobPosting dict into a PDPA-clean staging record.

    Used by `parse_html` and by `import_sqlite`, which reads JSON-LD the
    harvesters in `scraper/` already stored (no HTML kept there).
    """
    source_norm = validate_source(source)
    if not isinstance(raw_item, dict) or raw_item.get("@type") != "JobPosting":
        return None

    # Strip all HR contact keys and PII from payload first
    clean_payload = strip_hr_contacts(raw_item)
    if isinstance(clean_payload.get("description"), str):
        clean_payload["description"] = _clean_html_text(clean_payload["description"])
    if isinstance(clean_payload.get("qualifications"), str):
        clean_payload["qualifications"] = _clean_html_text(clean_payload["qualifications"])

    resolved_id = _extract_job_id(
        html,
        clean_payload,
        source=source_norm,
        source_job_id=source_job_id,
        file_path=file_path,
    )
    if not resolved_id:
        return None

    if source_url:
        resolved_url = source_url
    elif source_norm == "jobthai":
        resolved_url = JOBTHAI_DETAIL_URL.format(job_id=resolved_id)
    elif source_norm == "jobbkk":
        cid, jid = _extract_jobbkk_detail(html, clean_payload, preferred_job_id=resolved_id)
        if cid and jid:
            resolved_url = JOBBKK_DETAIL_URL.format(company_id=cid, job_id=jid)
        else:
            resolved_url = str(clean_payload.get("url") or "")
    else:
        resolved_url = str(clean_payload.get("url") or "")

    loc = clean_payload.get("jobLocation") or {}
    if isinstance(loc, list):
        loc = loc[0] if loc else {}
    addr = loc.get("address") if isinstance(loc, dict) else {}
    if not isinstance(addr, dict):
        addr = {}

    org = clean_payload.get("hiringOrganization") or {}
    company_name = scrub_pii(org.get("name").strip()) if isinstance(org, dict) and isinstance(org.get("name"), str) else None

    title = _clean_html_text(clean_payload.get("title"))
    description = _clean_html_text(clean_payload.get("description"))
    qualifications = _clean_html_text(clean_payload.get("qualifications"))
    salary_text, salary_min, salary_max = _extract_salary(clean_payload.get("baseSalary"))
    province = _normalize_province(addr.get("addressRegion"))
    district = scrub_pii(str(addr.get("addressLocality")).strip()) if addr.get("addressLocality") else None

    job_cat = clean_payload.get("occupationalCategory")
    if isinstance(job_cat, list):
        job_cat = ", ".join(str(x) for x in job_cat if x)
    job_category = scrub_pii(str(job_cat).strip()) if job_cat else None

    ind = clean_payload.get("industry")
    if isinstance(ind, list):
        ind = ", ".join(str(x) for x in ind if x)
    industry = scrub_pii(str(ind).strip()) if ind else None

    emp = clean_payload.get("employmentType")
    if isinstance(emp, list):
        emp = ", ".join(str(x) for x in emp if x)
    employment_type = scrub_pii(str(emp).strip()) if emp else None

    date_posted = _normalize_date(clean_payload.get("datePosted"))
    valid_through = _normalize_date(clean_payload.get("validThrough"))

    hash_basis = {
        "source": source_norm,
        "source_job_id": resolved_id,
        "title": title,
        "description": description,
        "qualifications": qualifications,
        "salary_text": salary_text,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "province": province,
        "district": district,
        "job_category": job_category,
        "industry": industry,
        "employment_type": employment_type,
        "date_posted": date_posted,
        "valid_through": valid_through,
        "company_name": company_name,
    }
    content_hash = _compute_content_hash(hash_basis)

    return {
        "source": source_norm,
        "source_job_id": resolved_id,
        "source_url": resolved_url,
        "title": title,
        "description": description,
        "qualifications": qualifications,
        "salary_text": salary_text,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "province": province,
        "district": district,
        "job_category": job_category,
        "industry": industry,
        "employment_type": employment_type,
        "date_posted": date_posted,
        "valid_through": valid_through,
        "company_name": company_name,
        "payload": clean_payload,
        "content_hash": content_hash,
    }


def parse_file(
    path: str | Path,
    source: str = "jobthai",
    source_job_id: str | None = None,
) -> dict[str, Any] | None:
    """Read a saved HTML file from disk and parse it into a PDPA-clean staging record."""
    file_path = Path(path)
    html = file_path.read_text(encoding="utf-8", errors="ignore")
    return parse_html(
        html,
        source=source,
        source_job_id=source_job_id,
        file_path=file_path,
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint printing parsed JSONL records to stdout."""
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("Usage: py -3 -I -X utf8 -m pipeline.scraper.parse <html_file> [...]", file=sys.stderr)
        return 1
    exit_code = 0
    for file_arg in args:
        rec = parse_file(file_arg)
        if rec is None:
            print(json.dumps({"_source_file": file_arg, "_error": "no JobPosting"}, ensure_ascii=False), file=sys.stderr)
            exit_code = 1
        else:
            print(json.dumps(rec, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
