import sys
import time
import io
import json

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from shared.database import SessionLocal
from shared.models.deployment import Deployment
from shared.models.model_registry import ModelRegistry
from shared.schemas.deployment import (
    DeployResponse,
    PredictionInput,
    NamedPredictionInput,
    PredictionResponse,
    BatchPredictionResponse,
)

from app.services.model_loader import load_model
from app.services.logger import log_prediction
from app.services.explainer import compute_shap

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Deploy ────────────────────────────────────────────────────────────────────

@router.post("/deploy/{model_id}", response_model=DeployResponse)
def deploy_model(model_id: int, db: Session = Depends(get_db)):
    model = db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    model.stage = "production"
    deployment = Deployment(
        model_id=model.id,
        status="active",
        endpoint=f"/predict/{model.id}",
    )
    db.add(deployment)
    db.commit()
    db.refresh(deployment)

    return {"message": "Model deployed successfully", "endpoint": deployment.endpoint}


# ── List / Delete deployments ─────────────────────────────────────────────────

@router.get("/deployments")
def list_deployments(db: Session = Depends(get_db)):
    return db.query(Deployment).all()


@router.delete("/deploy/{deployment_id}")
def undeploy_model(deployment_id: int, db: Session = Depends(get_db)):
    dep = db.query(Deployment).filter(Deployment.id == deployment_id).first()
    if not dep:
        raise HTTPException(status_code=404, detail="Deployment not found")
    db.delete(dep)
    db.commit()
    return {"message": "Deployment removed successfully"}


# ── Online prediction (positional) — legacy ───────────────────────────────────

@router.post("/predict/{model_id}")
def predict_positional(
    model_id: int,
    request: PredictionInput,
    db: Session = Depends(get_db),
):
    t0 = time.time()
    model_entry = _get_model_or_404(model_id, db)
    pipeline = load_model(model_entry.model_path)

    try:
        prediction = pipeline.predict([request.features])[0]
        latency = round((time.time() - t0) * 1000, 2)
        _log(model_id, {"features": request.features}, prediction, latency, "success")
        return {"prediction": str(prediction), "latency_ms": latency}
    except Exception as e:
        _log(model_id, {"features": request.features}, None, 0, "failed")
        raise HTTPException(status_code=500, detail=str(e))


# ── Online prediction (named features) — preferred ────────────────────────────

@router.post("/predict/{model_id}/named", response_model=PredictionResponse)
def predict_named(
    model_id: int,
    request: NamedPredictionInput,
    db: Session = Depends(get_db),
):
    t0 = time.time()
    model_entry = _get_model_or_404(model_id, db)
    pipeline = load_model(model_entry.model_path)

    try:
        input_df = pd.DataFrame([request.features])
        prediction = pipeline.predict(input_df)[0]
        latency = round((time.time() - t0) * 1000, 2)

        probability = None
        if request.return_proba:
            model_step = pipeline.named_steps.get("model")
            if model_step and hasattr(model_step, "predict_proba"):
                proba = pipeline.predict_proba(input_df)[0]
                classes = [str(c) for c in model_step.classes_]
                probability = {cls: round(float(p), 4) for cls, p in zip(classes, proba)}

        _log(model_id, request.features, prediction, latency, "success")
        return PredictionResponse(
            prediction=_native(prediction),
            probability=probability,
            latency_ms=latency,
        )

    except Exception as e:
        _log(model_id, request.features, None, 0, "failed")
        raise HTTPException(status_code=500, detail=str(e))


# ── Batch prediction (CSV upload) ─────────────────────────────────────────────

