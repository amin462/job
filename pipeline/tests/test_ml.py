"""Unit and integration tests for ML features, fairness guards, Nested CV, export & ml-api (T4.0–T4.7)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline.ml.benchmark import (
    MAX_TUNING_TRIALS,
    MODEL_ORDER,
    HierarchicalMedianBaseline,
    run_benchmark,
    sample_param_candidates,
    tune_hyperparameters_nested,
)
from pipeline.ml.export_model import merge_ml_into_seed_marts, run_ml_pipeline
from pipeline.ml.features import (
    SALARY_MAX_THB,
    SALARY_MIN_THB,
    assert_no_forbidden_features,
    build_feature_matrix,
    build_inference_dataframe,
    is_forbidden_feature_name,
    predict_salary_records,
    validate_feature_spec,
)

# Load services/ml-api/main.py cleanly (hyphenated directory name)
_ML_API_SPEC = importlib.util.spec_from_file_location(
    "ml_api_main",
    REPO_ROOT / "services" / "ml-api" / "main.py",
)
assert _ML_API_SPEC is not None and _ML_API_SPEC.loader is not None
ml_api_main = importlib.util.module_from_spec(_ML_API_SPEC)
sys.modules["ml_api_main"] = ml_api_main
_ML_API_SPEC.loader.exec_module(ml_api_main)

FORBIDDEN_INJECT_FIELDS = (
    "gender",
    "mentions_gender",
    "age",
    "mentions_age",
    "company",
    "company_name",
    "company_name_norm",
    "company_key",
)


def _make_synthetic_postings(n_companies: int = 8, rows_per_company: int = 6) -> pd.DataFrame:
    """Create realistic synthetic salaried postings with clear signal (no gender/age/company effect)."""
    rng = np.random.default_rng(42)
    occupations = [
        ("Data & Analytics", 38000),
        ("Software & IT", 42000),
        ("Accounting & Finance", 26000),
        ("Sales & Business Development", 20000),
    ]
    regions_provs = [
        ("กลาง", "กรุงเทพมหานคร", 1.20),
        ("ตะวันออก", "ชลบุรี", 1.10),
        ("ใต้", "สงขลา", 0.95),
        ("อีสาน", "ขอนแก่น", 0.90),
    ]
    exps = [
        ("ไม่ระบุ/ไม่จำเป็น", 0.95),
        ("0 ปี / จบใหม่", 1.00),
        ("1-2 ปี", 1.18),
        ("3-5 ปี", 1.42),
    ]
    edus = [
        ("ม.3/ม.6", 0.90),
        ("ปวช./ปวส.", 1.00),
        ("ปริญญาตรี", 1.25),
    ]
    skill_pools = {
        "Data & Analytics": ["SQL", "Python", "Power BI", "Microsoft Excel"],
        "Software & IT": ["Python", "SQL", "Docker / Kubernetes", "Git / Version Control"],
        "Accounting & Finance": ["Accounting", "Tax", "Microsoft Excel", "SAP / ERP"],
        "Sales & Business Development": ["Sales & Closing", "Communication", "Negotiation & Persuasion"],
    }

    rows = []
    idx = 0
    for c_i in range(n_companies):
        comp_name = f"company_{c_i:02d}"
        for _ in range(rows_per_company):
            occ, base_sal = occupations[idx % len(occupations)]
            reg, prov, reg_mult = regions_provs[(idx // 2) % len(regions_provs)]
            exp, exp_mult = exps[(idx // 3) % len(exps)]
            edu, edu_mult = edus[(idx // 4) % len(edus)]
            sk_pool = skill_pools[occ]
            n_sk = 1 + (idx % len(sk_pool))
            chosen_sk = sk_pool[:n_sk]
            noise = float(rng.normal(1.0, 0.03))
            salary = round(base_sal * reg_mult * exp_mult * edu_mult * (1.0 + 0.05 * n_sk) * noise, -2)
            salary = max(SALARY_MIN_THB, min(SALARY_MAX_THB, salary))
            rows.append(
                {
                    "source": "jobthai",
                    "source_job_id": f"syn_{idx}",
                    "company_name_norm": comp_name,
                    "occupation_cluster": occ,
                    "province_th": prov,
                    "region": reg,
                    "experience_band": exp,
                    "education_level": edu,
                    "employment_type": "FULL_TIME",
                    "industry": "เทคโนโลยี" if occ in ("Data & Analytics", "Software & IT") else "พาณิชย์",
                    "n_skills": len(chosen_sk),
                    "skills": "|".join(chosen_sk),
                    "has_salary": True,
                    "salary_mid": salary,
                    "mentions_gender": bool(idx % 2 == 0),
                    "mentions_age": bool(idx % 3 == 0),
                }
            )
            idx += 1

    # Add non-salaried and out-of-range rows that MUST be filtered out
    rows.append(
        {
            "source": "jobthai",
            "source_job_id": "syn_nosal",
            "company_name_norm": "company_99",
            "occupation_cluster": "Data & Analytics",
            "province_th": "กรุงเทพมหานคร",
            "region": "กลาง",
            "experience_band": "1-2 ปี",
            "education_level": "ปริญญาตรี",
            "employment_type": "FULL_TIME",
            "industry": "เทคโนโลยี",
            "n_skills": 2,
            "skills": "SQL|Python",
            "has_salary": False,
            "salary_mid": np.nan,
            "mentions_gender": True,
            "mentions_age": True,
        }
    )
    rows.append(
        {
            "source": "jobthai",
            "source_job_id": "syn_oor",
            "company_name_norm": "company_98",
            "occupation_cluster": "Data & Analytics",
            "province_th": "กรุงเทพมหานคร",
            "region": "กลาง",
            "experience_band": "1-2 ปี",
            "education_level": "ปริญญาตรี",
            "employment_type": "FULL_TIME",
            "industry": "เทคโนโลยี",
            "n_skills": 2,
            "skills": "SQL|Python",
            "has_salary": True,
            "salary_mid": 999_999.0,  # exceeds 500,000 cap
            "mentions_gender": False,
            "mentions_age": False,
        }
    )
    return pd.DataFrame(rows)


def test_features_filters_salary_and_excludes_forbidden_columns():
    clean_csv = REPO_ROOT / "data" / "processed" / "clean_postings.csv"
    df = pd.read_csv(clean_csv)
    ds = build_feature_matrix(df)

    # Only salaried rows in [5000, 500000]
    expected_sal = df[
        (df["has_salary"] == True)  # noqa: E712
        & (df["salary_mid"] >= SALARY_MIN_THB)
        & (df["salary_mid"] <= SALARY_MAX_THB)
    ]
    assert len(ds.X) == len(expected_sal)
    assert np.allclose(ds.y_log, np.log(expected_sal["salary_mid"].to_numpy()), atol=1e-9)

    # Zero forbidden columns in X or feature_spec
    for forbidden in FORBIDDEN_INJECT_FIELDS:
        assert forbidden not in ds.X.columns
        assert forbidden not in ds.feature_spec["feature_columns"]
    assert_no_forbidden_features(ds.X.columns)
    validate_feature_spec(ds.feature_spec)

    # Legitimate terms containing substring 'age' (e.g. language/management) are NOT falsely flagged
    assert not is_forbidden_feature_name("skill__english")
    assert not is_forbidden_feature_name("skill__thai_language")
    assert not is_forbidden_feature_name("skill__leadership_team_management")


@pytest.mark.parametrize("forbidden_col", FORBIDDEN_INJECT_FIELDS)
def test_features_rejects_injected_forbidden_columns(forbidden_col: str):
    df = _make_synthetic_postings(n_companies=5, rows_per_company=4)
    ds = build_feature_matrix(df)

    # 1. Reject via extra_columns request
    with pytest.raises(ValueError, match="Fairness/leakage violation"):
        build_feature_matrix(df, extra_columns=[forbidden_col])

    # 2. Reject via assert_no_forbidden_features on feature matrix columns
    with pytest.raises(ValueError, match="Fairness/leakage violation"):
        assert_no_forbidden_features([*ds.X.columns, forbidden_col])

    # 3. Reject if injected into input DataFrame with strict guard (non-group raw columns)
    if forbidden_col not in ("company_name_norm", "company_key"):
        injected_df = df.copy()
        injected_df[forbidden_col] = "test_val"
        with pytest.raises(ValueError, match="Fairness/leakage violation"):
            build_feature_matrix(injected_df, reject_forbidden_in_input=True)

    # 4. Reject if injected into inference payload
    payload = {
        "occupation_cluster": "Data & Analytics",
        "province_th": "กรุงเทพมหานคร",
        "experience_band": "1-2 ปี",
        "education_level": "ปริญญาตรี",
        "employment_type": "FULL_TIME",
        "skills": ["SQL"],
        forbidden_col: "injected",
    }
    with pytest.raises(ValueError, match="Fairness policy violation"):
        build_inference_dataframe([payload], ds.feature_spec)

    # 5. Reject if present in feature_spec.json
    bad_spec = dict(ds.feature_spec)
    bad_spec["feature_columns"] = [*ds.feature_spec["feature_columns"], forbidden_col]
    with pytest.raises(ValueError, match="Fairness/leakage violation"):
        validate_feature_spec(bad_spec)


def test_groupkfold_zero_company_overlap_and_nested_cv_isolation():
    df = _make_synthetic_postings(n_companies=10, rows_per_company=5)
    ds = build_feature_matrix(df)
    groups = ds.groups

    outer_audit: dict[int, tuple[set[int], set[int]]] = {}

    def on_outer(fold_idx, tr_idx, va_idx, tr_groups, va_groups):
        assert set(map(str, tr_groups)).isdisjoint(set(map(str, va_groups)))
        assert set(tr_idx.tolist()).isdisjoint(set(va_idx.tolist()))
        outer_audit[fold_idx] = (set(tr_idx.tolist()), set(va_idx.tolist()))

    def on_inner(fold_idx, in_tr_global_idx, in_va_global_idx):
        tr_set, va_set = outer_audit[fold_idx]
        # Inner splits MUST strictly remain inside outer train indices & NEVER touch outer val!
        assert set(in_tr_global_idx.tolist()).issubset(tr_set)
        assert set(in_va_global_idx.tolist()).issubset(tr_set)
        assert set(in_tr_global_idx.tolist()).isdisjoint(va_set)
        assert set(in_va_global_idx.tolist()).isdisjoint(va_set)
        # Zero company overlap inside inner CV too
        assert set(map(str, groups[in_tr_global_idx])).isdisjoint(
            set(map(str, groups[in_va_global_idx]))
        )

    res = run_benchmark(
        ds,
        models=MODEL_ORDER,
        outer_splits=5,
        inner_splits=3,
        n_tuning_trials=2,
        outer_fold_callback=on_outer,
        inner_split_callback=on_inner,
    )

    assert len(outer_audit) == 5
    assert all(fa["company_overlap_count"] == 0 for fa in res.fold_audit)
    assert {r["model_name"] for r in res.summary_rows} == set(MODEL_ORDER)
    assert len(res.summary_rows) == 6
    assert all(r["fold"] == -1 and r["is_summary"] is True for r in res.summary_rows)

    # Check inner tuning trial cap <= 20
    assert len(sample_param_candidates("XGBoost", 100, n_trials=99, random_state=42)) <= MAX_TUNING_TRIALS

    # Direct tune_hyperparameters_nested isolation check
    tr_idx = np.array(sorted(outer_audit[0][0]))
    in_checked = []
    tune_hyperparameters_nested(
        "Ridge",
        ds.X.iloc[tr_idx],
        ds.y_log[tr_idx],
        groups[tr_idx],
        ds.feature_spec["skill_feature_names"],
        inner_splits=3,
        n_tuning_trials=4,
        inner_split_callback=lambda in_tr, in_va: in_checked.append((len(in_tr), len(in_va))),
    )
    assert len(in_checked) == 3


def test_groupkfold_fallback_when_fewer_than_5_companies():
    df = _make_synthetic_postings(n_companies=3, rows_per_company=6)
    ds = build_feature_matrix(df)
    res = run_benchmark(
        ds,
        models=("Baseline", "Ridge"),
        outer_splits=5,
        inner_splits=3,
        n_tuning_trials=3,
    )
    assert res.n_outer_splits == 3
    assert all(fa["company_overlap_count"] == 0 for fa in res.fold_audit)


def test_baseline_hierarchy():
    df = pd.DataFrame(
        {
            "occupation_cluster": ["Data & Analytics", "Data & Analytics", "Sales & Business Development"],
            "region": ["กลาง", "อีสาน", "กลาง"],
        }
    )
    y_log = np.log([40000.0, 30000.0, 20000.0])
    base = HierarchicalMedianBaseline().fit(df, y_log)

    q = pd.DataFrame(
        {
            "occupation_cluster": ["Data & Analytics", "Data & Analytics", "Unknown Occ"],
            "region": ["กลาง", "เหนือ", "ใต้"],
        }
    )
    preds_thb = np.exp(base.predict(q))
    assert np.isclose(preds_thb[0], 40000.0)  # exact occ x region
    assert np.isclose(preds_thb[1], np.sqrt(40000.0 * 30000.0) if False else 35000.0)  # occ fallback median
    assert np.isclose(preds_thb[2], 30000.0)  # global median fallback


def test_export_pipeline_and_ml_api_parity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    df = _make_synthetic_postings(n_companies=8, rows_per_company=6)
    in_csv = tmp_path / "clean_postings.csv"
    df.to_csv(in_csv, index=False)

    # Existing ETL seed_marts.json should be preserved on merge
    seed_path = tmp_path / "seed_marts.json"
    seed_path.write_text(
        json.dumps({"public_summary": {"n_postings": 999}, "ml_leaderboard": []}, ensure_ascii=False),
        encoding="utf-8",
    )

    models_dir = tmp_path / "models"
    report_path = tmp_path / "ml-report.md"
    summary = run_ml_pipeline(
        input_csv=in_csv,
        models_dir=models_dir,
        out_dir=tmp_path,
        report_path=report_path,
        merge_seed=True,
        outer_splits=4,
        inner_splits=3,
        n_tuning_trials=2,
    )

    assert summary["beats_baseline"] is True
    assert summary["champion_model"] in set(MODEL_ORDER) - {"Baseline"}
    assert (models_dir / "salary_champion.joblib").exists()
    assert (models_dir / "feature_spec.json").exists()
    assert (tmp_path / "ml_marts.json").exists()
    assert report_path.exists()

    spec = json.loads((models_dir / "feature_spec.json").read_text(encoding="utf-8"))
    validate_feature_spec(spec)
    for forbidden in FORBIDDEN_INJECT_FIELDS:
        assert forbidden not in spec["feature_columns"]

    # Verify atomic merge kept ETL key and added ML keys
    merged_seed = json.loads(seed_path.read_text(encoding="utf-8"))
    assert merged_seed["public_summary"]["n_postings"] == 999
    assert len(merged_seed["ml_leaderboard"]) > 0
    assert len(merged_seed["ml_feature_importance"]) > 0
    assert 0 < len(merged_seed["salary_prediction"]) < 1000

    # Configure FastAPI ml-api env vars to point to exported tmp artifacts + secret key
    monkeypatch.setenv("MODEL_PATH", str(models_dir / "salary_champion.joblib"))
    monkeypatch.setenv("FEATURE_SPEC_PATH", str(models_dir / "feature_spec.json"))
    monkeypatch.setenv("ML_API_KEY", "test-secret-key-2026")
    ml_api_main._BUNDLE_CACHE["key"] = None

    with TestClient(ml_api_main.app) as client:
        # 1. GET /health succeeds WITHOUT auth key
        health_res = client.get("/health")
        assert health_res.status_code == 200
        hdata = health_res.json()
        assert hdata["status"] == "ok"
        assert hdata["model"] == summary["champion_model"]
        assert hdata["n_rows"] == summary["n_rows"]

        sample_payload = {
            "occupation_cluster": "Data & Analytics",
            "province_th": "กรุงเทพมหานคร",
            "experience_band": "1-2 ปี",
            "education_level": "ปริญญาตรี",
            "employment_type": "FULL_TIME",
            "skills": ["SQL", "Python"],
        }

        # 2. Missing / wrong X-ML-Key rejected with 401 / 403
        assert client.post("/predict", json=sample_payload).status_code == 401
        assert client.post("/predict", json=sample_payload, headers={"X-ML-Key": "wrong"}).status_code == 403
        assert client.post("/predict/batch", json={"items": [sample_payload]}).status_code == 401
        assert client.post("/predict/batch", json={"items": [sample_payload]}, headers={"X-ML-Key": "wrong"}).status_code == 403

        # 3. Forbidden fairness keys rejected with 422
        for bad_key in ("gender", "mentions_gender", "age", "mentions_age", "company_name_norm"):
            bad_res = client.post(
                "/predict",
                json={**sample_payload, bad_key: "bad"},
                headers={"X-ML-Key": "test-secret-key-2026"},
            )
            assert bad_res.status_code == 422

        # 4. Valid /predict matches direct Python Champion prediction within ±1e-6
        direct_model = joblib.load(models_dir / "salary_champion.joblib")
        direct_pred = predict_salary_records(direct_model, spec, [sample_payload])[0]

        api_res = client.post(
            "/predict",
            json=sample_payload,
            headers={"X-ML-Key": "test-secret-key-2026"},
        )
        assert api_res.status_code == 200
        api_pred = api_res.json()
        assert api_pred["p25"] <= api_pred["p50"] <= api_pred["p75"]
        assert api_pred["out_of_domain"] is False
        assert api_pred["model_name"] == summary["champion_model"]
        assert abs(api_pred["p25"] - direct_pred["p25"]) <= 1e-6
        assert abs(api_pred["p50"] - direct_pred["p50"]) <= 1e-6
        assert abs(api_pred["p75"] - direct_pred["p75"]) <= 1e-6

        # 5. Out-of-domain flag triggers for unknown occupation
        ood_res = client.post(
            "/predict",
            json={**sample_payload, "occupation_cluster": "Astronaut"},
            headers={"X-ML-Key": "test-secret-key-2026"},
        )
        assert ood_res.status_code == 200
        assert ood_res.json()["out_of_domain"] is True

        # 6. Valid /predict/batch matches direct Python predictions within ±1e-6
        batch_items = [
            sample_payload,
            {**sample_payload, "skills": ["SQL", "Python", "Power BI"]},
            {**sample_payload, "province_th": "สงขลา", "experience_band": "3-5 ปี"},
        ]
        direct_batch = predict_salary_records(direct_model, spec, batch_items)
        batch_res = client.post(
            "/predict/batch",
            json={"items": batch_items},
            headers={"X-ML-Key": "test-secret-key-2026"},
        )
        assert batch_res.status_code == 200
        bdata = batch_res.json()
        assert bdata["count"] == len(batch_items)
        for api_item, py_item in zip(bdata["predictions"], direct_batch):
            assert abs(api_item["p25"] - py_item["p25"]) <= 1e-6
            assert abs(api_item["p50"] - py_item["p50"]) <= 1e-6
            assert abs(api_item["p75"] - py_item["p75"]) <= 1e-6


def test_real_exported_artifacts_and_ml_api_parity(monkeypatch: pytest.MonkeyPatch):
    """Verify real models/ artifacts generated from clean_postings.csv load and serve identically."""
    model_path = REPO_ROOT / "models" / "salary_champion.joblib"
    spec_path = REPO_ROOT / "models" / "feature_spec.json"
    if not model_path.exists() or not spec_path.exists():
        pytest.skip("Real exported model artifacts not present yet.")

    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    validate_feature_spec(spec)
    for forbidden in FORBIDDEN_INJECT_FIELDS:
        assert forbidden not in spec["feature_columns"]

    direct_model = joblib.load(model_path)
    payload = {
        "occupation_cluster": "Sales & Business Development",
        "province_th": "กรุงเทพมหานคร",
        "experience_band": "1-2 ปี",
        "education_level": "ปริญญาตรี",
        "employment_type": "FULL_TIME",
        "skills": ["Sales & Closing", "Communication"],
    }
    direct_pred = predict_salary_records(direct_model, spec, [payload])[0]

    monkeypatch.setenv("MODEL_PATH", str(model_path))
    monkeypatch.setenv("FEATURE_SPEC_PATH", str(spec_path))
    monkeypatch.setenv("ML_API_KEY", "prod-verify-key")
    ml_api_main._BUNDLE_CACHE["key"] = None

    with TestClient(ml_api_main.app) as client:
        h = client.get("/health")
        assert h.status_code == 200
        assert h.json()["model"] == spec["champion_model"]

        r = client.post(
            "/predict",
            json=payload,
            headers={"X-ML-Key": "prod-verify-key"},
        )
        assert r.status_code == 200
        api_pred = r.json()
        assert abs(api_pred["p25"] - direct_pred["p25"]) <= 1e-6
        assert abs(api_pred["p50"] - direct_pred["p50"]) <= 1e-6
        assert abs(api_pred["p75"] - direct_pred["p75"]) <= 1e-6
