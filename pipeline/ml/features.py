"""Feature engineering and fairness/leakage guards for salary regression (T4.1, D6).

Enforces strict separation between:
- Allowed ML features: occupation_cluster, province_th, region, experience_band,
  education_level, employment_type, industry, n_skills, derived ordinal ranks,
  and multi-hot top-K skills.
- Group column: company_name_norm / company_key (used ONLY as GroupKFold groups,
  NEVER included in X).
- Forbidden columns (D6 / PDPA): gender, mentions_gender, age, mentions_age,
  company, company_name, company_name_norm, company_key, HR contact PII, and
  target/salary columns.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

from pipeline.etl.enrich import ENRICH_COLUMNS, SENIORITY_UNKNOWN

SALARY_MIN_THB = 5_000.0
SALARY_MAX_THB = 500_000.0

CATEGORICAL_FEATURES: tuple[str, ...] = (
    "occupation_cluster",
    "province_th",
    "region",
    "experience_band",
    "education_level",
    # JSON-LD employmentType is FULL_TIME for every JobThai posting (no signal), so the
    # type derived from the title/text is used instead (pipeline/etl/enrich.py)
    "employment_type_derived",
    "seniority_level",
    "industry",
)

NUMERIC_FEATURES: tuple[str, ...] = (
    "n_skills",
    "education_rank",
    "exp_years_mid",
)

# Exact forbidden column/key names (lowercase)
FORBIDDEN_FEATURE_NAMES: frozenset[str] = frozenset(
    {
        "gender",
        "mentions_gender",
        "req_gender",
        "age",
        "mentions_age",
        "min_age",
        "max_age",
        "company",
        "company_name",
        "company_name_norm",
        "company_raw",
        "company_key",
        "sex",
        "birth_year",
        "date_of_birth",
        "dob",
        # Target & leakage columns
        "salary_min",
        "salary_max",
        "salary_mid",
        "has_salary",
        "salary_open_max",
        "salary_unit_orig",
        "salary_out_of_range",
        "y_log",
        "y_thb",
        # Raw posting text & HR PII
        "description",
        "qualifications",
        "telephone",
        "email",
        "contact",
        "contactpoint",
        "applicationcontact",
        "faxnumber",
        "line_id",
        "hr_name",
        "hr_phone",
        "hr_email",
        "source_url",
        "source_job_id",
        "content_hash",
    }
)

# Token-level forbidden terms (matched on word/delimiter boundaries so words like
# 'language' or 'management' are not falsely matched as 'age').
_FORBIDDEN_BOUNDED_TOKENS: frozenset[str] = frozenset(
    {
        "gender",
        "age",
        "company",
        "sex",
        "salary",
        "telephone",
        "email",
        "contact",
        "description",
        "qualifications",
        "dob",
    }
)

_FORBIDDEN_SUBSTRINGS: tuple[str, ...] = (
    "gender",
    "mentions_age",
    "company_name",
    "company_key",
    "birth_year",
    "line_id",
    "เพศ",
    "อายุ",
    "ชื่อบริษัท",
)

EDUCATION_RANK_MAP: dict[str, int] = {
    "ไม่ระบุ": 0,
    "ม.3/ม.6": 1,
    "ปวช./ปวส.": 2,
    "ปริญญาตรี": 3,
    "ปริญญาโท+": 4,
}

EXPERIENCE_YEARS_MAP: dict[str, float] = {
    "ไม่ระบุ/ไม่จำเป็น": 0.0,
    "0 ปี / จบใหม่": 0.25,
    "1-2 ปี": 1.5,
    "3-5 ปี": 4.0,
    "5+ ปี": 6.0,
}

# Authoritative fallback map matching supabase/migrations/002_dw_dimensions_and_seed.sql
DEFAULT_PROVINCE_TO_REGION: dict[str, str] = {
    "ทั้งประเทศ": "ทั้งประเทศ",
    "กรุงเทพมหานคร": "กลาง",
    "กระบี่": "ใต้",
    "กาญจนบุรี": "ตะวันตก",
    "กาฬสินธุ์": "อีสาน",
    "กำแพงเพชร": "กลาง",
    "ขอนแก่น": "อีสาน",
    "จันทบุรี": "ตะวันออก",
    "ฉะเชิงเทรา": "ตะวันออก",
    "ชลบุรี": "ตะวันออก",
    "ชัยนาท": "กลาง",
    "ชัยภูมิ": "อีสาน",
    "ชุมพร": "ใต้",
    "เชียงราย": "เหนือ",
    "เชียงใหม่": "เหนือ",
    "ตรัง": "ใต้",
    "ตราด": "ตะวันออก",
    "ตาก": "ตะวันตก",
    "นครนายก": "กลาง",
    "นครปฐม": "กลาง",
    "นครพนม": "อีสาน",
    "นครราชสีมา": "อีสาน",
    "นครศรีธรรมราช": "ใต้",
    "นครสวรรค์": "กลาง",
    "นนทบุรี": "กลาง",
    "นราธิวาส": "ใต้",
    "น่าน": "เหนือ",
    "บุรีรัมย์": "อีสาน",
    "ปทุมธานี": "กลาง",
    "ประจวบคีรีขันธ์": "ตะวันตก",
    "ปราจีนบุรี": "ตะวันออก",
    "ปัตตานี": "ใต้",
    "พระนครศรีอยุธยา": "กลาง",
    "พะเยา": "เหนือ",
    "พังงา": "ใต้",
    "พัทลุง": "ใต้",
    "พิจิตร": "กลาง",
    "พิษณุโลก": "กลาง",
    "เพชรบุรี": "ตะวันตก",
    "เพชรบูรณ์": "กลาง",
    "แพร่": "เหนือ",
    "ภูเก็ต": "ใต้",
    "มหาสารคาม": "อีสาน",
    "มุกดาหาร": "อีสาน",
    "แม่ฮ่องสอน": "เหนือ",
    "ยโสธร": "อีสาน",
    "ยะลา": "ใต้",
    "ร้อยเอ็ด": "อีสาน",
    "ระนอง": "ใต้",
    "ระยอง": "ตะวันออก",
    "ราชบุรี": "ตะวันตก",
    "ลพบุรี": "กลาง",
    "ลำปาง": "เหนือ",
    "ลำพูน": "เหนือ",
    "เลย": "อีสาน",
    "ศรีสะเกษ": "อีสาน",
    "สกลนคร": "อีสาน",
    "สงขลา": "ใต้",
    "สตูล": "ใต้",
    "สมุทรปราการ": "กลาง",
    "สมุทรสงคราม": "กลาง",
    "สมุทรสาคร": "กลาง",
    "สระแก้ว": "ตะวันออก",
    "สระบุรี": "กลาง",
    "สิงห์บุรี": "กลาง",
    "สุโขทัย": "กลาง",
    "สุพรรณบุรี": "กลาง",
    "สุราษฎร์ธานี": "ใต้",
    "สุรินทร์": "อีสาน",
    "หนองคาย": "อีสาน",
    "หนองบัวลำภู": "อีสาน",
    "อ่างทอง": "กลาง",
    "อำนาจเจริญ": "อีสาน",
    "อุดรธานี": "อีสาน",
    "อุตรดิตถ์": "เหนือ",
    "อุทัยธานี": "กลาง",
    "อุบลราชธานี": "อีสาน",
    "บึงกาฬ": "อีสาน",
    "หลายจังหวัด": "ไม่ระบุ",
    "ต่างประเทศ": "ไม่ระบุ",
}


@dataclass(frozen=True)
class FeatureDataset:
    """Container for ML training features, log-target, company groups, and metadata."""

    X: pd.DataFrame
    y_log: np.ndarray
    y_thb: np.ndarray
    groups: np.ndarray
    feature_spec: dict[str, Any]
    postings_used: pd.DataFrame


def is_forbidden_feature_name(name: str) -> bool:
    """Return True if a feature/column name violates D6 fairness, PDPA, or leakage rules."""
    col = str(name).strip().lower()
    if not col:
        return False
    if col in FORBIDDEN_FEATURE_NAMES:
        return True
    if any(sub in col for sub in _FORBIDDEN_SUBSTRINGS):
        return True
    tokens = [tok for tok in re.split(r"[^a-z0-9ก-๙]+", col) if tok]
    if any(tok in _FORBIDDEN_BOUNDED_TOKENS for tok in tokens):
        return True
    return False


def assert_no_forbidden_features(columns: Iterable[str], context: str = "feature matrix") -> None:
    """Raise ValueError if any column violates D6 fairness, PDPA, or target leakage rules."""
    violations = [str(c) for c in columns if is_forbidden_feature_name(str(c))]
    if violations:
        raise ValueError(
            f"Fairness/leakage violation (D6) in {context}: forbidden feature(s) {violations}"
        )


def reject_forbidden_payload(payload: Mapping[str, Any]) -> None:
    """Reject API or inference dictionaries containing forbidden fairness/leakage keys."""
    violations = [str(k) for k in payload.keys() if is_forbidden_feature_name(str(k))]
    if violations:
        raise ValueError(
            f"Fairness policy violation (D6): forbidden input key(s) {violations} must not be provided"
        )


def validate_feature_spec(spec: Mapping[str, Any]) -> None:
    """Verify a feature_spec dictionary contains zero forbidden columns."""
    for key in ("feature_columns", "categorical_features", "numeric_features", "skill_feature_names"):
        cols = spec.get(key) or []
        assert_no_forbidden_features(cols, context=f"feature_spec.{key}")
    top_skills = spec.get("top_skills") or []
    for item in top_skills:
        if isinstance(item, Mapping):
            assert_no_forbidden_features(
                [str(item.get("feature_name", "")), str(item.get("skill_canonical", ""))],
                context="feature_spec.top_skills",
            )


def slugify_skill_feature(skill_canonical: str) -> str:
    """Deterministic safe column name for a multi-hot skill feature."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", str(skill_canonical).strip().lower()).strip("_")
    return f"skill__{slug or 'unknown'}"