@router.post("/predict/{model_id}/batch")
async def predict_batch(
    model_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    t0 = time.time()
    model_entry = _get_model_or_404(model_id, db)
    pipeline = load_model(model_entry.model_path)

    try:
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))
        original_df = df.copy()

        predictions = pipeline.predict(df)
        latency = round((time.time() - t0) * 1000, 2)

        original_df["prediction"] = [_native(p) for p in predictions]

        _log(model_id, f"batch:{len(df)}rows", f"{len(predictions)}predictions", latency, "success")

        output = io.StringIO()
        original_df.to_csv(output, index=False)
        output.seek(0)

        return StreamingResponse(
            io.BytesIO(output.getvalue().encode()),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=predictions_{model_id}.csv"},
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Model schema (feature names + types) ──────────────────────────────────────

@router.get("/predict/{model_id}/schema")
def get_prediction_schema(model_id: int, db: Session = Depends(get_db)):
    model_entry = _get_model_or_404(model_id, db)
    pipeline = load_model(model_entry.model_path)

    try:
        preprocessor = pipeline.named_steps["preprocessor"]
        schema = {}
        for name, transformer, cols in preprocessor.transformers_:
            for col in cols:
                schema[col] = "numeric" if name == "num" else "categorical"

        metadata = {}
        if model_entry.metadata_path:
            try:
                with open(model_entry.metadata_path) as f:
                    metadata = json.load(f)
            except Exception:
                pass

        return {
            "model_id":     model_id,
            "features":     schema,
            "model_type":   metadata.get("model_type"),
            "task_type":    metadata.get("task_type"),
            "top_features": list(metadata.get("feature_importance", {}).keys())[:10],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── SHAP explanation ──────────────────────────────────────────────────────────

@router.post("/predict/{model_id}/explain")
def explain_prediction(
    model_id: int,
    request: NamedPredictionInput,
    db: Session = Depends(get_db),
):
    model_entry = _get_model_or_404(model_id, db)

    # ── 1. Fast Path (Fixed Syntax Closing Error) ─────────────────────────────
    if model_entry.metadata_path:
        try:
            with open(model_entry.metadata_path) as f:
                meta = json.load(f)
            fi = meta.get("feature_importance") or meta.get("shap_global")
            if fi:
                input_df   = pd.DataFrame([request.features])
                pipeline   = load_model(model_entry.model_path)
                prediction = pipeline.predict(input_df)[0]
                return {
                    "model_id":          model_id,
                    "prediction":        _native(prediction),
                    "global_importance": fi,
                    "local_explanation": [], # Fast path fallback
                    "base_value":        meta.get("shap_base"),
                    "source":            "precomputed",
                }
        except Exception as meta_err:
            # Fall through to slow path if metadata reading fails
            pass

    # ── 2. Slow Path (Compute SHAP in Real-Time) ──────────────────────────────
    try:
        pipeline = load_model(model_entry.model_path)
        input_df = pd.DataFrame([request.features])

        # ── Fix: Background dataset scaling fallback ──────────────────────────
        # Instead of feeding input_df to background_df, we construct a tiny baseline distribution.
        # Ideally, substitute this with a training dataframe sample asset (e.g., training_df.sample(100))
        # As a safe placeholder fallback to prevent a 0-variance matrix crash:
        background_df = input_df.copy()
        if len(background_df) == 1:
            # Duplicate the row with minimal random jitter to prevent matrix variance errors
            jittered_row = background_df.copy()
            for col in jittered_row.select_dtypes(include=['number']).columns:
                jittered_row[col] = jittered_row[col] * 1.01
            background_df = pd.concat([background_df, jittered_row], ignore_index=True)

        result = compute_shap(
            pipeline=pipeline,
            background_df=background_df,
            explain_df=input_df,
        )

        # ── Fix: Surface deep SHAP inner exceptions explicitly ────────────────
        if "error" in result:
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "SHAP runtime evaluation failed.",
                    "error": result.get("error"),
                    "traceback": result.get("traceback")
                }
            )

        prediction = pipeline.predict(input_df)[0]

        return {
            "model_id":          model_id,
            "prediction":        _native(prediction),
            "global_importance": result.get("global_importance"),
            "local_explanation": result.get("local_explanation"),
            "base_value":        result.get("base_value"),
            "source":            "realtime",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SHAP failed: {str(e)}")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_model_or_404(model_id: int, db: Session) -> ModelRegistry:
    m = db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Model not found")
    return m


def _log(model_id, input_data, prediction, latency_ms, status):
    try:
        log_prediction(
            model_id=model_id,
            input_data=str(input_data),
            prediction=str(prediction),
            latency_ms=latency_ms,
            status=status,
        )
    except Exception:
        pass


def _native(val):
    if hasattr(val, "item"):
        return val.item()
    return val