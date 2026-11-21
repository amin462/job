"""Model export, mart precomputation, atomic seed merge, and ML report generation (T4.4–T4.7).

Usage:
  py -I -X utf8 -m pipeline.ml.export_model \
    --input data/processed/clean_postings.csv \
    --models-dir models \
    --out-dir data/processed \
    --report docs/ml-report.md
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

import joblib
import pandas as pd

from pipeline.ml.benchmark import BenchmarkResult, run_benchmark
from pipeline.ml.champion import ChampionResult, select_and_fit_champion
from pipeline.ml.features import (
    DEFAULT_PROVINCE_TO_REGION,
    FeatureDataset,
    build_feature_matrix,
    parse_skills_cell,
    predict_salary_records,
    validate_feature_spec,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

FALLBACK_EXPERIENCE_BANDS: tuple[str, ...] = (
    "ไม่ระบุ/ไม่จำเป็น",
    "0 ปี / จบใหม่",
    "1-2 ปี",
    "3-5 ปี",
    "5+ ปี",
)
FALLBACK_EDUCATION_LEVELS: tuple[str, ...] = (
    "ไม่ระบุ",
    "ม.3/ม.6",
    "ปวช./ปวส.",
    "ปริญญาตรี",
    "ปริญญาโท+",
)
FALLBACK_HUB_PROVINCES: tuple[tuple[str, str], ...] = (
    ("กรุงเทพมหานคร", "กลาง"),
    ("นนทบุรี", "กลาง"),
    ("ชลบุรี", "ตะวันออก"),
    ("เชียงใหม่", "เหนือ"),
    ("ขอนแก่น", "อีสาน"),
    ("สงขลา", "ใต้"),
    ("ภูเก็ต", "ใต้"),
    ("ราชบุรี", "ตะวันตก"),
)
FALLBACK_REGIONS: tuple[str, ...] = ("กลาง", "ใต้", "อีสาน", "เหนือ", "ตะวันออก", "ตะวันตก")


def _load_all_occupation_clusters(occupations_csv: Path | str | None = None) -> list[str]:
    path = Path(occupations_csv) if occupations_csv else (REPO_ROOT / "taxonomy" / "occupations.csv")
    clusters: list[str] = []
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                occ = (row.get("occupation_cluster") or "").strip()
                if occ and occ not in clusters:
                    clusters.append(occ)
    return clusters


def _top_skills_by_occupation(postings_df: pd.DataFrame, max_skills: int = 3) -> dict[str, list[str]]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    if "occupation_cluster" in postings_df.columns and "skills" in postings_df.columns:
        for occ, sk_val in zip(postings_df["occupation_cluster"], postings_df["skills"]):
            occ_str = str(occ or "").strip()
            if not occ_str:
                continue
            for sk in parse_skills_cell(sk_val):
                counts[occ_str][sk] += 1
    return {
        occ: [sk for sk, _ in cnt.most_common(max_skills)]
        for occ, cnt in counts.items()
    }


def build_salary_prediction_grid(
    champion: ChampionResult,
    feature_spec: Mapping[str, Any],
    postings_df: pd.DataFrame,
    occupations_csv: Path | str | None = None,
) -> list[dict[str, Any]]:
    """Precompute < 1,000 representative Champion predictions for mart.salary_prediction fallback."""
    occ_clusters = _load_all_occupation_clusters(occupations_csv)
    for occ in feature_spec.get("known_categories", {}).get("occupation_cluster", []):
        if occ not in occ_clusters:
            occ_clusters.append(occ)

    top_skills_occ = _top_skills_by_occupation(postings_df, max_skills=3)
    occ_support = feature_spec.get("occupation_support_counts") or {}

    grid_records: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str, str, str, str, str]] = set()

    def _add_point(occ: str, prov: str, reg: str, exp: str, edu: str) -> None:
        emp = "FULL_TIME"
        bundle = "typical"
        key = (occ, prov, exp, edu, emp, bundle)
        if key in seen_keys:
            return
        seen_keys.add(key)
        grid_records.append(
            {
                "occupation_cluster": occ,
                "province_th": prov,
                "region": reg,
                "experience_band": exp,
                "education_level": edu,
                "employment_type": emp,
                "industry": "อื่นๆ",
                "skills": top_skills_occ.get(occ, []),
                "skill_bundle": bundle,
            }
        )

    for occ in occ_clusters:
        # 1. National baseline across all experience bands (edu = ไม่ระบุ)
        for exp in FALLBACK_EXPERIENCE_BANDS:
            _add_point(occ, "ทั้งประเทศ", "ทั้งประเทศ", exp, "ไม่ระบุ")
        # 2. National key experience x education grid
        for exp in ("0 ปี / จบใหม่", "1-2 ปี", "3-5 ปี"):
            for edu in ("ม.3/ม.6", "ปวช./ปวส.", "ปริญญาตรี", "ปริญญาโท+"):
                _add_point(occ, "ทั้งประเทศ", "ทั้งประเทศ", exp, edu)
        # 3. Regional aggregate defaults
        for reg in FALLBACK_REGIONS:
            _add_point(occ, "ทั้งหมดในภาค", reg, "ไม่ระบุ/ไม่จำเป็น", "ไม่ระบุ")
        # 4. Major hub provinces across all 6 regions
        for prov, reg in FALLBACK_HUB_PROVINCES:
            for exp in ("ไม่ระบุ/ไม่จำเป็น", "1-2 ปี"):
                _add_point(occ, prov, reg, exp, "ไม่ระบุ")

    preds = predict_salary_records(champion.champion_estimator, feature_spec, grid_records)
    mae_cv = round(float(champion.champion_cv_metrics["mae"]), 2)
    mape_cv = round(float(champion.champion_cv_metrics["mape"]), 2)

    out_rows: list[dict[str, Any]] = []
    for idx, (rec, pred) in enumerate(zip(grid_records, preds), start=1):
        out_rows.append(
            {
                "prediction_id": idx,
                "model_name": champion.champion_name,
                "occupation_cluster": rec["occupation_cluster"],
                "province_th": rec["province_th"],
                "region": rec["region"],
                "experience_band": rec["experience_band"],
                "education_level": rec["education_level"],
                "employment_type": rec["employment_type"],
                "skill_bundle": rec["skill_bundle"],
                "pred_p25": int(round(pred["p25"])),
                "pred_p50": int(round(pred["p50"])),
                "pred_p75": int(round(pred["p75"])),
                "mae_cv": mae_cv,
                "mape_cv": mape_cv,
                "n_train_support": int(occ_support.get(rec["occupation_cluster"], 0)),
            }
        )
    return out_rows


def merge_ml_into_seed_marts(ml_marts: Mapping[str, Any], seed_marts_path: Path | str) -> Path:
    """Atomically merge ML mart keys into seed_marts.json without disturbing ETL mart keys."""
    target = Path(seed_marts_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        existing = json.loads(target.read_text(encoding="utf-8"))
    else:
        existing = {}

    for key in ("ml_leaderboard", "ml_feature_importance", "salary_prediction"):
        if key in ml_marts:
            existing[key] = ml_marts[key]

    fd, tmp_name = tempfile.mkstemp(
        prefix=".seed_marts_",
        suffix=".tmp.json",
        dir=str(target.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        os.replace(tmp_name, target)
    except Exception:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
        raise
    return target


def _load_dotenv(env_path: Path | None = None) -> None:
    """Load simple KEY=VALUE lines from .env without overriding existing env vars."""
    path = env_path or (REPO_ROOT / ".env")
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key, val = s.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, val)


def upsert_ml_to_postgres(
    database_url: str,
    dataset_version: str,
    n_rows: int,
    ml_marts: Mapping[str, Any],
) -> dict[str, int]:
    """Persist experiment, leaderboard results, feature importance & fallback predictions to Postgres.

    Idempotent per `(task, dataset_version)`: replaces any previous experiment row for the same
    dataset version (cascading `ml.model_result` and `ml.feature_importance`) and uses batch
    `unnest(...)` writes for low roundtrip latency over pooled connections.
    """
    import psycopg

    counts = {"experiment_id": 0, "model_results": 0, "feature_importance": 0, "salary_prediction": 0}
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                delete from ml.experiment
                where task = 'salary_regression' and dataset_version = %s
                """,
                (dataset_version,),
            )
            cur.execute(
                """
                insert into ml.experiment (task, dataset_version, n_rows)
                values ('salary_regression', %s, %s)
                returning experiment_id
                """,
                (dataset_version, int(n_rows)),
            )
            exp_id = int(cur.fetchone()[0])
            counts["experiment_id"] = exp_id

            lb_rows = list(ml_marts.get("ml_leaderboard") or [])
            if lb_rows:
                cur.execute(
                    """
                    insert into ml.model_result (
                      experiment_id, model_name, fold, r2, rmse, mae, mape, fit_seconds, params, is_champion
                    )
                    select * from unnest(
                      %s::bigint[], %s::text[], %s::int[], %s::numeric[], %s::numeric[],
                      %s::numeric[], %s::numeric[], %s::numeric[], %s::jsonb[], %s::boolean[]
                    )
                    """,
                    (
                        [exp_id] * len(lb_rows),
                        [str(r["model_name"]) for r in lb_rows],
                        [int(r["fold"]) for r in lb_rows],
                        [float(r["r2"]) if r.get("r2") is not None else None for r in lb_rows],
                        [float(r["rmse"]) if r.get("rmse") is not None else None for r in lb_rows],
                        [float(r["mae"]) if r.get("mae") is not None else None for r in lb_rows],
                        [float(r["mape"]) if r.get("mape") is not None else None for r in lb_rows],
                        [float(r["fit_seconds"]) if r.get("fit_seconds") is not None else None for r in lb_rows],
                        [json.dumps(r.get("params") or {}, ensure_ascii=False) for r in lb_rows],
                        [bool(r["is_champion"]) for r in lb_rows],
                    ),
                )
                counts["model_results"] = len(lb_rows)

            fi_rows = list(ml_marts.get("ml_feature_importance") or [])
            if fi_rows:
                cur.execute(
                    """
                    insert into ml.feature_importance (experiment_id, model_name, feature, importance)
                    select * from unnest(%s::bigint[], %s::text[], %s::text[], %s::numeric[])
                    """,
                    (
                        [exp_id] * len(fi_rows),
                        [str(fi["model_name"]) for fi in fi_rows],
                        [str(fi["feature"]) for fi in fi_rows],
                        [float(fi["importance"]) for fi in fi_rows],
                    ),
                )
                counts["feature_importance"] = len(fi_rows)

            pred_rows = list(ml_marts.get("salary_prediction") or [])
            if pred_rows:
                cur.execute(
                    """
                    insert into mart.salary_prediction (
                      experiment_id, model_name, occupation_cluster, province_th, region,
                      experience_band, education_level, employment_type, skill_bundle,
                      pred_p25, pred_p50, pred_p75, mae_cv, mape_cv, n_train_support
                    )
                    select * from unnest(
                      %s::bigint[], %s::text[], %s::text[], %s::text[], %s::text[],
                      %s::text[], %s::text[], %s::text[], %s::text[],
                      %s::numeric[], %s::numeric[], %s::numeric[], %s::numeric[], %s::numeric[], %s::int[]
                    )
                    on conflict (occupation_cluster, province_th, experience_band, education_level, employment_type, skill_bundle)
                    do update set
                      experiment_id   = excluded.experiment_id,
                      model_name      = excluded.model_name,
                      region          = excluded.region,
                      pred_p25        = excluded.pred_p25,
                      pred_p50        = excluded.pred_p50,
                      pred_p75        = excluded.pred_p75,
                      mae_cv          = excluded.mae_cv,
                      mape_cv         = excluded.mape_cv,
                      n_train_support = excluded.n_train_support,
                      created_at      = now()
                    """,
                    (
                        [exp_id] * len(pred_rows),
                        [str(p["model_name"]) for p in pred_rows],
                        [str(p["occupation_cluster"]) for p in pred_rows],
                        [str(p["province_th"]) for p in pred_rows],
                        [str(p["region"]) for p in pred_rows],
                        [str(p["experience_band"]) for p in pred_rows],
                        [str(p["education_level"]) for p in pred_rows],
                        [str(p["employment_type"]) for p in pred_rows],
                        [str(p["skill_bundle"]) for p in pred_rows],
                        [float(p["pred_p25"]) for p in pred_rows],
                        [float(p["pred_p50"]) for p in pred_rows],
                        [float(p["pred_p75"]) for p in pred_rows],
                        [float(p["mae_cv"]) if p.get("mae_cv") is not None else None for p in pred_rows],
                        [float(p["mape_cv"]) if p.get("mape_cv") is not None else None for p in pred_rows],
                        [int(p["n_train_support"]) for p in pred_rows],
                    ),
                )
                counts["salary_prediction"] = len(pred_rows)
        conn.commit()
    return counts


