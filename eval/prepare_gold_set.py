"""Create stratified gold-set labeling template without saving raw posting text (T2.7, D4, D16).

Usage:
  py -I -X utf8 eval/prepare_gold_set.py \
    --input data/processed/clean_postings.csv \
    --out eval/skills_gold_template.csv \
    --n 200 --overlap 50 --seed 42
"""
from __future__ import annotations

import argparse
import csv
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
DEFAULT_INPUT = REPO_ROOT / "data" / "processed" / "clean_postings.csv"
DEFAULT_OUT = REPO_ROOT / "eval" / "skills_gold_template.csv"

TEMPLATE_COLUMNS: list[str] = [
    "source_job_id",
    "source_url",
    "title_short",
    "occupational_category",
    "occupation_cluster",
    "province_th",
    "annotator_group",
    "gold_skills_a",
    "gold_skills_b",
    "out_of_taxonomy_skills",
    "notes",
]


def stratified_sample_rows(
    rows: list[dict[str, str]],
    target_n: int = 200,
    overlap_n: int = 50,
    seed: int = 42,
) -> list[dict[str, str]]:
    """Select stratified sample by occupation_cluster and assign annotator_group."""
    if not rows:
        return []

    rng = random.Random(seed)
    n_avail = len(rows)
    n_pick = min(target_n, n_avail)
    eff_overlap = min(overlap_n, max(1, round(n_pick * overlap_n / max(1, target_n)))) if n_pick < target_n else min(overlap_n, n_pick)

    by_occ: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_occ[row.get("occupation_cluster") or "Other / General"].append(row)

    for occ in by_occ:
        by_occ[occ].sort(key=lambda r: str(r.get("source_job_id") or ""))
        rng.shuffle(by_occ[occ])

    picked: list[dict[str, str]] = []
    if n_pick == n_avail:
        picked = [r for occ in sorted(by_occ) for r in by_occ[occ]]
    else:
        # Proportional stratified allocation with floor >= 1 per cluster
        allocs: dict[str, int] = {}
        for occ, grp in sorted(by_occ.items()):
            allocs[occ] = min(len(grp), max(1, math.floor(n_pick * len(grp) / n_avail)))
        while sum(allocs.values()) < n_pick:
            rem = [(len(by_occ[occ]) - allocs[occ], occ) for occ in sorted(by_occ) if allocs[occ] < len(by_occ[occ])]
            if not rem:
                break
            rem.sort(reverse=True)
            allocs[rem[0][1]] += 1
        while sum(allocs.values()) > n_pick:
            reducible = [(allocs[occ], occ) for occ in sorted(allocs) if allocs[occ] > 1]
            if not reducible:
                break
            reducible.sort(reverse=True)
            allocs[reducible[0][1]] -= 1
        for occ in sorted(allocs):
            picked.extend(by_occ[occ][: allocs[occ]])

    rng.shuffle(picked)
    rem_after_overlap = len(picked) - eff_overlap
    n_a = rem_after_overlap // 2

    out_rows: list[dict[str, str]] = []
    for idx, r in enumerate(picked):
        if idx < eff_overlap:
            grp = "overlap_50"
        elif idx < eff_overlap + n_a:
            grp = "annotator_a"
        else:
            grp = "annotator_b"

        out_rows.append(
            {
                "source_job_id": str(r.get("source_job_id") or ""),
                "source_url": str(r.get("source_url") or ""),
                "title_short": str(r.get("title_short") or "")[:120],
                "occupational_category": str(r.get("occupational_category") or ""),
                "occupation_cluster": str(r.get("occupation_cluster") or ""),
                "province_th": str(r.get("province_th") or ""),
                "annotator_group": grp,
                "gold_skills_a": "",
                "gold_skills_b": "",
                "out_of_taxonomy_skills": "",
                "notes": "",
            }
        )
    return out_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare stratified gold-set labeling template (no raw description).")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Path to clean_postings.csv")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output template CSV path")
    parser.add_argument("--n", type=int, default=200, help="Target sample size (default: 200)")
    parser.add_argument("--overlap", type=int, default=50, help="Inter-annotator overlap size (default: 50)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    template_rows = stratified_sample_rows(rows, target_n=args.n, overlap_n=args.overlap, seed=args.seed)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=TEMPLATE_COLUMNS)
        writer.writeheader()
        writer.writerows(template_rows)

    print(f"Wrote {len(template_rows)} stratified template rows to {out_path} (NO description/qualifications stored)")


if __name__ == "__main__":
    main()
