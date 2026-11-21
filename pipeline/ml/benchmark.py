"""Salary regression model benchmark with Nested GroupKFold CV (T4.2, T4.3, D15).

Compares Baseline (median of occupation_cluster x region -> occupation_cluster -> global)
against >= 5 ML models: Ridge, RandomForest, XGBoost, LightGBM, and CatBoost.

Evaluation guarantees:
- Outer CV: GroupKFold(n_splits=5) grouped by company_name_norm (zero company overlap).
- Inner CV (hyperparameter tuning): GroupKFold(n_splits=3) STRICTLY inside each outer
  training split (<= 20 random parameter candidates per model per fold).
- Target: log(salary_mid); all reported metrics (R2, RMSE, MAE, MAPE) are computed back in THB.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from lightgbm import LGBMRegressor
from sklearn.base import BaseEstimator, RegressorMixin, clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, KFold, ParameterSampler
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBRegressor

from pipeline.ml.features import CATEGORICAL_FEATURES, NUMERIC_FEATURES, FeatureDataset

MODEL_ORDER: tuple[str, ...] = (
    "Baseline",
    "Ridge",
    "RandomForest",
    "XGBoost",
    "LightGBM",
    "CatBoost",
)
MAX_TUNING_TRIALS = 20


class HierarchicalMedianBaseline(BaseEstimator, RegressorMixin):
    """Baseline regressor predicting median(salary_mid) by (occupation_cluster x region),
    falling back to occupation_cluster median, then global training median.
    Fits and predicts in log(THB) space so exp(pred) equals the exact THB median.
    """

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> "HierarchicalMedianBaseline":
        y_arr = np.asarray(y, dtype=np.float64)
        y_thb = np.exp(y_arr)
        self.global_median_log_ = float(np.log(np.median(y_thb)))

        occ_series = X["occupation_cluster"].astype(str).tolist()
        reg_series = X["region"].astype(str).tolist()

        occ_buckets: dict[str, list[float]] = {}
        occ_reg_buckets: dict[tuple[str, str], list[float]] = {}
        for occ, reg, val in zip(occ_series, reg_series, y_thb):
            occ_buckets.setdefault(occ, []).append(float(val))
            occ_reg_buckets.setdefault((occ, reg), []).append(float(val))

        self.occ_median_log_: dict[str, float] = {
            occ: float(np.log(np.median(vals))) for occ, vals in occ_buckets.items()
        }
        self.occ_reg_median_log_: dict[tuple[str, str], float] = {
            pair: float(np.log(np.median(vals))) for pair, vals in occ_reg_buckets.items()
        }
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        occ_series = X["occupation_cluster"].astype(str).tolist()
        reg_series = X["region"].astype(str).tolist()
        preds = [
            self.occ_reg_median_log_.get(
                (occ, reg),
                self.occ_median_log_.get(occ, self.global_median_log_),
            )
            for occ, reg in zip(occ_series, reg_series)
        ]
        return np.asarray(preds, dtype=np.float64)


@dataclass
class BenchmarkResult:
    """Complete benchmark output across Baseline + 5 ML models."""

    rows: list[dict[str, Any]]
    summary_rows: list[dict[str, Any]]
    oof_predictions_log: dict[str, np.ndarray]
    best_params_by_model: dict[str, dict[str, Any]]
    fold_audit: list[dict[str, Any]]
    n_rows: int
    n_companies: int
    n_outer_splits: int
    n_inner_splits: int
    n_tuning_trials: int


def build_preprocessor(skill_columns: list[str]) -> ColumnTransformer:
    """Build ColumnTransformer fit strictly inside each CV fold."""
    cat_pipe = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="constant", fill_value="ไม่ระบุ")),
            ("ohe", OneHotEncoder(handle_unknown="ignore", sparse_output=False, dtype=np.float64)),
        ]
    )
    num_pipe = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    transformers: list[tuple[str, Any, list[str]]] = [
        ("cat", cat_pipe, list(CATEGORICAL_FEATURES)),
        ("num", num_pipe, list(NUMERIC_FEATURES)),
    ]
    if skill_columns:
        transformers.append(
            ("skills", SimpleImputer(strategy="constant", fill_value=0.0), list(skill_columns))
        )
    return ColumnTransformer(transformers=transformers, remainder="drop")


def create_regressor(
    model_name: str,
    params: Mapping[str, Any] | None = None,
    random_state: int = 42,
) -> BaseEstimator:
    """Instantiate the bare regressor estimator for a given model_name."""
    p = dict(params or {})
    if model_name == "Ridge":
        return Ridge(
            alpha=float(p.get("alpha", 10.0)),
            random_state=random_state,
        )
    if model_name == "RandomForest":
        return RandomForestRegressor(
            n_estimators=int(p.get("n_estimators", 120)),
            max_depth=p.get("max_depth", 8),
            min_samples_leaf=int(p.get("min_samples_leaf", 2)),
            max_features=p.get("max_features", 0.6),
            random_state=random_state,
            n_jobs=1,
        )
    if model_name == "XGBoost":
        return XGBRegressor(
            n_estimators=int(p.get("n_estimators", 120)),
            max_depth=int(p.get("max_depth", 3)),
            learning_rate=float(p.get("learning_rate", 0.05)),
            subsample=float(p.get("subsample", 0.85)),
            colsample_bytree=float(p.get("colsample_bytree", 0.8)),
            reg_alpha=float(p.get("reg_alpha", 0.1)),
            reg_lambda=float(p.get("reg_lambda", 3.0)),
            objective="reg:squarederror",
            random_state=random_state,
            n_jobs=1,
            verbosity=0,
        )
    if model_name == "LightGBM":
        return LGBMRegressor(
            n_estimators=int(p.get("n_estimators", 120)),
            num_leaves=int(p.get("num_leaves", 15)),
            max_depth=int(p.get("max_depth", 5)),
            learning_rate=float(p.get("learning_rate", 0.05)),
            min_child_samples=int(p.get("min_child_samples", 5)),
            reg_alpha=float(p.get("reg_alpha", 0.1)),
            reg_lambda=float(p.get("reg_lambda", 1.0)),
            random_state=random_state,
            n_jobs=1,
            verbosity=-1,
            force_col_wise=True,
        )
    if model_name == "CatBoost":
        return CatBoostRegressor(
            iterations=int(p.get("iterations", 150)),
            depth=int(p.get("depth", 4)),
            learning_rate=float(p.get("learning_rate", 0.05)),
            l2_leaf_reg=float(p.get("l2_leaf_reg", 3.0)),
            random_seed=random_state,
            verbose=0,
            allow_writing_files=False,
            thread_count=1,
        )
    raise ValueError(f"Unknown model_name: {model_name}")


def create_model_pipeline(
    model_name: str,
    skill_columns: list[str],
    params: Mapping[str, Any] | None = None,
    random_state: int = 42,
) -> BaseEstimator:
    """Instantiate an estimator or sklearn Pipeline for the given model name and hyperparameters."""
    if model_name == "Baseline":
        return HierarchicalMedianBaseline()

    preprocessor = build_preprocessor(skill_columns)
    est = create_regressor(model_name, params=params, random_state=random_state)
    return Pipeline(steps=[("preprocessor", preprocessor), ("regressor", est)])


def get_param_distributions(model_name: str, n_train_samples: int) -> dict[str, list[Any]]:
    """Return hyperparameter search grid/distribution per model (adapted safely for small/large N)."""
    if model_name == "Baseline":
        return {}
    if model_name == "Ridge":
        return {
            "alpha": [0.1, 0.3, 1.0, 2.0, 5.0, 10.0, 20.0, 40.0, 75.0, 120.0, 200.0],
        }
    if model_name == "RandomForest":
        return {
            "n_estimators": [50, 80, 120],
            "max_depth": [4, 6, 8, 12, None],
            "min_samples_leaf": [1, 2, 3, 5] if n_train_samples < 300 else [2, 4, 8, 15],
            "max_features": ["sqrt", 0.4, 0.6, 0.8],
        }
    if model_name == "XGBoost":
        return {
            "n_estimators": [60, 100, 150],
            "max_depth": [2, 3, 4, 6],
            "learning_rate": [0.03, 0.05, 0.08, 0.12],
            "subsample": [0.7, 0.85, 1.0],
            "colsample_bytree": [0.6, 0.8, 1.0],
            "reg_alpha": [0.0, 0.1, 0.5, 1.0],
            "reg_lambda": [1.0, 3.0, 10.0],
        }
    if model_name == "LightGBM":
        min_child = [2, 3, 5, 10] if n_train_samples < 300 else [5, 10, 20, 35]
        return {
            "n_estimators": [60, 100, 150],
            "num_leaves": [7, 12, 20, 31],
            "max_depth": [-1, 3, 5, 7],
            "learning_rate": [0.03, 0.05, 0.08, 0.12],
            "min_child_samples": min_child,
            "reg_alpha": [0.0, 0.1, 1.0],
            "reg_lambda": [0.0, 1.0, 5.0],
        }
    if model_name == "CatBoost":
        return {
            "iterations": [60, 100, 150],
            "depth": [3, 4, 5],
            "learning_rate": [0.03, 0.06, 0.10],
            "l2_leaf_reg": [1.0, 3.0, 7.0],
        }
    raise ValueError(f"Unknown model_name: {model_name}")


def sample_param_candidates(
    model_name: str,
    n_train_samples: int,
    n_trials: int,
    random_state: int,
) -> list[dict[str, Any]]:
    """Sample <= 20 deterministic hyperparameter candidates."""
    space = get_param_distributions(model_name, n_train_samples)
    if not space:
        return [{}]
    capped_trials = max(1, min(int(n_trials), MAX_TUNING_TRIALS))
    total_combos = 1
    for vals in space.values():
        total_combos *= len(vals)
    effective_iter = min(capped_trials, total_combos)
    return list(ParameterSampler(space, n_iter=effective_iter, random_state=random_state))


def get_group_splits(
    X: pd.DataFrame,
    groups: np.ndarray,
    requested_splits: int,
) -> tuple[list[tuple[np.ndarray, np.ndarray]], int]:
    """Generate GroupKFold splits (clean fallback if < requested_splits unique groups)."""
    n_unique = int(pd.Series(groups).nunique())
    n_samples = len(X)
    if n_unique >= 2:
        n_splits = min(int(requested_splits), n_unique)
        splitter = GroupKFold(n_splits=n_splits)
        splits = list(splitter.split(X, groups=groups))
        return splits, n_splits
    n_splits = min(int(requested_splits), n_samples)
    if n_splits < 2:
        raise ValueError(f"Need at least 2 samples/groups for CV, got n_samples={n_samples}, n_unique_groups={n_unique}.")
    splitter_kf = KFold(n_splits=n_splits, shuffle=True, random_state=42)
    return list(splitter_kf.split(X)), n_splits


def log_preds_to_thb(y_pred_log: np.ndarray) -> np.ndarray:
    """Convert log(salary) predictions safely back to THB."""
    clipped = np.clip(np.asarray(y_pred_log, dtype=np.float64), np.log(1_000.0), np.log(2_000_000.0))
    return np.exp(clipped)


def compute_thb_metrics(y_true_log: np.ndarray, y_pred_log: np.ndarray) -> dict[str, float]:
    """Compute R2, RMSE (THB), MAE (THB), and MAPE (%) in THB space."""
    y_true_thb = np.exp(np.asarray(y_true_log, dtype=np.float64))
    y_pred_thb = log_preds_to_thb(y_pred_log)

    rmse = float(np.sqrt(mean_squared_error(y_true_thb, y_pred_thb)))
    mae = float(mean_absolute_error(y_true_thb, y_pred_thb))
    mape = float(np.mean(np.abs((y_true_thb - y_pred_thb) / np.maximum(y_true_thb, 1e-9))) * 100.0)
    if len(y_true_thb) >= 2 and float(np.var(y_true_thb)) > 0.0:
        r2 = float(r2_score(y_true_thb, y_pred_thb))
    else:
        r2 = 0.0
    return {
        "r2": r2,
        "rmse": rmse,
        "mae": mae,
        "mape": mape,
    }


def tune_hyperparameters_nested(
    model_name: str,
    X_train: pd.DataFrame,
    y_train_log: np.ndarray,
    train_groups: np.ndarray,
    skill_columns: list[str],
    *,
    inner_splits: int = 3,
    n_tuning_trials: int = 6,
    random_state: int = 42,
    inner_split_callback: Callable[[np.ndarray, np.ndarray], None] | None = None,
    _precomputed_inner: list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]] | None = None,
) -> tuple[dict[str, Any], float]:
    """Run inner GroupKFold(3) strictly inside the outer training set to pick best params.

    Notice X_val/y_val are never passed to this function, making outer-fold leakage impossible.
    Each inner split fits its preprocessor ONLY on the inner training fold before scoring candidates.
    """
    if model_name == "Baseline":
        return {"strategy": "median_occ_x_region_fallback_occ_global"}, 0.0

    candidates = sample_param_candidates(
        model_name=model_name,
        n_train_samples=len(X_train),
        n_trials=n_tuning_trials,
        random_state=random_state,
    )
    if len(candidates) == 1:
        return dict(candidates[0]), 0.0

    if _precomputed_inner is None:
        splits, _ = get_group_splits(X_train, train_groups, requested_splits=inner_splits)
        precomputed: list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = []
        for in_tr, in_va in splits:
            if inner_split_callback is not None:
                inner_split_callback(in_tr, in_va)
            prep = build_preprocessor(skill_columns)
            Xt_tr = prep.fit_transform(X_train.iloc[in_tr])
            Xt_va = prep.transform(X_train.iloc[in_va])
            precomputed.append((Xt_tr, y_train_log[in_tr], Xt_va, y_train_log[in_va]))
    else:
        precomputed = _precomputed_inner

    best_params = dict(candidates[0])
    best_inner_rmse = float("inf")

    for cand in candidates:
        fold_rmses: list[float] = []
        for Xt_tr, y_in_tr, Xt_va, y_in_va in precomputed:
            reg = create_regressor(model_name=model_name, params=cand, random_state=random_state)
            reg.fit(Xt_tr, y_in_tr)
            preds_log = reg.predict(Xt_va)
            metrics = compute_thb_metrics(y_in_va, preds_log)
            fold_rmses.append(metrics["rmse"])

        mean_rmse = float(np.mean(fold_rmses))
        if mean_rmse < best_inner_rmse:
            best_inner_rmse = mean_rmse
            best_params = dict(cand)

    return best_params, best_inner_rmse


def _representative_params(fold_params: list[dict[str, Any]], fold_rmses: list[float]) -> dict[str, Any]:
    """Select params from the best-performing fold (or mode if uniform)."""
    if not fold_params:
        return {}
    best_idx = int(np.argmin(fold_rmses))
    return dict(fold_params[best_idx])


def run_benchmark(
    dataset: FeatureDataset,
    *,
    models: tuple[str, ...] = MODEL_ORDER,
    outer_splits: int = 5,
    inner_splits: int = 3,
    n_tuning_trials: int = 6,
    random_state: int = 42,
    outer_fold_callback: Callable[[int, np.ndarray, np.ndarray, np.ndarray, np.ndarray], None] | None = None,
    inner_split_callback: Callable[[int, np.ndarray, np.ndarray], None] | None = None,
) -> BenchmarkResult:
    """Evaluate Baseline + ML models using Nested GroupKFold CV."""
    X = dataset.X
    y_log = dataset.y_log
    groups = dataset.groups
    skill_cols = list(dataset.feature_spec.get("skill_feature_names") or [])
    capped_trials = max(1, min(int(n_tuning_trials), MAX_TUNING_TRIALS))

    outer_split_pairs, eff_outer = get_group_splits(X, groups, requested_splits=outer_splits)
    _, eff_inner_ref = get_group_splits(
        X.iloc[outer_split_pairs[0][0]],
        groups[outer_split_pairs[0][0]],
        requested_splits=inner_splits,
    )

    fold_audit: list[dict[str, Any]] = []
    precomputed_inner_by_fold: dict[int, list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]] = {}
    for fold_idx, (tr_idx, va_idx) in enumerate(outer_split_pairs):
        tr_cos = set(map(str, groups[tr_idx]))
        va_cos = set(map(str, groups[va_idx]))
        overlap = tr_cos & va_cos
        if overlap:
            raise AssertionError(f"GroupKFold company leakage detected on fold {fold_idx}: {overlap}")
        fold_audit.append(
            {
                "fold": fold_idx,
                "n_train": int(len(tr_idx)),
                "n_val": int(len(va_idx)),
                "n_train_companies": len(tr_cos),
                "n_val_companies": len(va_cos),
                "company_overlap_count": len(overlap),
            }
        )
        # Notify outer fold audit hook before inner splits are generated
        if outer_fold_callback is not None:
            outer_fold_callback(fold_idx, tr_idx, va_idx, groups[tr_idx], groups[va_idx])
        # Pre-transform inner splits once per outer fold (strictly inside outer train indices)
        X_tr_fold = X.iloc[tr_idx]
        y_tr_fold = y_log[tr_idx]
        groups_tr_fold = groups[tr_idx]
        in_splits, _ = get_group_splits(X_tr_fold, groups_tr_fold, requested_splits=inner_splits)
        precomp_list: list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = []
        for in_tr, in_va in in_splits:
            if inner_split_callback is not None:
                inner_split_callback(fold_idx, tr_idx[in_tr], tr_idx[in_va])
            prep_in = build_preprocessor(skill_cols)
            Xt_in_tr = prep_in.fit_transform(X_tr_fold.iloc[in_tr])
            Xt_in_va = prep_in.transform(X_tr_fold.iloc[in_va])
            precomp_list.append((Xt_in_tr, y_tr_fold[in_tr], Xt_in_va, y_tr_fold[in_va]))
        precomputed_inner_by_fold[fold_idx] = precomp_list

    all_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    oof_predictions_log: dict[str, np.ndarray] = {}
    best_params_by_model: dict[str, dict[str, Any]] = {}

    for model_name in models:
        fold_metrics_list: list[dict[str, Any]] = []
        fold_params_list: list[dict[str, Any]] = []
        fold_rmses: list[float] = []
        oof_arr = np.empty(len(y_log), dtype=np.float64)

        for fold_idx, (tr_idx, va_idx) in enumerate(outer_split_pairs):
            X_tr = X.iloc[tr_idx]
            y_tr_log = y_log[tr_idx]
            groups_tr = groups[tr_idx]

            X_va = X.iloc[va_idx]
            y_va_log = y_log[va_idx]

            t0 = time.perf_counter()
            best_params, inner_rmse = tune_hyperparameters_nested(
                model_name=model_name,
                X_train=X_tr,
                y_train_log=y_tr_log,
                train_groups=groups_tr,
                skill_columns=skill_cols,
                inner_splits=inner_splits,
                n_tuning_trials=capped_trials,
                random_state=random_state + fold_idx,
                _precomputed_inner=precomputed_inner_by_fold[fold_idx],
            )

            estimator = create_model_pipeline(
                model_name=model_name,
                skill_columns=skill_cols,
                params=best_params,
                random_state=random_state + fold_idx,
            )
            estimator.fit(X_tr, y_tr_log)
            fit_seconds = float(time.perf_counter() - t0)

            preds_va_log = np.asarray(estimator.predict(X_va), dtype=np.float64)
            oof_arr[va_idx] = preds_va_log
            metrics = compute_thb_metrics(y_va_log, preds_va_log)

            fold_row = {
                "model_name": model_name,
                "fold": int(fold_idx),
                "is_summary": False,
                "r2": round(metrics["r2"], 4),
                "rmse": round(metrics["rmse"], 2),
                "mae": round(metrics["mae"], 2),
                "mape": round(metrics["mape"], 2),
                "r2_sd": None,
                "rmse_sd": None,
                "mae_sd": None,
                "mape_sd": None,
                "fit_seconds": round(fit_seconds, 4),
                "params": dict(best_params),
                "inner_cv_rmse": round(inner_rmse, 2) if np.isfinite(inner_rmse) else None,
                "is_champion": False,
            }
            all_rows.append(fold_row)
            fold_metrics_list.append(metrics)
            fold_params_list.append(best_params)
            fold_rmses.append(metrics["rmse"])

        oof_predictions_log[model_name] = oof_arr
        rep_params = _representative_params(fold_params_list, fold_rmses)
        best_params_by_model[model_name] = rep_params

        ddof = 1 if len(fold_metrics_list) > 1 else 0
        r2_vals = [m["r2"] for m in fold_metrics_list]
        rmse_vals = [m["rmse"] for m in fold_metrics_list]
        mae_vals = [m["mae"] for m in fold_metrics_list]
        mape_vals = [m["mape"] for m in fold_metrics_list]
        time_vals = [
            r["fit_seconds"]
            for r in all_rows
            if r["model_name"] == model_name and not r["is_summary"]
        ]

        summary_row = {
            "model_name": model_name,
            "fold": -1,
            "is_summary": True,
            "r2": round(float(np.mean(r2_vals)), 4),
            "rmse": round(float(np.mean(rmse_vals)), 2),
            "mae": round(float(np.mean(mae_vals)), 2),
            "mape": round(float(np.mean(mape_vals)), 2),
            "r2_sd": round(float(np.std(r2_vals, ddof=ddof)), 4),
            "rmse_sd": round(float(np.std(rmse_vals, ddof=ddof)), 2),
            "mae_sd": round(float(np.std(mae_vals, ddof=ddof)), 2),
            "mape_sd": round(float(np.std(mape_vals, ddof=ddof)), 2),
            "fit_seconds": round(float(np.mean(time_vals)), 4),
            "params": {
                **rep_params,
                "outer_cv": f"GroupKFold({eff_outer})",
                "inner_cv": f"GroupKFold({eff_inner_ref})" if model_name != "Baseline" else "none",
                "n_trials": capped_trials if model_name != "Baseline" else 0,
            },
            "is_champion": False,
        }
        all_rows.append(summary_row)
        summary_rows.append(summary_row)

    return BenchmarkResult(
        rows=all_rows,
        summary_rows=summary_rows,
        oof_predictions_log=oof_predictions_log,
        best_params_by_model=best_params_by_model,
        fold_audit=fold_audit,
        n_rows=len(X),
        n_companies=int(pd.Series(groups).nunique()),
        n_outer_splits=eff_outer,
        n_inner_splits=eff_inner_ref,
        n_tuning_trials=capped_trials,
    )
