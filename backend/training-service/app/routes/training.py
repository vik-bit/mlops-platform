import json
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from threading import Thread
import requests

from shared.database import SessionLocal
from shared.models.training_job import TrainingJob
from shared.models.model_registry import ModelRegistry
from shared.schemas.training import TrainingRequest, TrainingResponse
from shared.schemas.prediction import PredictionRequest, PredictionResponse

from app.services.data_loader import load_dataset
from app.services.trainer import train_model
from app.services.model_saver import save_model
from app.services.predictor import predict
from app.utils.mlflow_logger import log_training


router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Background training ───────────────────────────────────────────────────────

def background_training(
    job_id: int,
    dataset_id: int,
    target_column: str,
    model_type: str,
    task_type: str = "classification",
    hyperparameters: dict | None = None,
):
    db = SessionLocal()
    try:
        job = db.query(TrainingJob).filter(TrainingJob.id == job_id).first()
        if not job:
            return

        job.status = "running"
        db.commit()

        # Fetch dataset
        response = requests.get(f"http://dataset-service:8000/datasets/{dataset_id}")
        if response.status_code != 200:
            raise Exception("Dataset service unavailable")

        dataset_path = response.json()["path"]
        df = load_dataset(dataset_path)

        # Train — returns full TrainingResult
        result = train_model(
            df,
            target_column,
            model_type=model_type,
            task_type=task_type,
            hyperparameters=hyperparameters,
        )

        # Save pipeline
        model_path = save_model(result.pipeline, job_id)

        # Save feature importance + training distribution baseline into metadata
        metadata_path = None
        if result.feature_importance:
            metadata_path = model_path.replace(".pkl", "_metadata.json")

            # Compute per-feature distribution stats for drift baseline
            training_distribution = {}
            X = df.drop(columns=[target_column, "id"], errors="ignore")
            for col in X.columns:
                series = X[col].dropna()
                if pd.api.types.is_numeric_dtype(series):
                    training_distribution[col] = {
                        "type":   "numeric",
                        "mean":   round(float(series.mean()), 6),
                        "std":    round(float(series.std()), 6),
                        "min":    round(float(series.min()), 6),
                        "max":    round(float(series.max()), 6),
                        "p25":    round(float(series.quantile(0.25)), 6),
                        "p50":    round(float(series.quantile(0.50)), 6),
                        "p75":    round(float(series.quantile(0.75)), 6),
                        "p95":    round(float(series.quantile(0.95)), 6),
                        # Store histogram for PSI computation
                        "hist_counts": [int(v) for v in
                                        pd.cut(series, bins=10).value_counts(sort=False).values],
                        "hist_edges":  [round(float(v), 6) for v in
                                        pd.cut(series, bins=10, retbins=True)[1]],
                    }
                else:
                    vc = series.value_counts(normalize=True)
                    training_distribution[col] = {
                        "type":        "categorical",
                        "frequencies": {str(k): round(float(v), 6) for k, v in vc.items()},
                    }

            with open(metadata_path, "w") as f:
                json.dump({
                    "feature_importance":      result.feature_importance,
                    "model_type":              model_type,
                    "task_type":               task_type,
                    "hyperparameters":         hyperparameters,
                    "training_distribution":   training_distribution,
                    "training_rows":           len(df),
                }, f)

        # Register model
        registry_entry = ModelRegistry(
            training_job_id=job.id,
            model_name=f"{model_type}_model",
            model_version="v1",
            model_path=model_path,
            metadata_path=metadata_path,
            stage="staging",
            accuracy=str(round(result.accuracy, 4)) if result.accuracy is not None else None,
        )
        db.add(registry_entry)
        db.commit()

        # Log to MLflow
        run_id = log_training(
            model_type=model_type,
            accuracy=result.accuracy or 0.0,
            hyperparameters=hyperparameters,
            extra_metrics={
                "precision": result.precision,
                "recall":    result.recall,
                "f1":        result.f1,
                "r2":        result.r2,
                "mae":       result.mae,
                "rmse":      result.rmse,
                "cv_mean":   result.cv_mean,
                "cv_std":    result.cv_std,
            },
        )

        db.refresh(job)

        # Update job with ALL metrics
        job.status          = "completed"
        job.accuracy        = result.accuracy
        job.precision       = result.precision
        job.recall          = result.recall
        job.f1_score        = result.f1
        job.r2_score        = result.r2
        job.mae             = result.mae
        job.rmse            = result.rmse
        job.cv_mean         = result.cv_mean
        job.cv_std          = result.cv_std
        job.mlflow_run_id   = run_id
        job.hyperparameters = json.dumps(hyperparameters or {})

        db.commit()
        print(f"[Job {job_id}] Training complete | acc={result.accuracy} | cv={result.cv_mean}±{result.cv_std}")

    except Exception as e:
        import traceback
        print(f"========== TRAINING ERROR [Job {job_id}] ==========")
        traceback.print_exc()
        db.rollback()
        failed_job = db.query(TrainingJob).filter(TrainingJob.id == job_id).first()
        if failed_job:
            failed_job.status = "failed"
            failed_job.error_message = str(e)
            db.commit()
    finally:
        db.close()


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/train", response_model=TrainingResponse)
def start_training(request: TrainingRequest, db: Session = Depends(get_db)):
    job = TrainingJob(
        dataset_id=request.dataset_id,
        model_type=request.model_type,
        task_type=request.task_type,
        target_column=request.target_column,
        status="queued",
        hyperparameters=json.dumps(request.hyperparameters or {}),
    )
    db.add(job)
    db.commit()

    assigned_job_id = job.id

    Thread(
        target=background_training,
        args=(assigned_job_id, request.dataset_id, request.target_column,
              request.model_type, request.task_type, request.hyperparameters),
    ).start()

    return _job_to_dict(job)


