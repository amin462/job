"""Unit tests for stratified province x jobtype weighting and seen dates (T1.7, T3.4)."""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline.etl.load_dw import (  # noqa: E402
    compute_weights_and_seen_dates,
    load_strata_population,
)
from pipeline.etl.validate import run_dq_checks  # noqa: E402


def _write_strata_csv(path: Path, rows: list[dict[str, object]]) -> Path:
    fields = [
        "stratum",
        "province_code",
        "province",
        "jobtype_code",
        "jobtype",
        "N_h",
        "scanned_date",
        "n_seen",
        "n_fetched",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _write_province_csv(path: Path, rows: list[dict[str, object]]) -> Path:
    fields = ["code", "province", "total", "scanned_date"]
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_compute_weights_uses_listing_seen_cell_stratum_and_conserves_nh(tmp_path: Path) -> None:
    strata_csv = _write_strata_csv(
        tmp_path / "jobthai_strata.csv",
        [
            {
                "stratum": "p=24|c=9",
                "province_code": "24",
                "province": "นนทบุรี",
                "jobtype_code": "9",
                "jobtype": "งานธุรการ",
                "N_h": 158,
                "scanned_date": "2026-11-21",
                "n_seen": 20,
                "n_fetched": 3,
            },
            {
                "stratum": "p=57|c=4",
                "province_code": "57",
                "province": "สงขลา",
                "jobtype_code": "4",
                "jobtype": "งานขาย",
                "N_h": 137,
                "scanned_date": "2026-11-21",
                "n_seen": 20,
                "n_fetched": 2,
            },
        ],
    )
    prov_csv = _write_province_csv(
        tmp_path / "jobthai_province_totals.csv",
        [
            {"code": "24", "province": "นนทบุรี", "total": 1903, "scanned_date": "2026-11-21"},
            {"code": "57", "province": "สงขลา", "total": 620, "scanned_date": "2026-11-21"},
            {"code": "19", "province": "นครปฐม", "total": 1062, "scanned_date": "2026-11-21"},
        ],
    )

    strata_pop = load_strata_population(strata_csv)
    assert strata_pop == {"p=24|c=9": 158, "p=57|c=4": 137}

    postings = [
        # 3 postings in cell p=24|c=9 -> N_h=158, n_h=3 -> weight = 158/3
        {"source": "jobthai", "source_job_id": "101", "province_code": "24", "province_th": "นนทบุรี", "date_posted": "2026-11-18"},
        {"source": "jobthai", "source_job_id": "102", "province_code": "24", "province_th": "นนทบุรี", "date_posted": "2026-11-18"},
        {"source": "jobthai", "source_job_id": "103", "province_code": "24", "province_th": "นนทบุรี", "date_posted": "2026-11-18"},
        # 2 postings in cell p=57|c=4 -> N_h=137, n_h=2 -> weight = 137/2 = 68.5
        {"source": "jobthai", "source_job_id": "201", "province_code": "57", "province_th": "สงขลา", "date_posted": "2026-11-19"},
        {"source": "jobthai", "source_job_id": "202", "province_code": "57", "province_th": "สงขลา", "date_posted": "2026-11-19"},
        # 4 postings with province-only stratum (no |c=) -> N_h from jobthai_province_totals.csv = 1062 -> weight = 265.5
        {"source": "jobthai", "source_job_id": "301", "province_code": "19", "province_th": "นครปฐม", "date_posted": "2026-11-20"},
        {"source": "jobthai", "source_job_id": "302", "province_code": "19", "province_th": "นครปฐม", "date_posted": "2026-11-20"},
        {"source": "jobthai", "source_job_id": "303", "province_code": "19", "province_th": "นครปฐม", "date_posted": "2026-11-20"},
        {"source": "jobthai", "source_job_id": "304", "province_code": "19", "province_th": "นครปฐม", "date_posted": "2026-11-20"},
        # 1 posting whose cell p=18|c=1 is not yet in jobthai_strata.csv -> safe fallback weight = 1.0
        {"source": "jobthai", "source_job_id": "401", "province_code": "18", "province_th": "นครนายก", "date_posted": "2026-11-20"},
    ]

    listing_seen_history = {
        ("jobthai", "101"): ("2026-11-18", "2026-11-21", "p=24|c=9"),
        ("jobthai", "102"): ("2026-11-18", "2026-11-21", "p=24|c=9"),
        ("jobthai", "103"): ("2026-11-19", "2026-11-21", "p=24|c=9"),
        ("jobthai", "201"): ("2026-11-19", "2026-11-21", "p=57|c=4"),
        ("jobthai", "202"): ("2026-11-19", "2026-11-20", "p=57|c=4"),
        ("jobthai", "301"): ("2026-11-20", "2026-11-21", "p=19"),
        ("jobthai", "302"): ("2026-11-20", "2026-11-21", "p=19"),
        ("jobthai", "303"): ("2026-11-20", "2026-11-21", "p=19"),
        ("jobthai", "304"): ("2026-11-20", "2026-11-21", "p=19"),
        ("jobthai", "401"): ("2026-11-20", "2026-11-21", "p=18|c=1"),
    }

    ref_pop = compute_weights_and_seen_dates(
        postings,
        province_totals_csv=prov_csv,
        listing_seen_history=listing_seen_history,
        strata_csv=strata_csv,
    )

    assert ref_pop == {"p=24|c=9": 158.0, "p=57|c=4": 137.0, "p=19": 1062.0}
    assert postings[0]["sample_stratum"] == "p=24|c=9"
    assert postings[0]["first_seen_date_key"] == 20261118
    assert postings[0]["last_seen_date_key"] == 20261121
    assert postings[5]["sample_stratum"] == "p=19"
    assert postings[9]["sample_stratum"] == "p=18|c=1"
    assert postings[9]["sample_weight"] == 1.0

    # Verify sum(sample_weight) per stratum == N_h
    weight_sums: dict[str, float] = {}
    for p in postings:
        st = p["sample_stratum"]
        weight_sums[st] = weight_sums.get(st, 0.0) + p["sample_weight"]

    assert weight_sums["p=24|c=9"] == pytest.approx(158.0, rel=1e-6, abs=1e-4)
    assert weight_sums["p=57|c=4"] == pytest.approx(137.0, rel=1e-6, abs=1e-4)
    assert weight_sums["p=19"] == pytest.approx(1062.0, rel=1e-6, abs=1e-4)

    # Verify DQ sampling check passes with these weights
    for p in postings:
        p.update(
            {
                "title_short": "Test Role",
                "occupational_category": "งานขาย",
                "company_name_norm": "demo_co",
                "has_salary": True,
                "salary_min": 20000.0,
                "salary_max": 25000.0,
                "salary_mid": 22500.0,
                "occupation_mapped": True,
                "occupation_cluster": "Sales & Business Development",
                "n_skills": 1,
                "content_hash": f"hash_{p['source_job_id']}",
            }
        )
    dq = run_dq_checks(postings, stratum_population=ref_pop)
    sampling_check = next(d for d in dq if d["dimension"] == "Sampling")
    assert sampling_check["pass"] is True