def generate_ml_report_markdown(
    dataset: FeatureDataset,
    benchmark: BenchmarkResult,
    champion: ChampionResult,
    feature_spec: Mapping[str, Any],
) -> str:
    """Generate docs/ml-report.md covering T4.4 & T4.7 requirements."""
    summary_sorted = sorted(
        benchmark.summary_rows,
        key=lambda r: (float(r["rmse"]), float(r["mae"])),
    )
    fold_rows = [r for r in benchmark.rows if not r["is_summary"]]
    q = champion.residual_quantiles_log

    lines: list[str] = [
        "# รายงานการทดลองและประเมินผลโมเดล ML ประมาณเงินเดือน (ML Evaluation Report — T4.4 / T4.7)",
        "",
        (
            f"> **Dataset Version:** `{feature_spec.get('dataset_version')}` · "
            f"**จำนวนแถวมีเงินเดือนที่ใช้เทรน:** {dataset.feature_spec['n_rows']} จากทั้งหมด {dataset.feature_spec['n_total_postings']} ประกาศ · "
            f"**จำนวนบริษัท (Groups):** {dataset.feature_spec['n_companies']} บริษัท · "
            f"**Champion:** `{champion.champion_name}`"
        ),
        "",
        "## 1. การออกแบบการทดลองและความเป็นธรรมของโมเดล (Experimental Design & Fairness D6/D15)",
        "",
        "- **ตัวแปรเป้าหมาย (Target):** `log(salary_mid)` เฉพาะประกาศที่ `has_salary == True` และ `salary_mid ∈ [5,000, 500,000]` บาท/เดือน (รายงานผลกลับเป็นบาทด้วย `exp(pred)`)",
        "- **ตัวแปรต้น (Features):** "
        + ", ".join(f"`{col}`" for col in (feature_spec.get("categorical_features") or []))
        + ", "
        + ", ".join(f"`{col}`" for col in (feature_spec.get("numeric_features") or []))
        + ", และ multi-hot ทักษะยอดนิยม "
        + f"(Top {len(feature_spec.get('skill_feature_names') or [])} ทักษะ รวม {len(feature_spec.get('feature_columns') or [])} คอลัมน์)",
        "- **การป้องกันอคติ (Fairness Guard D6):** **ไม่ใช้** `gender`, `mentions_gender`, `age`, `mentions_age`, `company`, `company_name`, และ `company_name_norm` เป็น feature ของโมเดลโดยเด็ดขาด",
        f"- **การแบ่งข้อมูลแบบ Nested Cross-Validation (D15):** Outer CV ใช้ `GroupKFold(n_splits={benchmark.n_outer_splits})` แบ่งตาม `company_name_norm` (ทับซ้อนระหว่าง train/val = 0 บริษัทในทุก fold) · Inner Hyperparameter Tuning ใช้ `GroupKFold(n_splits={benchmark.n_inner_splits})` เฉพาะภายใน outer train fold (`<= {benchmark.n_tuning_trials}` trials/model/fold) ทำให้ outer validation fold ไม่รั่วไหลเข้าสู่การเลือก hyperparameter",
        "- **การเสิร์ฟในระบบจริง (D19):** ใช้เฉพาะ **Champion ตัวเดียว** (`"
        + champion.champion_name
        + "`) ผ่าน FastAPI `services/ml-api` พร้อมตาราง fallback `mart.salary_prediction`",
        "",
        "## 2. ตารางเปรียบเทียบผลโมเดล (Leaderboard: Mean ± SD across Outer Folds)",
        "",
        "| อันดับ | โมเดล | R² (Mean ± SD) | RMSE บาท (Mean ± SD) | MAE บาท (Mean ± SD) | MAPE % (Mean ± SD) | Avg Fit+Tune (s) | สถานะ |",
        "|---:|---|---:|---:|---:|---:|---:|---|",
    ]

    for rank_idx, row in enumerate(summary_sorted, start=1):
        tag = "**Champion**" if row["is_champion"] else ("Baseline" if row["model_name"] == "Baseline" else "Benchmark")
        lines.append(
            f"| {rank_idx} | `{row['model_name']}` | "
            f"{row['r2']:.4f} ± {row.get('r2_sd', 0.0):.4f} | "
            f"{row['rmse']:,.1f} ± {row.get('rmse_sd', 0.0):,.1f} | "
            f"{row['mae']:,.1f} ± {row.get('mae_sd', 0.0):,.1f} | "
            f"{row['mape']:.2f}% ± {row.get('mape_sd', 0.0):.2f}% | "
            f"{row['fit_seconds']:.3f} | {tag} |"
        )

    lines.extend(
        [
            "",
            f"- **ผลการเทียบกับ Baseline:** Champion `{champion.champion_name}` มี RMSE เฉลี่ย `{champion.champion_cv_metrics['rmse']:,.2f}` บาท เทียบกับ Baseline `{champion.baseline_rmse:,.2f}` บาท "
            + (
                f"(ลด RMSE ลง `{(1 - champion.champion_cv_metrics['rmse'] / champion.baseline_rmse) * 100:.1f}%` — **ดีกว่า Baseline**)"
                if champion.beats_baseline and champion.baseline_rmse > 0
                else "(หมายเหตุ: ข้อมูลชุดตัวอย่างมีขนาดเล็ก ควรประเมินซ้ำหลังเก็บครบ ≥ 5,000 ประกาศ)"
            ),
            f"- **ช่วงความไม่แน่นอนของค่าคาด (`p25–p75` จาก Out-of-Fold Log Residuals):** `q25_offset = {q['q25']:+.4f}`, `q75_offset = {q['q75']:+.4f}` (`p25 = exp(ŷ + q25)`, `p50 = exp(ŷ)`, `p75 = exp(ŷ + q75)`)",
            "",
            "## 3. เสถียรภาพราย Fold และยืนยันการไม่รั่วไหลข้ามบริษัท (Per-Fold Stability)",
            "",
            "| Fold | Train Rows (Companies) | Val Rows (Companies) | Company Overlap | Champion RMSE (THB) | Champion MAE (THB) | Champion MAPE (%) | Baseline RMSE (THB) |",
            "|---:|---|---|---:|---:|---:|---:|---:|",
        ]
    )

    champ_folds = {r["fold"]: r for r in fold_rows if r["model_name"] == champion.champion_name}
    base_folds = {r["fold"]: r for r in fold_rows if r["model_name"] == "Baseline"}
    for fa in benchmark.fold_audit:
        fidx = fa["fold"]
        cf = champ_folds.get(fidx, {})
        bf = base_folds.get(fidx, {})
        lines.append(
            f"| {fidx} | {fa['n_train']} ({fa['n_train_companies']}) | {fa['n_val']} ({fa['n_val_companies']}) | "
            f"{fa['company_overlap_count']} | {cf.get('rmse', 0.0):,.1f} | {cf.get('mae', 0.0):,.1f} | "
            f"{cf.get('mape', 0.0):.2f}% | {bf.get('rmse', 0.0):,.1f} |"
        )

    lines.extend(
        [
            "",
            "## 4. ความสำคัญของตัวแปร (Permutation Feature Importance — Top 15)",
            "",
            "| อันดับ | Feature | Importance (Δ R²) | Std |",
            "|---:|---|---:|---:|",
        ]
    )
    for idx, fi in enumerate(champion.feature_importance[:15], start=1):
        lines.append(f"| {idx} | `{fi['feature']}` | {fi['importance']:.4f} | {fi['importance_std']:.4f} |")

    lines.extend(
        [
            "",
            "## 5. การวิเคราะห์ความคลาดเคลื่อนตามกลุ่มอาชีพและภูมิภาค (Error Analysis — T4.7)",
            "",
            "### 5.1 รายกลุ่มอาชีพ (Occupation Cluster — Out-of-Fold)",
            "| กลุ่มอาชีพ | n | ค่าเฉลี่ยจริง (บาท) | ค่าเฉลี่ยคาด (บาท) | RMSE (บาท) | MAE (บาท) | MAPE (%) |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in champion.error_breakdown_occupation:
        lines.append(
            f"| {row['subgroup']} | {row['n_rows']} | {row['mean_actual_thb']:,.0f} | "
            f"{row['mean_pred_thb']:,.0f} | {row['rmse']:,.1f} | {row['mae']:,.1f} | {row['mape']:.2f}% |"
        )

    lines.extend(
        [
            "",
            "### 5.2 รายภูมิภาค (Region — Out-of-Fold)",
            "| ภูมิภาค | n | ค่าเฉลี่ยจริง (บาท) | ค่าเฉลี่ยคาด (บาท) | RMSE (บาท) | MAE (บาท) | MAPE (%) |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in champion.error_breakdown_region:
        lines.append(
            f"| {row['subgroup']} | {row['n_rows']} | {row['mean_actual_thb']:,.0f} | "
            f"{row['mean_pred_thb']:,.0f} | {row['rmse']:,.1f} | {row['mae']:,.1f} | {row['mape']:.2f}% |"
        )

    lines.extend(
        [
            "",
            "## 6. ข้อจำกัดและอคติในการเลือกตัวอย่าง (Limitations & Selection Bias)",
            "",
            "1. **Selection Bias ของประกาศที่เปิดเผยเงินเดือน:** โมเดลเทรนเฉพาะประกาศที่มีตัวเลขเงินเดือนชัดเจนเท่านั้น ส่วนตำแหน่งระดับสูงหรือเฉพาะทางมักระบุว่า *\"ตามโครงสร้างบริษัท / ตามตกลง\"* ซึ่งถูกตัดออกจากชุดเทรน ทำให้ค่าคาดการณ์อาจเอนเอียงไปทางระดับปฏิบัติการหรือระดับต้น-กลาง",
            "2. **เงินเดือนที่ประกาศ ≠ รายได้สุทธิจริง:** ตัวเลขเป้าหมาย `salary_mid` คำนวณจากค่ากึ่งกลางช่วงเงินเดือนฐาน (หรือขั้นต่ำกรณี *\"ขึ้นไป\"*) โดยไม่รวมค่าคอมมิชชั่น โบนัส หรือค่าล่วงเวลา",
            "3. **ความครอบคลุมของข้อมูลรายกลุ่มย่อย:** กลุ่มอาชีพหรือจังหวัดที่มีจำนวนตัวอย่างน้อย (`n < 5`) มีความแปรปรวนสูง ระบบจึงแจ้งเตือน `out_of_domain` / `low_support_warning` และแสดงค่าเป็นช่วง `p25–p75` พร้อมข้อความกำกับว่า *\"ประมาณการจากประกาศที่ระบุเงินเดือน ไม่ใช่เงินเดือนจริง\"*",
            "4. **การสุ่มแบบแบ่งชั้น vs การเทรน:** ตารางสถิติใน `mart.*` ถ่วงน้ำหนักด้วย `sample_weight` แต่โมเดล ML เทรนบนแถวประกาศจริงโดยไม่ถ่วงน้ำหนัก (PLAN §6) เพื่อสะท้อนความสัมพันธ์ระดับตำแหน่งงานจริง",
            "",
        ]
    )
    return "\n".join(lines)


def run_ml_pipeline(
    input_csv: Path | str = REPO_ROOT / "data" / "processed" / "clean_postings.csv",
    *,
    models_dir: Path | str = REPO_ROOT / "models",
    out_dir: Path | str = REPO_ROOT / "data" / "processed",
    report_path: Path | str = REPO_ROOT / "docs" / "ml-report.md",
    merge_seed: bool = False,
    database_url: str | None = None,
    top_k_skills: int = 40,
    min_skill_freq: int = 2,
    outer_splits: int = 5,
    inner_splits: int = 3,
    n_tuning_trials: int = 6,
    random_state: int = 42,
) -> dict[str, Any]:
    """Run full ML pipeline: features -> nested benchmark -> champion -> export artifacts & marts."""
    in_path = Path(input_csv)
    df = pd.read_csv(in_path)
    dataset = build_feature_matrix(
        df,
        top_k_skills=top_k_skills,
        min_skill_freq=min_skill_freq,
    )

    benchmark = run_benchmark(
        dataset,
        outer_splits=outer_splits,
        inner_splits=inner_splits,
        n_tuning_trials=n_tuning_trials,
        random_state=random_state,
    )
    champion = select_and_fit_champion(
        dataset,
        benchmark,
        inner_splits=inner_splits,
        n_tuning_trials=n_tuning_trials,
        random_state=random_state,
    )

    now_iso = dt.datetime.now(dt.timezone.utc).isoformat()
    csv_digest = hashlib.sha256(in_path.read_bytes()).hexdigest()[:8]
    dataset_version = f"clean_postings_n{dataset.feature_spec['n_rows']}_{csv_digest}"

    feature_spec = dict(dataset.feature_spec)
    feature_spec.update(
        {
            "dataset_version": dataset_version,
            "champion_model": champion.champion_name,
            "champion_params": champion.champion_params,
            "beats_baseline": champion.beats_baseline,
            "baseline_rmse": champion.baseline_rmse,
            "cv_metrics": champion.champion_cv_metrics,
            "residual_quantiles_log": champion.residual_quantiles_log,
            "trained_at": now_iso,
        }
    )
    validate_feature_spec(feature_spec)

    models_out = Path(models_dir)
    models_out.mkdir(parents=True, exist_ok=True)
    model_path = models_out / "salary_champion.joblib"
    spec_path = models_out / "feature_spec.json"
    joblib.dump(champion.champion_estimator, model_path, compress=3)
    spec_path.write_text(json.dumps(feature_spec, ensure_ascii=False, indent=2), encoding="utf-8")

    # Build ML mart payloads aligned with 004_marts_and_ml_grants.sql & apps/web/src/types/marts.ts
    exp_id = 1
    ml_leaderboard = [
        {
            "experiment_id": exp_id,
            "task": "salary_regression",
            "dataset_version": dataset_version,
            "n_rows": dataset.feature_spec["n_rows"],
            "created_at": now_iso,
            **row,
        }
        for row in benchmark.rows
    ]
    ml_feature_importance = [
        {
            "experiment_id": exp_id,
            "task": "salary_regression",
            "dataset_version": dataset_version,
            "model_name": champion.champion_name,
            "feature": fi["feature"],
            "importance": fi["importance"],
            "importance_std": fi["importance_std"],
        }
        for fi in champion.feature_importance
    ]
    salary_prediction = build_salary_prediction_grid(
        champion=champion,
        feature_spec=feature_spec,
        postings_df=dataset.postings_used,
    )

    ml_marts = {
        "dataset_version": dataset_version,
        "trained_at": now_iso,
        "champion_model": champion.champion_name,
        "ml_leaderboard": ml_leaderboard,
        "ml_feature_importance": ml_feature_importance,
        "salary_prediction": salary_prediction,
    }

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    ml_marts_path = out_path / "ml_marts.json"
    ml_marts_path.write_text(json.dumps(ml_marts, ensure_ascii=False, indent=2), encoding="utf-8")

    seed_marts_path = out_path / "seed_marts.json"
    if merge_seed:
        merge_ml_into_seed_marts(ml_marts, seed_marts_path)

    rep_path = Path(report_path)
    rep_path.parent.mkdir(parents=True, exist_ok=True)
    rep_md = generate_ml_report_markdown(dataset, benchmark, champion, feature_spec)
    rep_path.write_text(rep_md, encoding="utf-8")

    db_counts = None
    if database_url:
        db_counts = upsert_ml_to_postgres(
            database_url=database_url,
            dataset_version=dataset_version,
            n_rows=dataset.feature_spec["n_rows"],
            ml_marts=ml_marts,
        )

    return {
        "dataset_version": dataset_version,
        "n_rows": dataset.feature_spec["n_rows"],
        "n_companies": dataset.feature_spec["n_companies"],
        "champion_model": champion.champion_name,
        "beats_baseline": champion.beats_baseline,
        "cv_metrics": champion.champion_cv_metrics,
        "model_path": str(model_path),
        "spec_path": str(spec_path),
        "ml_marts_path": str(ml_marts_path),
        "seed_marts_merged": bool(merge_seed),
        "report_path": str(rep_path),
        "n_salary_predictions": len(salary_prediction),
        "db_counts": db_counts,
    }


def main(argv: list[str] | None = None) -> int:
    _load_dotenv()
    parser = argparse.ArgumentParser(description="Train ML salary benchmark, select Champion, and export artifacts.")
    parser.add_argument("--input", default=str(REPO_ROOT / "data" / "processed" / "clean_postings.csv"))
    parser.add_argument("--models-dir", default=str(REPO_ROOT / "models"))
    parser.add_argument("--out-dir", default=str(REPO_ROOT / "data" / "processed"))
    parser.add_argument("--report", default=str(REPO_ROOT / "docs" / "ml-report.md"))
    parser.add_argument("--merge-seed", action="store_true", help="Atomically merge ML keys into seed_marts.json")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", "").strip() or None)
    parser.add_argument("--top-k-skills", type=int, default=40)
    parser.add_argument("--min-skill-freq", type=int, default=2)
    parser.add_argument("--outer-splits", type=int, default=5)
    parser.add_argument("--inner-splits", type=int, default=3)
    parser.add_argument("--n-tuning-trials", type=int, default=6)
    args = parser.parse_args(argv)

    # Guard placeholder DATABASE_URL from .env.example
    db_url = args.database_url
    if db_url and any(p in db_url.lower() for p in ("your-project-id", "your-password", "<project-id>")):
        db_url = None

    summary = run_ml_pipeline(
        input_csv=args.input,
        models_dir=args.models_dir,
        out_dir=args.out_dir,
        report_path=args.report,
        merge_seed=args.merge_seed,
        database_url=db_url,
        top_k_skills=args.top_k_skills,
        min_skill_freq=args.min_skill_freq,
        outer_splits=args.outer_splits,
        inner_splits=args.inner_splits,
        n_tuning_trials=args.n_tuning_trials,
    )
    print(
        f"ML export done: version={summary['dataset_version']} n_rows={summary['n_rows']} "
        f"companies={summary['n_companies']} champion={summary['champion_model']} "
        f"RMSE={summary['cv_metrics']['rmse']:.1f} MAE={summary['cv_metrics']['mae']:.1f} "
        f"MAPE={summary['cv_metrics']['mape']:.2f}% beats_baseline={summary['beats_baseline']} "
        f"fallback_grid={summary['n_salary_predictions']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
