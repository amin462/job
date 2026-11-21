"""Evaluate rule-based skill extraction against human-labeled gold set (T2.7, D16).

Computes:
- Micro Precision, Recall (strictly within taxonomy), and F1 overall
- Per skill_group Precision, Recall, F1, and support
- Out-of-taxonomy (OOV) rate from `out_of_taxonomy_skills`
- Inter-annotator Cohen's kappa across overlapping postings
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
DEFAULT_SKILLS_CSV = REPO_ROOT / "taxonomy" / "skills.csv"


def _parse_skill_pipe(raw: str | None) -> set[str]:
    if not raw:
        return set()
    return {s.strip() for s in str(raw).split("|") if s.strip()}


def load_skill_groups(skills_csv: Path | str = DEFAULT_SKILLS_CSV) -> dict[str, str]:
    """Return `{skill_canonical: skill_group}` lookup."""
    groups: dict[str, str] = {}
    with open(skills_csv, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            groups[row["skill_canonical"].strip()] = row["skill_group"].strip()
    return groups


def compute_cohens_kappa(
    overlap_rows: list[dict[str, str]],
    canonical_skills: set[str] | list[str] | None = None,
) -> float:
    """Compute multi-label binary Cohen's kappa across overlapping postings of 2 annotators."""
    if not overlap_rows:
        return 0.0

    universe = sorted(set(canonical_skills or ()))
    if not universe:
        seen: set[str] = set()
        for r in overlap_rows:
            seen |= _parse_skill_pipe(r.get("gold_skills_a"))
            seen |= _parse_skill_pipe(r.get("gold_skills_b"))
        universe = sorted(seen)
    if not universe:
        return 1.0

    n_11 = n_10 = n_01 = n_00 = 0
    for r in overlap_rows:
        set_a = _parse_skill_pipe(r.get("gold_skills_a"))
        set_b = _parse_skill_pipe(r.get("gold_skills_b"))
        for sk in universe:
            in_a = sk in set_a
            in_b = sk in set_b
            if in_a and in_b:
                n_11 += 1
            elif in_a and not in_b:
                n_10 += 1
            elif not in_a and in_b:
                n_01 += 1
            else:
                n_00 += 1

    total = n_11 + n_10 + n_01 + n_00
    if total == 0:
        return 0.0
    p_o = (n_11 + n_00) / total
    p_yes_a = (n_11 + n_10) / total
    p_yes_b = (n_11 + n_01) / total
    p_no_a = (n_01 + n_00) / total
    p_no_b = (n_10 + n_00) / total
    p_e = (p_yes_a * p_yes_b) + (p_no_a * p_no_b)
    if abs(1.0 - p_e) < 1e-12:
        return 1.0 if abs(p_o - 1.0) < 1e-12 else 0.0
    return round((p_o - p_e) / (1.0 - p_e), 4)


def _prf(tp: int, fp: int, fn: int) -> dict[str, Any]:
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
        "support": tp + fn,
    }


def evaluate_predictions(
    gold_rows: list[dict[str, str]],
    pred_by_id: dict[str, set[str] | str],
    skills_csv: Path | str = DEFAULT_SKILLS_CSV,
) -> dict[str, Any]:
    """Evaluate predictions against gold rows; recall is counted strictly within taxonomy."""
    skill_groups = load_skill_groups(skills_csv)
    in_tax_vocab = set(skill_groups.keys())

    overall_tp = overall_fp = overall_fn = 0
    oov_mentions = 0
    total_gold_mentions = 0
    postings_with_oov = 0

    group_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    overlap_rows: list[dict[str, str]] = []

    for row in gold_rows:
        jid = str(row.get("source_job_id") or "")
        sa = _parse_skill_pipe(row.get("gold_skills_a"))
        sb = _parse_skill_pipe(row.get("gold_skills_b"))
        if sa and sb:
            overlap_rows.append(row)

        # Prefer adjudicated `gold_skills`, otherwise combine `gold_skills_a` / `gold_skills_b`
        if row.get("gold_skills"):
            gold_raw = _parse_skill_pipe(row.get("gold_skills"))
        else:
            gold_raw = (sa | sb) if (sa and sb) else (sa or sb)

        oov_set = _parse_skill_pipe(row.get("out_of_taxonomy_skills")) | (gold_raw - in_tax_vocab)
        gold_in_tax = gold_raw & in_tax_vocab
        total_gold_mentions += len(gold_in_tax) + len(oov_set)
        oov_mentions += len(oov_set)
        if oov_set:
            postings_with_oov += 1

        raw_pred = pred_by_id.get(jid, set())
        pred_set = _parse_skill_pipe(raw_pred) if isinstance(raw_pred, str) else set(raw_pred)
        pred_in_tax = pred_set & in_tax_vocab

        tp_set = gold_in_tax & pred_in_tax
        fp_set = pred_in_tax - gold_in_tax
        fn_set = gold_in_tax - pred_in_tax

        overall_tp += len(tp_set)
        overall_fp += len(fp_set)
        overall_fn += len(fn_set)

        for sk in tp_set:
            group_counts[skill_groups[sk]]["tp"] += 1
        for sk in fp_set:
            group_counts[skill_groups[sk]]["fp"] += 1
        for sk in fn_set:
            group_counts[skill_groups[sk]]["fn"] += 1

    overall = _prf(overall_tp, overall_fp, overall_fn)
    per_group = {grp: _prf(c["tp"], c["fp"], c["fn"]) for grp, c in sorted(group_counts.items())}
    oov_rate = round(oov_mentions / total_gold_mentions, 4) if total_gold_mentions > 0 else 0.0
    kappa = compute_cohens_kappa(overlap_rows, in_tax_vocab) if overlap_rows else None

    return {
        "n_postings": len(gold_rows),
        "n_overlap": len(overlap_rows),
        "overall": overall,
        "per_group": per_group,
        "oov_mentions": oov_mentions,
        "total_gold_mentions": total_gold_mentions,
        "postings_with_oov": postings_with_oov,
        "oov_rate": oov_rate,
        "cohens_kappa": kappa,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate skill extractor against gold CSV.")
    parser.add_argument("--gold", required=True, help="Path to human-labeled gold CSV")
    parser.add_argument("--pred", required=True, help="Path to clean_postings.csv containing predicted `skills`")
    parser.add_argument("--skills-csv", default=str(DEFAULT_SKILLS_CSV), help="Path to taxonomy/skills.csv")
    args = parser.parse_args()

    with open(args.gold, encoding="utf-8-sig") as f:
        gold_rows = list(csv.DictReader(f))
    with open(args.pred, encoding="utf-8-sig") as f:
        pred_by_id = {row["source_job_id"]: row.get("skills", "") for row in csv.DictReader(f)}

    report = evaluate_predictions(gold_rows, pred_by_id, skills_csv=args.skills_csv)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
