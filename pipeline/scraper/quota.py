"""Stratified sampling quota planner and sample_weight verifier (T1.7, D13).

Implements proportional allocation with a minimum floor of 5 postings per stratum
(or N_h when N_h < 5):
    n_h = min(N_h, max(5, round(n_target * N_h / N_total)))
    sample_weight = N_h / n_h

Guarantees exact conservation per stratum:
    sum(sample_weight for sampled row in stratum_h) == N_h
"""
from __future__ import annotations

import argparse
import csv
import math
import random
from pathlib import Path
from typing import Any


def load_province_totals(csv_path: str | Path) -> list[dict[str, Any]]:
    """Load province stratum population sizes (N_h) from CSV."""
    path = Path(csv_path)
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            code = str(row.get("code") or "").strip()
            province = str(row.get("province") or "").strip()
            raw_total = row.get("total")
            n_h_pop = int(raw_total) if raw_total not in (None, "") else 0
            stratum = f"p={code}" if code else f"p={province}"
            rows.append(
                {
                    "stratum": stratum,
                    "code": code,
                    "province": province,
                    "N_h": n_h_pop,
                }
            )
    return rows


def _normalize_strata_input(
    strata: dict[str, int] | list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if isinstance(strata, dict):
        return [
            {"stratum": str(k), "N_h": int(v)}
            for k, v in strata.items()
        ]
    normalized: list[dict[str, Any]] = []
    for item in strata:
        stratum = str(item.get("stratum") or item.get("code") or "")
        pop = int(item.get("N_h") if "N_h" in item else item.get("total", 0))
        rec = dict(item)
        rec["stratum"] = stratum
        rec["N_h"] = pop
        normalized.append(rec)
    return normalized


def compute_stratified_quota(
    strata: dict[str, int] | list[dict[str, Any]],
    n_target: int = 6000,
    min_per_stratum: int = 5,
) -> list[dict[str, Any]]:
    """Compute stratified proportional quota allocation with minimum per stratum.

    For each stratum h with population N_h:
      - If N_h <= 0: n_h = 0, sample_weight = 0.0
      - Else: n_h = min(N_h, max(min_per_stratum, round(n_target * N_h / N_total)))
              sample_weight = N_h / n_h
    """
    if n_target < 0:
        raise ValueError(f"n_target must be >= 0, got {n_target}")
    if min_per_stratum < 1:
        raise ValueError(f"min_per_stratum must be >= 1, got {min_per_stratum}")

    items = _normalize_strata_input(strata)
    n_total = sum(max(0, item["N_h"]) for item in items)

    plan: list[dict[str, Any]] = []
    for item in items:
        pop = max(0, int(item["N_h"]))
        if pop == 0 or n_total == 0 or n_target == 0:
            n_h = 0
            weight = 0.0
        else:
            prop = round(n_target * pop / n_total)
            n_h = min(pop, max(min_per_stratum, prop))
            weight = pop / n_h

        rec = dict(item)
        rec["N_h"] = pop
        rec["n_h"] = n_h
        rec["sample_weight"] = weight
        rec["expected_weight_sum"] = n_h * weight if n_h > 0 else 0.0
        plan.append(rec)
    return plan


def select_stratified_sample(
    discovered_by_stratum: dict[str, list[str]],
    quota_plan: list[dict[str, Any]],
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Select stratified sample of job IDs according to quota_plan and attach weights.

    If a stratum has fewer discovered IDs than n_h, takes all available IDs and
    recomputes sample_weight = N_h / actual_n_h so weight conservation holds.
    """
    rng = random.Random(seed)
    sampled_rows: list[dict[str, Any]] = []
    for entry in quota_plan:
        stratum = entry["stratum"]
        pop = int(entry["N_h"])
        target_n = int(entry["n_h"])
        available = list(dict.fromkeys(discovered_by_stratum.get(stratum, [])))
        if pop == 0 or target_n == 0 or not available:
            continue

        if len(available) <= target_n:
            chosen = available
        else:
            chosen = rng.sample(available, target_n)

        actual_n = len(chosen)
        weight = pop / actual_n
        for job_id in chosen:
            sampled_rows.append(
                {
                    "source_job_id": job_id,
                    "sample_stratum": stratum,
                    "sample_weight": weight,
                    "N_h": pop,
                    "n_h": actual_n,
                }
            )
    return sampled_rows


def verify_weight_conservation(
    quota_plan: list[dict[str, Any]],
    sampled_rows: list[dict[str, Any]] | None = None,
    rel_tol: float = 1e-9,
    abs_tol: float = 1e-9,
) -> dict[str, Any]:
    """Verify sum(sample_weight for row in stratum_h) == N_h across every stratum."""
    plan_by_stratum = {row["stratum"]: row for row in quota_plan}
    failures: list[dict[str, Any]] = []

    if sampled_rows is None:
        # Verify theoretical conservation on the plan itself
        for stratum, row in plan_by_stratum.items():
            pop = float(row["N_h"])
            n_h = int(row["n_h"])
            w_sum = n_h * float(row["sample_weight"]) if n_h > 0 else 0.0
            if not math.isclose(w_sum, pop, rel_tol=rel_tol, abs_tol=abs_tol):
                failures.append(
                    {"stratum": stratum, "N_h": pop, "weight_sum": w_sum}
                )
        return {
            "passed": len(failures) == 0,
            "n_strata": len(plan_by_stratum),
            "failures": failures,
        }

    sums_by_stratum: dict[str, float] = {}
    counts_by_stratum: dict[str, int] = {}
    for srow in sampled_rows:
        st = str(srow.get("sample_stratum") or srow.get("stratum"))
        sums_by_stratum[st] = sums_by_stratum.get(st, 0.0) + float(srow["sample_weight"])
        counts_by_stratum[st] = counts_by_stratum.get(st, 0) + 1

    for stratum, row in plan_by_stratum.items():
        pop = float(row["N_h"])
        if pop == 0 or stratum not in sums_by_stratum:
            continue
        w_sum = sums_by_stratum[stratum]
        if not math.isclose(w_sum, pop, rel_tol=rel_tol, abs_tol=abs_tol):
            failures.append(
                {
                    "stratum": stratum,
                    "N_h": pop,
                    "n_sampled": counts_by_stratum.get(stratum, 0),
                    "weight_sum": w_sum,
                }
            )

    return {
        "passed": len(failures) == 0,
        "n_strata_checked": len(sums_by_stratum),
        "failures": failures,
    }


def format_quota_summary(plan: list[dict[str, Any]]) -> str:
    """Format a human-readable quota table for CLI display."""
    total_pop = sum(r["N_h"] for r in plan)
    total_sample = sum(r["n_h"] for r in plan)
    total_w = sum(r["expected_weight_sum"] for r in plan)
    lines = [
        f"Stratified Quota Plan: {len(plan)} strata | N_total={total_pop:,} | planned_sample={total_sample:,} | sum(weights)={total_w:,.2f}",
        f"{'stratum':12s} {'province':22s} {'N_h':>8s} {'n_h':>6s} {'weight':>10s} {'sum(w)':>10s}",
        "-" * 74,
    ]
    for r in plan:
        prov = str(r.get("province") or "")[:20]
        lines.append(
            f"{r['stratum']:12s} {prov:22s} {r['N_h']:8d} {r['n_h']:6d} {r['sample_weight']:10.4f} {r['expected_weight_sum']:10.2f}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compute stratified scraping quota plan.")
    parser.add_argument(
        "--csv",
        default="spike/raw/jobthai/by_province/province_totals.csv",
        help="Path to province_totals.csv",
    )
    parser.add_argument("--target", type=int, default=6000, help="Target total sample size")
    parser.add_argument("--min-per-stratum", type=int, default=5, help="Minimum floor per stratum")
    args = parser.parse_args(argv)

    strata = load_province_totals(args.csv)
    plan = compute_stratified_quota(
        strata, n_target=args.target, min_per_stratum=args.min_per_stratum
    )
    check = verify_weight_conservation(plan)
    print(format_quota_summary(plan))
    print(f"\nConservation check passed: {check['passed']}")
    return 0 if check["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