@router.get("/models")
def list_models(db: Session = Depends(get_db)):
    return db.query(ModelRegistry).all()


@router.get("/training/{job_id}")
def get_training_status(job_id: int, db: Session = Depends(get_db)):
    job = db.query(TrainingJob).filter(TrainingJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_dict(job)


@router.get("/training")
def list_training_jobs(db: Session = Depends(get_db)):
    jobs = db.query(TrainingJob).order_by(TrainingJob.id.desc()).all()
    return [_job_to_dict(j) for j in jobs]


@router.delete("/training/{job_id}")
def delete_training_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(TrainingJob).filter(TrainingJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    has_relations = db.query(ModelRegistry).filter(
        ModelRegistry.training_job_id == job_id
    ).first()
    if has_relations:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete job {job_id}: it has a registered model. Delete the model first.",
        )

    db.delete(job)
    db.commit()
    return {"message": f"Training job {job_id} deleted"}


@router.put("/training/{job_id}/cancel")
def cancel_training_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(TrainingJob).filter(TrainingJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status in ("completed", "failed", "cancelled"):
        return {"message": f"Job already {job.status}"}
    job.status = "cancelled"
    db.commit()
    return {"message": f"Training job {job_id} cancelled"}


@router.post("/predict", response_model=PredictionResponse)
def make_prediction(request: PredictionRequest):
    try:
        prediction = predict(request.model_id, request.features)
        return {"prediction": str(prediction)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Feature importance ────────────────────────────────────────────────────────

@router.get("/models/{model_id}/feature-importance")
def get_feature_importance(model_id: int, db: Session = Depends(get_db)):
    model = db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    if not model.metadata_path:
        raise HTTPException(status_code=404, detail="No metadata for this model")
    try:
        with open(model.metadata_path) as f:
            meta = json.load(f)
        return {"model_id": model_id, "feature_importance": meta.get("feature_importance", {})}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Metadata file not found")


# ── Job / Model comparison ────────────────────────────────────────────────────

@router.get("/jobs/compare")
def compare_jobs(
    ids: str,
    db: Session = Depends(get_db),
):
    """
    Side-by-side comparison of training jobs.
    GET /jobs/compare?ids=1,2,3
    Returns all metrics for each job so the frontend can render a comparison table.
    """
    try:
        job_ids = [int(x.strip()) for x in ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=422, detail="ids must be comma-separated integers")

    if not job_ids:
        raise HTTPException(status_code=422, detail="Provide at least one job id")

    results = []
    for jid in job_ids:
        job = db.query(TrainingJob).filter(TrainingJob.id == jid).first()
        if not job:
            continue

        entry = _job_to_dict(job)

        # Attach registered model info if present
        model = db.query(ModelRegistry).filter(
            ModelRegistry.training_job_id == jid
        ).first()
        if model:
            entry["model_id"]      = model.id
            entry["model_name"]    = model.model_name
            entry["model_version"] = model.model_version
            entry["stage"]         = model.stage

            # Pull feature importance from metadata
            if model.metadata_path:
                try:
                    with open(model.metadata_path) as f:
                        meta = json.load(f)
                    entry["feature_importance"] = meta.get("feature_importance", {})
                except Exception:
                    pass

        results.append(entry)

    # Highlight best per metric
    def _best(key, fn, results):
        candidates = [r for r in results if r.get(key) is not None]
        if not candidates:
            return None
        best = fn(candidates, key=lambda x: float(x[key] or 0))
        return best.get("id")

    return {
        "jobs":  results,
        "count": len(results),
        "best_by": {
            "accuracy": _best("accuracy",  max, results),
            "f1_score": _best("f1_score",  max, results),
            "cv_mean":  _best("cv_mean",   max, results),
            "rmse":     _best("rmse",      min, results),
            "mae":      _best("mae",       min, results),
        },
    }


# ── Helper ────────────────────────────────────────────────────────────────────

def _job_to_dict(job: TrainingJob) -> dict:
    h_params = job.hyperparameters
    if isinstance(h_params, str):
        try:
            h_params = json.loads(h_params)
        except Exception:
            h_params = {}

    return {
        "id":            job.id,
        "dataset_id":    job.dataset_id,
        "model_type":    job.model_type,
        "task_type":     job.task_type,
        "target_column": job.target_column,
        "status":        job.status,
        "accuracy":      str(round(job.accuracy, 4)) if job.accuracy is not None else None,
        "precision":     job.precision,
        "recall":        job.recall,
        "f1_score":      job.f1_score,
        "r2_score":      job.r2_score,
        "mae":           job.mae,
        "rmse":          job.rmse,
        "cv_mean":       job.cv_mean,
        "cv_std":        job.cv_std,
        "hyperparameters": h_params or {},
        "mlflow_run_id": job.mlflow_run_id,
        "error_message": job.error_message,
        "created_at":    getattr(job, "created_at", None),
    }