def load_skill_aliases_lookup(skills_csv: Path | str | None = None) -> dict[str, str]:
    """Build case-insensitive lookup mapping canonical names and slugs to canonical skill name."""
    lookup: dict[str, str] = {}
    if skills_csv is None:
        candidate = Path(__file__).resolve().parents[2] / "taxonomy" / "skills.csv"
    else:
        candidate = Path(skills_csv)
    if not candidate.exists():
        return lookup
    with open(candidate, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            canon = (row.get("skill_canonical") or "").strip()
            slug = (row.get("skill_slug") or "").strip().lower()
            name_th = (row.get("skill_name_th") or "").strip()
            if not canon:
                continue
            lookup[canon.lower()] = canon
            if slug:
                lookup[slug] = canon
            if name_th:
                lookup[name_th.lower()] = canon
    return lookup


def _parse_bool_series(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "yes"})


def parse_skills_cell(val: Any) -> list[str]:
    """Parse pipe-separated or list skills into deduplicated list preserving order."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return []
    if isinstance(val, (list, tuple, set)):
        raw_items = [str(x).strip() for x in val]
    else:
        raw_items = [x.strip() for x in str(val).split("|")]
    seen: set[str] = set()
    out: list[str] = []
    for item in raw_items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def filter_salaried_postings(df: pd.DataFrame) -> pd.DataFrame:
    """Keep ONLY rows where has_salary is True and salary_mid is within [5000, 500000]."""
    if df.empty:
        return df.copy()
    has_sal = _parse_bool_series(df["has_salary"]) if "has_salary" in df.columns else pd.Series(True, index=df.index)
    sal_mid = pd.to_numeric(df["salary_mid"], errors="coerce")
    mask = has_sal & sal_mid.notna() & np.isfinite(sal_mid) & (sal_mid >= SALARY_MIN_THB) & (sal_mid <= SALARY_MAX_THB)
    filtered = df.loc[mask].copy().reset_index(drop=True)
    filtered["salary_mid"] = pd.to_numeric(filtered["salary_mid"], errors="raise").astype(float)
    return filtered


def _clean_cat(series: pd.Series | None, default: str, length: int) -> pd.Series:
    if series is None:
        return pd.Series([default] * length, dtype="object")
    s = series.fillna(default).astype(str).str.strip()
    return s.replace({"": default, "nan": default, "None": default, "NaN": default})


def build_feature_matrix(
    df: pd.DataFrame,
    *,
    top_k_skills: int = 40,
    min_skill_freq: int = 1,
    feature_spec: Mapping[str, Any] | None = None,
    extra_columns: Iterable[str] | None = None,
    reject_forbidden_in_input: bool = False,
    skills_csv: Path | str | None = None,
) -> FeatureDataset:
    """Build clean ML feature matrix X, log(salary_mid) target, and company groups.

    Args:
        df: Cleaned postings DataFrame (e.g. from data/processed/clean_postings.csv).
        top_k_skills: Max number of multi-hot skill columns when fitting a new spec.
        min_skill_freq: Minimum occurrence count for a skill to become a multi-hot feature.
        feature_spec: Optional existing spec to align columns deterministically.
        extra_columns: Optional caller-requested extra columns (rejected if forbidden).
        reject_forbidden_in_input: If True, raise ValueError if any forbidden column
            (like 'gender', 'age', 'company', 'company_name') is present in df.
        skills_csv: Optional path to taxonomy/skills.csv for alias/slug lookup.
    """
    if extra_columns is not None:
        extra_list = list(extra_columns)
        assert_no_forbidden_features(extra_list, context="extra_columns")

    if reject_forbidden_in_input:
        # Check raw columns except company_name_norm / company_key which are allowed ONLY as group IDs,
        # and except salary_mid / has_salary which define the target filter.
        allowed_non_feature_df_cols = {
            "source",
            "source_job_id",
            "source_url",
            "title_short",
            "company_name_norm",
            "company_key",
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
            "content_hash",
            *ENRICH_COLUMNS,  # derived analysis columns; only ML_CATEGORICAL_ENRICH become features
        }
        injected =[c for c in df.columns if c not in allowed_non_feature_df_cols and is_forbidden_feature_name(str(c))]
        if injected:
            raise ValueError(
                f"Fairness/leakage violation (D6) in input DataFrame: forbidden column(s) {injected}"
            )

    sal_df = filter_salaried_postings(df)
    if sal_df.empty:
        raise ValueError("No valid salaried rows remain after filtering has_salary & salary_mid in [5000, 500000].")

    n = len(sal_df)

    # Extract groups ONLY for GroupKFold (never placed in X)
    if "company_name_norm" in sal_df.columns:
        groups_series = _clean_cat(sal_df["company_name_norm"], "unknown_company", n)
    elif "company_key" in sal_df.columns:
        groups_series = _clean_cat(sal_df["company_key"], "unknown_company", n)
    else:
        raise ValueError("Input DataFrame must contain 'company_name_norm' or 'company_key' for GroupKFold grouping.")
    groups = groups_series.to_numpy(dtype=object)

    # Target
    y_thb = sal_df["salary_mid"].to_numpy(dtype=np.float64)
    y_log = np.log(y_thb)

    # Categorical features
    cat_defaults = {
        "occupation_cluster": "Other / General",
        "province_th": "ไม่ระบุ",
        "region": "ไม่ระบุ",
        "experience_band": "ไม่ระบุ/ไม่จำเป็น",
        "education_level": "ไม่ระบุ",
        "employment_type": "FULL_TIME",
        "employment_type_derived": "full_time",
        "seniority_level": SENIORITY_UNKNOWN,
        "industry": "อื่นๆ",
    }
    X_dict: dict[str, Any] = {}
    for col in CATEGORICAL_FEATURES:
        X_dict[col] = _clean_cat(sal_df[col] if col in sal_df.columns else None, cat_defaults[col], n)

    # Parsed skill lists
    parsed_skills: list[list[str]] = (
        [parse_skills_cell(v) for v in sal_df["skills"]]
        if "skills" in sal_df.columns
        else [[] for _ in range(n)]
    )

    if "n_skills" in sal_df.columns:
        n_skills_vals = pd.to_numeric(sal_df["n_skills"], errors="coerce").fillna(0).astype(float)
    else:
        n_skills_vals = pd.Series([float(len(s)) for s in parsed_skills], dtype=float)

    X_dict["n_skills"] = n_skills_vals
    X_dict["education_rank"] = X_dict["education_level"].map(EDUCATION_RANK_MAP).fillna(0).astype(float)
    X_dict["exp_years_mid"] = X_dict["experience_band"].map(EXPERIENCE_YEARS_MAP).fillna(0.0).astype(float)

    # Determine top-K skill columns
    if feature_spec is not None:
        validate_feature_spec(feature_spec)
        top_skills_meta = list(feature_spec.get("top_skills") or [])
    else:
        counts: dict[str, int] = {}
        for sk_list in parsed_skills:
            for sk in sk_list:
                counts[sk] = counts.get(sk, 0) + 1
        ranked = sorted(
            [(sk, cnt) for sk, cnt in counts.items() if cnt >= min_skill_freq],
            key=lambda kv: (-kv[1], kv[0]),
        )[:top_k_skills]

        used_names: set[str] = set()
        top_skills_meta = []
        for sk, cnt in ranked:
            fname = slugify_skill_feature(sk)
            while fname in used_names:
                fname = f"{fname}_dup"
            used_names.add(fname)
            top_skills_meta.append(
                {
                    "skill_canonical": sk,
                    "feature_name": fname,
                    "train_count": int(cnt),
                }
            )

    for sk_meta in top_skills_meta:
        canon = str(sk_meta["skill_canonical"])
        fname = str(sk_meta["feature_name"])
        X_dict[fname] = np.array([1.0 if canon in row_sks else 0.0 for row_sks in parsed_skills], dtype=np.float64)

    X = pd.DataFrame(X_dict)

    # Strict final check against forbidden columns / leakage
    assert_no_forbidden_features(X.columns, context="X")
    if "company_name_norm" in X.columns or "company_key" in X.columns:
        raise ValueError("company_name_norm / company_key leaked into X!")

    province_to_region = dict(DEFAULT_PROVINCE_TO_REGION)
    for prov_val, reg_val in zip(X["province_th"], X["region"]):
        if prov_val and prov_val not in ("ไม่ระบุ", "ทั้งประเทศ") and reg_val:
            province_to_region.setdefault(str(prov_val), str(reg_val))

    known_categories = {
        col: sorted({str(v) for v in X[col].tolist() if str(v)})
        for col in CATEGORICAL_FEATURES
    }
    occ_support = {
        str(k): int(v)
        for k, v in X["occupation_cluster"].value_counts().items()
    }
    skill_lookup = load_skill_aliases_lookup(skills_csv)
    for sk_meta in top_skills_meta:
        canon = str(sk_meta["skill_canonical"])
        skill_lookup.setdefault(canon.lower(), canon)

    skill_feature_names = [str(m["feature_name"]) for m in top_skills_meta]
    spec_out: dict[str, Any] = {
        "schema_version": "1.0",
        "n_rows": int(n),
        "n_total_postings": int(len(df)),
        "n_companies": int(pd.Series(groups).nunique()),
        "target": "log(salary_mid)",
        "target_unit": "THB",
        "salary_bounds": [SALARY_MIN_THB, SALARY_MAX_THB],
        "categorical_features": list(CATEGORICAL_FEATURES),
        "numeric_features": list(NUMERIC_FEATURES),
        "top_skills": top_skills_meta,
        "skill_feature_names": skill_feature_names,
        "feature_columns": list(X.columns),
        "forbidden_features": sorted(FORBIDDEN_FEATURE_NAMES),
        "known_categories": known_categories,
        "occupation_support_counts": occ_support,
        "province_to_region": province_to_region,
        "skill_aliases_lookup": skill_lookup,
    }
    validate_feature_spec(spec_out)

    return FeatureDataset(
        X=X,
        y_log=y_log,
        y_thb=y_thb,
        groups=groups,
        feature_spec=spec_out,
        postings_used=sal_df,
    )


def build_inference_dataframe(
    records: list[Mapping[str, Any]],
    feature_spec: Mapping[str, Any],
) -> pd.DataFrame:
    """Transform API/fallback prediction payloads into exact DataFrame columns expected by the Champion model.

    Strictly rejects any payload containing D6 forbidden keys (gender, mentions_gender,
    age, mentions_age, company, company_name, company_name_norm, etc.).
    """
    validate_feature_spec(feature_spec)
    if not records:
        raise ValueError("At least one prediction payload record is required.")

    province_to_region = feature_spec.get("province_to_region") or DEFAULT_PROVINCE_TO_REGION
    skill_lookup: dict[str, str] = {
        str(k).lower(): str(v) for k, v in (feature_spec.get("skill_aliases_lookup") or {}).items()
    }
    top_skills_meta = feature_spec.get("top_skills") or []
    feature_columns = list(feature_spec.get("feature_columns") or [])

    rows_out: list[dict[str, Any]] = []
    for rec in records:
        reject_forbidden_payload(rec)

        occ = str(rec.get("occupation_cluster") or "Other / General").strip() or "Other / General"
        prov = str(rec.get("province_th") or "ทั้งประเทศ").strip() or "ทั้งประเทศ"
        reg_raw = str(rec.get("region") or "").strip()
        if not reg_raw or reg_raw == "ไม่ระบุ":
            reg = str(province_to_region.get(prov, "ทั้งประเทศ" if prov == "ทั้งประเทศ" else "ไม่ระบุ"))
        else:
            reg = reg_raw
        exp_band = str(rec.get("experience_band") or "ไม่ระบุ/ไม่จำเป็น").strip() or "ไม่ระบุ/ไม่จำเป็น"
        edu_level = str(rec.get("education_level") or "ไม่ระบุ").strip() or "ไม่ระบุ"
        emp_type = str(rec.get("employment_type") or "FULL_TIME").strip() or "FULL_TIME"
        industry = str(rec.get("industry") or "อื่นๆ").strip() or "อื่นๆ"

        raw_skills = parse_skills_cell(rec.get("skills"))
        canonical_skills: set[str] = set()
        for sk in raw_skills:
            resolved = skill_lookup.get(sk.lower(), sk)
            canonical_skills.add(resolved)

        n_sk_val = rec.get("n_skills")
        if n_sk_val is None:
            n_skills = float(len(canonical_skills))
        else:
            n_skills = float(n_sk_val)

        row_dict: dict[str, Any] = {
            "occupation_cluster": occ,
            "province_th": prov,
            "region": reg,
            "experience_band": exp_band,
            "education_level": edu_level,
            "employment_type": emp_type,
            # users pick these on the Salary page; unknown -> same defaults as training
            "employment_type_derived": str(rec.get("employment_type_derived") or "full_time").strip() or "full_time",
            "seniority_level": str(rec.get("seniority_level") or SENIORITY_UNKNOWN).strip() or SENIORITY_UNKNOWN,
            "industry": industry,
            "n_skills": n_skills,
            "education_rank": float(EDUCATION_RANK_MAP.get(edu_level, 0)),
            "exp_years_mid": float(EXPERIENCE_YEARS_MAP.get(exp_band, 0.0)),
        }
        for sk_meta in top_skills_meta:
            canon = str(sk_meta["skill_canonical"])
            fname = str(sk_meta["feature_name"])
            row_dict[fname] = 1.0 if canon in canonical_skills else 0.0

        rows_out.append(row_dict)

    X = pd.DataFrame(rows_out)
    if feature_columns:
        for col in feature_columns:
            if col not in X.columns:
                X[col] = 0.0
        X = X[feature_columns]

    assert_no_forbidden_features(X.columns, context="inference_dataframe")
    return X


def is_out_of_domain_record(
    record: Mapping[str, Any],
    feature_spec: Mapping[str, Any],
    p50_thb: float,
) -> bool:
    """Flag whether a salary prediction is outside well-supported training domain."""
    occ = str(record.get("occupation_cluster") or "").strip()
    known_cats = feature_spec.get("known_categories") or {}
    known_occs = set(known_cats.get("occupation_cluster") or [])
    occ_support = feature_spec.get("occupation_support_counts") or {}
    support = int(occ_support.get(occ, 0))

    if occ not in known_occs or support < 2:
        return True

    prov = str(record.get("province_th") or "ทั้งประเทศ").strip()
    reg = str(record.get("region") or "").strip()
    known_provs = set(known_cats.get("province_th") or [])
    known_regs = set(known_cats.get("region") or [])
    if prov not in ("", "ทั้งประเทศ", "ไม่ระบุ", "ทั้งหมดในภาค") and prov not in known_provs:
        if reg not in known_regs:
            return True

    if p50_thb < SALARY_MIN_THB or p50_thb > SALARY_MAX_THB:
        return True
    return False


def predict_salary_records(
    model: Any,
    feature_spec: Mapping[str, Any],
    records: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Single source of truth for Champion salary predictions (used by export_model & ml-api).

    Returns exact THB predictions (`exp(y_log)`) and centered OOF residual quantiles p25..p75.
    """
    X = build_inference_dataframe(records, feature_spec)
    pred_log_arr = np.asarray(model.predict(X), dtype=np.float64)
    pred_log_arr = np.clip(pred_log_arr, np.log(1_000.0), np.log(2_000_000.0))

    quantiles = feature_spec.get("residual_quantiles_log") or {}
    q25_off = float(min(0.0, float(quantiles.get("q25", -0.15))))
    q75_off = float(max(0.0, float(quantiles.get("q75", 0.15))))

    cv_metrics = feature_spec.get("cv_metrics") or {}
    model_name = str(feature_spec.get("champion_model") or "Champion")
    mae_val = cv_metrics.get("mae")
    mape_val = cv_metrics.get("mape")
    occ_support = feature_spec.get("occupation_support_counts") or {}

    results: list[dict[str, Any]] = []
    for rec, pred_log in zip(records, pred_log_arr):
        p50 = float(np.exp(pred_log))
        p25 = float(np.exp(pred_log + q25_off))
        p75 = float(np.exp(pred_log + q75_off))
        occ = str(rec.get("occupation_cluster") or "").strip()
        results.append(
            {
                "p25": p25,
                "p50": p50,
                "p75": p75,
                "model_name": model_name,
                "mae": float(mae_val) if mae_val is not None else None,
                "mape": float(mape_val) if mape_val is not None else None,
                "cv_mae": float(mae_val) if mae_val is not None else None,
                "cv_mape": float(mape_val) if mape_val is not None else None,
                "n_support": int(occ_support.get(occ, 0)),
                "out_of_domain": is_out_of_domain_record(rec, feature_spec, p50),
            }
        )
    return results
