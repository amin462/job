"""FastAPI ML Champion Serving Service for Skill Demand Intelligence (T4.0, T4.5, D19).

Endpoints:
- GET  /health         (public, no auth required; used by cron-job.org & pre-warm)
- POST /predict        (requires X-ML-Key when ML_API_KEY env var is configured)
- POST /predict/batch  (requires X-ML-Key when ML_API_KEY env var is configured)
"""

import hmac
import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

import joblib
from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline.ml.features import (  # noqa: E402
    predict_salary_records,
    reject_forbidden_payload,
    validate_feature_spec,
)

DEFAULT_MODEL_PATH = "models/salary_champion.joblib"
DEFAULT_FEATURE_SPEC_PATH = "models/feature_spec.json"

_BUNDLE_CACHE: dict[str, Any] = {
    "key": None,
    "model": None,
    "spec": None,
}


def _resolve_path(env_name: str, default_rel: str) -> Path:
    raw = os.environ.get(env_name, default_rel).strip() or default_rel
    p = Path(raw)
    if p.is_absolute():
        return p
    cwd_candidate = Path.cwd() / p
    if cwd_candidate.exists():
        return cwd_candidate
    return REPO_ROOT / p


def load_champion_bundle(force_reload: bool = False) -> tuple[Any, dict[str, Any]]:
    """Load (and cache by path + mtime) the Champion joblib model and feature_spec.json."""
    model_path = _resolve_path("MODEL_PATH", DEFAULT_MODEL_PATH)
    spec_path = _resolve_path("FEATURE_SPEC_PATH", DEFAULT_FEATURE_SPEC_PATH)

    if not model_path.exists():
        raise FileNotFoundError(f"Model artifact not found at: {model_path}")
    if not spec_path.exists():
        raise FileNotFoundError(f"Feature spec not found at: {spec_path}")

    cache_key = (
        str(model_path.resolve()),
        model_path.stat().st_mtime_ns,
        str(spec_path.resolve()),
        spec_path.stat().st_mtime_ns,
    )
    if not force_reload and _BUNDLE_CACHE["key"] == cache_key and _BUNDLE_CACHE["model"] is not None:
        return _BUNDLE_CACHE["model"], _BUNDLE_CACHE["spec"]

    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    validate_feature_spec(spec)
    model = joblib.load(model_path)

    _BUNDLE_CACHE["key"] = cache_key
    _BUNDLE_CACHE["model"] = model
    _BUNDLE_CACHE["spec"] = spec
    return model, spec


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        load_champion_bundle()
    except FileNotFoundError:
        # Allow container boot even before initial training export; /health will report 503 until available.
        pass
    yield


app = FastAPI(
    title="Skill Demand Intelligence ML API",
    description="Single Champion salary estimation service (FastAPI, D19).",
    version="1.0.0",
    lifespan=lifespan,
)


def require_ml_key(x_ml_key: Optional[str] = Header(default=None, alias="X-ML-Key")) -> None:
    """Enforce X-ML-Key shared secret when ML_API_KEY is configured."""
    expected = os.environ.get("ML_API_KEY", "").strip()
    if not expected:
        return
    if not x_ml_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-ML-Key header",
        )
    if not hmac.compare_digest(x_ml_key, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid X-ML-Key header",
        )


class SalaryPredictRequest(BaseModel):
    """Input feature payload for single salary estimation (no gender, age, or company)."""

    model_config = ConfigDict(extra="forbid")

    occupation_cluster: str = Field(..., min_length=1)
    province_th: str = Field(default="ทั้งประเทศ")
    region: Optional[str] = Field(default=None)
    experience_band: str = Field(default="ไม่ระบุ/ไม่จำเป็น")
    education_level: str = Field(default="ไม่ระบุ")
    employment_type: str = Field(default="FULL_TIME")
    industry: str = Field(default="อื่นๆ")
    skills: list[str] = Field(default_factory=list)
    n_skills: Optional[int] = Field(default=None, ge=0)

    @model_validator(mode="before")
    @classmethod
    def _reject_forbidden_fairness_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            reject_forbidden_payload(data)
        return data


class BatchPredictRequest(BaseModel):
    """Batch salary estimation payload (used by /salary skill uplift meter)."""

    model_config = ConfigDict(extra="forbid")

    items: list[SalaryPredictRequest] = Field(..., min_length=1, max_length=100)


class SalaryPredictResponse(BaseModel):
    p25: float
    p50: float
    p75: float
    model_name: str
    mae: Optional[float] = None
    mape: Optional[float] = None
    cv_mae: Optional[float] = None
    cv_mape: Optional[float] = None
    n_support: Optional[int] = None
    out_of_domain: bool


class BatchPredictResponse(BaseModel):
    predictions: list[SalaryPredictResponse]
    model_name: str
    count: int


@app.get("/health")
def health() -> dict[str, Any]:
    """Public health & readiness endpoint (no auth header required)."""
    try:
        _, spec = load_champion_bundle()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Champion model unavailable: {exc}",
        ) from exc

    model_name = str(spec.get("champion_model") or "unknown")
    return {
        "status": "ok",
        "model": model_name,
        "model_name": model_name,
        "dataset_version": spec.get("dataset_version"),
        "n_rows": spec.get("n_rows"),
        "trained_at": spec.get("trained_at"),
    }


@app.post("/predict", response_model=SalaryPredictResponse, dependencies=[Depends(require_ml_key)])
def predict(req: SalaryPredictRequest) -> dict[str, Any]:
    """Estimate salary p25-p75 interval for one feature profile using the Champion model."""
    try:
        model, spec = load_champion_bundle()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    preds = predict_salary_records(model, spec, [req.model_dump()])
    return preds[0]


@app.post("/predict/batch", response_model=BatchPredictResponse, dependencies=[Depends(require_ml_key)])
def predict_batch(req: BatchPredictRequest) -> dict[str, Any]:
    """Estimate salary intervals for a batch of feature profiles in one request."""
    try:
        model, spec = load_champion_bundle()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    records = [item.model_dump() for item in req.items]
    preds = predict_salary_records(model, spec, records)
    return {
        "predictions": preds,
        "model_name": str(spec.get("champion_model") or "Champion"),
        "count": len(preds),
    }
