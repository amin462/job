"""Champion selection, full-data retraining, permutation importance & error analysis (T4.4, T4.7)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator
from sklearn.inspection import permutation_importance

from pipeline.ml.benchmark import (
    BenchmarkResult,
    compute_thb_metrics,
    create_model_pipeline,
    log_preds_to_thb,
    tune_hyperparameters_nested,
)
from pipeline.ml.features import FeatureDataset


@dataclass
class ChampionResult:
    """Artifacts and diagnostics for the winning Champion salary regression model."""

    champion_name: str
    beats_baseline: bool
    baseline_rmse: float
    champion_cv_metrics: dict[str, Any]
    champion_params: dict[str, Any]
    champion_estimator: BaseEstimator
    feature_importance: list[dict[str, Any]]
    residual_quantiles_log: dict[str, Any]
    error_breakdown_occupation: list[dict[str, Any]]
    error_breakdown_region: list[dict[str, Any]]


def compute_residual_quantiles(
    y_true_log: np.ndarray,
    oof_pred_log: np.ndarray,
) -> dict[str, Any]:
    """Compute centered out-of-fold log-residual quantiles for p25..p75 prediction intervals."""
    residuals = np.asarray(y_true_log, dtype=np.float64) - np.asarray(oof_pred_log, dtype=np.float64)
    raw_q25, raw_q50, raw_q75 = [float(x) for x in np.quantile(residuals, [0.25, 0.50, 0.75])]
    centered = residuals - raw_q50
    q25_offset = float(min(0.0, np.quantile(centered, 0.25)))
    q75_offset = float(max(0.0, np.quantile(centered, 0.75)))
    return {
        "q25": round(q25_offset, 6),
        "q50": 0.0,
        "q75": round(q75_offset, 6),
        "raw_q25": round(raw_q25, 6),
        "raw_q50": round(raw_q50, 6),
        "raw_q75": round(raw_q75, 6),
        "n_residuals": int(len(residuals)),
        "method": "oof_centered_log_residuals",
    }


def compute_permutation_feature_importance(
    estimator: BaseEstimator,
    X: pd.DataFrame,
    y_log: np.ndarray,
    *,
    n_repeats: int = 15,
    random_state: int = 42,
    top_n: int = 25,
) -> list[dict[str, Any]]:
    """Compute permutation importance on input columns using R2 in log-salary space."""
    perm = permutation_importance(
        estimator,
        X,
        y_log,
        scoring="r2",
        n_repeats=n_repeats,
        random_state=random_state,
        n_jobs=1,
    )
    rows: list[dict[str, Any]] = []
    for col, mean_imp, std_imp in zip(X.columns, perm.importances_mean, perm.importances_std):
        rows.append(
            {
                "feature": str(col),
                "importance": round(float(mean_imp), 6),
                "importance_std": round(float(std_imp), 6),
            }
        )
    rows.sort(key=lambda r: (-r["importance"], r["feature"]))
    return rows[:top_n]


def compute_subgroup_error_breakdown(
    X: pd.DataFrame,
    y_true_log: np.ndarray,
    oof_pred_log: np.ndarray,
    group_col: str,
) -> list[dict[str, Any]]:
    """Compute OOF error metrics broken down by occupation_cluster or region (T4.7)."""
    y_true_thb = np.exp(np.asarray(y_true_log, dtype=np.float64))
    y_pred_thb = log_preds_to_thb(oof_pred_log)

    df_eval = pd.DataFrame(
        {
            "subgroup": X[group_col].astype(str).values,
            "y_true": y_true_thb,
            "y_pred": y_pred_thb,
        }
    )
    breakdown: list[dict[str, Any]] = []
    for sub_val, sub_df in df_eval.groupby("subgroup", sort=False):
        yt = sub_df["y_true"].to_numpy()
        yp = sub_df["y_pred"].to_numpy()
        rmse = float(np.sqrt(np.mean((yt - yp) ** 2)))
        mae = float(np.mean(np.abs(yt - yp)))
        mape = float(np.mean(np.abs(yt - yp) / np.maximum(yt, 1e-9)) * 100.0)
        breakdown.append(
            {
                "subgroup": str(sub_val),
                "n_rows": int(len(sub_df)),
                "mean_actual_thb": round(float(np.mean(yt)), 0),
                "mean_pred_thb": round(float(np.mean(yp)), 0),
                "median_actual_thb": round(float(np.median(yt)), 0),
                "rmse": round(rmse, 2),
                "mae": round(mae, 2),
                "mape": round(mape, 2),
            }
        )
    breakdown.sort(key=lambda r: (-r["n_rows"], r["rmse"]))
    return breakdown


def select_and_fit_champion(
    dataset: FeatureDataset,
    benchmark: BenchmarkResult,
    *,
    inner_splits: int = 3,
    n_tuning_trials: int = 6,
    random_state: int = 42,
    require_beat_baseline: bool = False,
) -> ChampionResult:
    """Select the lowest-RMSE ML model, verify against Baseline, and fit on full dataset."""
    summary_by_name = {r["model_name"]: r for r in benchmark.summary_rows}
    baseline_row = summary_by_name.get("Baseline")
    baseline_rmse = float(baseline_row["rmse"]) if baseline_row else float("inf")

    ml_candidates = [r for r in benchmark.summary_rows if r["model_name"] != "Baseline"]
    if not ml_candidates:
        raise ValueError("Benchmark contains no ML model candidates besides Baseline.")

    ml_candidates.sort(key=lambda r: (float(r["rmse"]), float(r["mae"]), -float(r["r2"])))
    winner_row = ml_candidates[0]
    champion_name = str(winner_row["model_name"])
    beats_baseline = float(winner_row["rmse"]) < baseline_rmse

    if require_beat_baseline and not beats_baseline:
        raise ValueError(
            f"Best ML model {champion_name} (RMSE={winner_row['rmse']:.2f}) "
            f"did not beat Baseline (RMSE={baseline_rmse:.2f})."
        )

    # Mark champion flags in leaderboard rows
    for row in benchmark.rows:
        row["is_champion"] = row["model_name"] == champion_name
    for row in benchmark.summary_rows:
        row["is_champion"] = row["model_name"] == champion_name

    # Final hyperparameter selection on full dataset via GroupKFold (for full-data refit)
    skill_cols = list(dataset.feature_spec.get("skill_feature_names") or [])
    final_params, _ = tune_hyperparameters_nested(
        model_name=champion_name,
        X_train=dataset.X,
        y_train_log=dataset.y_log,
        train_groups=dataset.groups,
        skill_columns=skill_cols,
        inner_splits=min(5, max(2, inner_splits)),
        n_tuning_trials=n_tuning_trials,
        random_state=random_state,
    )

    champion_estimator = create_model_pipeline(
        model_name=champion_name,
        skill_columns=skill_cols,
        params=final_params,
        random_state=random_state,
    )
    champion_estimator.fit(dataset.X, dataset.y_log)

    oof_pred_log = benchmark.oof_predictions_log[champion_name]
    residual_quantiles = compute_residual_quantiles(dataset.y_log, oof_pred_log)
    feat_imp = compute_permutation_feature_importance(
        champion_estimator,
        dataset.X,
        dataset.y_log,
        random_state=random_state,
    )
    occ_breakdown = compute_subgroup_error_breakdown(
        dataset.X, dataset.y_log, oof_pred_log, "occupation_cluster"
    )
    reg_breakdown = compute_subgroup_error_breakdown(
        dataset.X, dataset.y_log, oof_pred_log, "region"
    )

    # Keep exact CV metrics of champion from outer CV summary
    cv_metrics = {
        "r2": float(winner_row["r2"]),
        "rmse": float(winner_row["rmse"]),
        "mae": float(winner_row["mae"]),
        "mape": float(winner_row["mape"]),
        "r2_sd": float(winner_row.get("r2_sd") or 0.0),
        "rmse_sd": float(winner_row.get("rmse_sd") or 0.0),
        "mae_sd": float(winner_row.get("mae_sd") or 0.0),
        "mape_sd": float(winner_row.get("mape_sd") or 0.0),
        "oof_overall": compute_thb_metrics(dataset.y_log, oof_pred_log),
    }

    return ChampionResult(
        champion_name=champion_name,
        beats_baseline=beats_baseline,
        baseline_rmse=baseline_rmse,
        champion_cv_metrics=cv_metrics,
        champion_params=final_params,
        champion_estimator=champion_estimator,
        feature_importance=feat_imp,
        residual_quantiles_log=residual_quantiles,
        error_breakdown_occupation=occ_breakdown,
        error_breakdown_region=reg_breakdown,
    )
