"""8-dimension Data Quality validation suite per ARCHITECTURE.md §7 (T3.3)."""
from __future__ import annotations

from datetime import date
from typing import Any

from pipeline.etl.clean import CANONICAL_PROVINCES, contains_hr_pii

FORBIDDEN_HR_COLUMNS: frozenset[str] = frozenset(
    {"telephone", "email", "contactpoint", "applicationcontact", "faxnumber", "contact", "hr_name", "hr_phone", "hr_email", "line_id"}
)
FORBIDDEN_ML_COLUMNS: frozenset[str] = frozenset(
    {"gender", "age", "company_name", "company_name_norm", "description", "qualifications", "telephone", "email", "line_id"}
)
FORBIDDEN_PUBLIC_TEXT_COLUMNS: frozenset[str] = frozenset({"description", "qualifications", "description_preview"})


def _make_check(
    dimension: str,
    check_name: str,
    table_name: str,
    n_total: int,
    n_fail: int,
    pass_flag: bool,
    details: str,
) -> dict[str, Any]:
    return {
        "dimension": dimension,
        "check_name": check_name,
        "table_name": table_name,
        "n_total": int(n_total),
        "n_fail": int(n_fail),
        "pass": bool(pass_flag),
        "details": details,
    }


def run_dq_checks(
    postings: list[dict[str, Any]],
    stratum_population: dict[str, float] | None = None,
    pending_aliases: list[dict[str, Any]] | None = None,
    reference_date: date | None = None,
    ml_feature_columns: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Run all 8 DQ dimensions against cleaned DW-ready postings."""
    n = len(postings)
    if reference_date is None:
        dates = [str(p.get("date_posted") or "")[:10] for p in postings if p.get("date_posted")]
        reference_date = date.fromisoformat(max(dates)) if dates else date.today()

    checks: list[dict[str, Any]] = []

    # 1. Completeness
    core_missing = sum(
        1
        for p in postings
        if not p.get("title_short")
        or not p.get("province_th")
        or p.get("province_th") == "ไม่ระบุ"
        or not p.get("occupational_category")
        or not p.get("company_name_norm")
        or p.get("company_name_norm") == "unknown"
    )
    comp_rate = (n - core_missing) / n if n else 0.0
    checks.append(
        _make_check(
            "Completeness",
            "Completeness: core_fields_complete",
            "dw.fact_job_posting",
            n,
            core_missing,
            n > 0 and comp_rate >= 0.90,
            f"Core fields (title, province, category, company) complete: {n - core_missing}/{n} ({comp_rate:.1%})",
        )
    )

    n_no_salary = sum(1 for p in postings if not p.get("has_salary"))
    sal_rate = (n - n_no_salary) / n if n else 0.0
    checks.append(
        _make_check(
            "Completeness",
            "Completeness: numeric_salary_rate",
            "dw.fact_job_posting",
            n,
            n_no_salary,
            n > 0 and sal_rate >= 0.35,
            f"Numeric salary available: {n - n_no_salary}/{n} ({sal_rate:.1%})",
        )
    )

    # 2. Validity
    sal_rows = [p for p in postings if p.get("has_salary")]
    sal_invalid = sum(
        1
        for p in sal_rows
        if (p.get("salary_min") is not None and p.get("salary_max") is not None and float(p["salary_min"]) > float(p["salary_max"]))
        or float(p["salary_mid"]) < 5000.0
        or float(p["salary_mid"]) > 500000.0
    )
    out_of_range_cnt = sum(1 for p in postings if p.get("salary_out_of_range"))
    checks.append(
        _make_check(
            "Validity",
            "Validity: salary_bounds_and_order",
            "dw.fact_job_posting",
            len(sal_rows),
            sal_invalid,
            sal_invalid == 0,
            f"Valid monthly THB [5000, 500000] & min<=max: {len(sal_rows) - sal_invalid}/{len(sal_rows)}; quarantined out-of-range={out_of_range_cnt}",
        )
    )

    bad_prov = sum(1 for p in postings if p.get("province_th") not in CANONICAL_PROVINCES)
    bad_dates = 0
    for p in postings:
        dp = str(p.get("date_posted") or "")[:10]
        if dp:
            try:
                if date.fromisoformat(dp) > reference_date:
                    bad_dates += 1
            except ValueError:
                bad_dates += 1
    checks.append(
        _make_check(
            "Validity",
            "Validity: canonical_province_and_date",
            "dw.dim_location",
            n,
            bad_prov + bad_dates,
            bad_prov == 0 and bad_dates == 0,
            f"Canonical provinces={n - bad_prov}/{n}, non-future date_posted={n - bad_dates}/{n}",
        )
    )

    # 3. Uniqueness
    seen_keys: set[tuple[str, str]] = set()
    dup_keys = 0
    seen_hashes: set[str] = set()
    dup_hashes = 0
    for p in postings:
        k = (str(p.get("source") or ""), str(p.get("source_job_id") or ""))
        if k in seen_keys:
            dup_keys += 1
        seen_keys.add(k)
        h = str(p.get("content_hash") or "")
        if h and h in seen_hashes:
            dup_hashes += 1
        if h:
            seen_hashes.add(h)
    checks.append(
        _make_check(
            "Uniqueness",
            "Uniqueness: source_job_id_dedup",
            "dw.fact_job_posting",
            n,
            dup_keys,
            dup_keys == 0,
            f"Duplicate (source, source_job_id)={dup_keys}; identical content_hash across distinct IDs={dup_hashes}",
        )
    )

    # 4. Consistency
    unmapped_occ = sum(1 for p in postings if not p.get("occupation_mapped", True) or p.get("occupation_cluster") == "Other / General")
    occ_rate = (n - unmapped_occ) / n if n else 0.0
    raw_cos = len({p.get("company_raw") for p in postings if p.get("company_raw")})
    norm_cos = len({p.get("company_name_norm") for p in postings if p.get("company_name_norm")})
    checks.append(
        _make_check(
            "Consistency",
            "Consistency: occupation_cluster_mapping",
            "dw.dim_occupation",
            n,
            unmapped_occ,
            n > 0 and occ_rate >= 0.85,
            f"Mapped to occupation cluster: {n - unmapped_occ}/{n} ({occ_rate:.1%}); companies consolidated {raw_cos} -> {norm_cos}",
        )
    )

    # 5. Freshness
    stale_cnt = 0
    expired_cnt = 0
    for p in postings:
        dp = str(p.get("date_posted") or "")[:10]
        if dp:
            try:
                if (reference_date - date.fromisoformat(dp)).days > 60:
                    stale_cnt += 1
            except ValueError:
                stale_cnt += 1
        vt = str(p.get("valid_through") or "")[:10]
        if vt:
            try:
                if date.fromisoformat(vt) < reference_date:
                    expired_cnt += 1
            except ValueError:
                pass
    checks.append(
        _make_check(
            "Freshness",
            "Freshness: active_and_recent_postings",
            "dw.fact_job_posting",
            n,
            stale_cnt + expired_cnt,
            n > 0 and stale_cnt == 0,
            f"Within 60d of reference ({reference_date.isoformat()}): {n - stale_cnt}/{n}; expired valid_through={expired_cnt}",
        )
    )

    # 6. Taxonomy
    no_skill = sum(1 for p in postings if int(p.get("n_skills") or 0) <= 0)
    skill_cov = (n - no_skill) / n if n else 0.0
    n_pending = len(pending_aliases or [])
    checks.append(
        _make_check(
            "Taxonomy",
            "Taxonomy: skill_extraction_coverage",
            "dw.fact_posting_skill",
            n,
            no_skill,
            n > 0 and skill_cov >= 0.90,
            f"Postings with >=1 skill: {n - no_skill}/{n} ({skill_cov:.1%}); pending unmapped candidates queued={n_pending}",
        )
    )

    # 7. Compliance (PDPA, ToS, ML Fairness — column AND value-level PII checks)
    all_cols = {k.lower() for p in postings for k in p.keys()}
    hr_leak = sorted(all_cols & FORBIDDEN_HR_COLUMNS)
    text_leak = sorted(all_cols & FORBIDDEN_PUBLIC_TEXT_COLUMNS)
    ml_cols_lower = {c.lower() for c in (ml_feature_columns or [])}
    ml_leak = sorted(ml_cols_lower & FORBIDDEN_ML_COLUMNS)
    pii_value_leaks = sum(
        1
        for p in postings
        if any(
            contains_hr_pii(str(p.get(col) or ""))
            for col in ("title_short", "job_title_norm", "company_name_norm", "source_url")
        )
    )
    gender_mentions = sum(1 for p in postings if p.get("mentions_gender"))
    age_mentions = sum(1 for p in postings if p.get("mentions_age"))
    comp_fail = len(hr_leak) + len(text_leak) + len(ml_leak) + pii_value_leaks
    checks.append(
        _make_check(
            "Compliance",
            "Compliance: pdpa_tos_and_ml_fairness",
            "dw.fact_job_posting",
            max(1, len(all_cols)),
            comp_fail,
            comp_fail == 0,
            (
                f"HR contact columns={hr_leak}, PII value leaks={pii_value_leaks}, "
                f"raw text leak={text_leak}, forbidden ML cols={ml_leak}; "
                f"DQ-only mentions_gender={gender_mentions}/{n} ({gender_mentions / n:.1%}), "
                f"mentions_age={age_mentions}/{n} ({age_mentions / n:.1%})"
                if n
                else "Empty dataset"
            ),
        )
    )

    # 8. Sampling (D13)
    bad_weight = sum(
        1
        for p in postings
        if not p.get("sample_stratum") or p.get("sample_weight") is None or float(p["sample_weight"]) <= 0
    )
    stratum_sum_diff = 0
    weight_note = "all rows weighted > 0"
    if stratum_population:
        observed_sums: dict[str, float] = {}
        for p in postings:
            st = str(p.get("sample_stratum") or "")
            observed_sums[st] = observed_sums.get(st, 0.0) + float(p.get("sample_weight") or 0.0)
        mismatches = [
            st
            for st, w_sum in observed_sums.items()
            if st in stratum_population and stratum_population[st] > 0 and abs(w_sum - stratum_population[st]) > 0.5
        ]
        stratum_sum_diff = len(mismatches)
        weight_note = f"checked {len(observed_sums)} strata vs N_h; mismatches={stratum_sum_diff}"
    checks.append(
        _make_check(
            "Sampling",
            "Sampling: stratum_and_weight_conservation",
            "dw.fact_job_posting",
            n,
            bad_weight + stratum_sum_diff,
            n > 0 and bad_weight == 0 and stratum_sum_diff == 0,
            f"Valid stratum+weight={n - bad_weight}/{n}; {weight_note}",
        )
    )

    return checks
