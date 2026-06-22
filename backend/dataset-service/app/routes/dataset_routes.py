import io
import tempfile
import os
from fastapi import (
    APIRouter,
    Depends,
    UploadFile,
    File,
    HTTPException
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from shared.database import SessionLocal
from shared.models.dataset import Dataset
from shared.schemas.dataset import DatasetResponse
from app.services.file_handler import save_uploaded_file
from app.services.profile_dataset import profile_dataset


router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Upload ────────────────────────────────────────────────────────────────────

@router.post("/datasets", response_model=DatasetResponse)
def upload_dataset(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # Store raw bytes in Postgres — no local disk, no S3, no credit card.
    # Dataset.content (LargeBinary column) holds the file; Dataset.path
    # is kept for compatibility but no longer used for file access.
    content = save_uploaded_file(file)

    dataset = Dataset(
        filename=file.filename,
        path=file.filename,   # kept for schema compatibility; real data is in .content
        content=content,
    )

    db.add(dataset)
    db.commit()
    db.refresh(dataset)

    return dataset


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("/datasets")
def list_datasets(db: Session = Depends(get_db)):
    return db.query(Dataset).all()


# ── Get ───────────────────────────────────────────────────────────────────────

@router.get("/datasets/{dataset_id}", response_model=DatasetResponse)
def get_dataset(dataset_id: int, db: Session = Depends(get_db)):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset


# ── Download ──────────────────────────────────────────────────────────────────

@router.get("/datasets/{dataset_id}/download")
def download_dataset(dataset_id: int, db: Session = Depends(get_db)):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    if not dataset.content:
        raise HTTPException(status_code=404, detail="Dataset file not found")

    return StreamingResponse(
        io.BytesIO(dataset.content),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={dataset.filename}"},
    )


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/datasets/{dataset_id}")
def delete_dataset(dataset_id: int, db: Session = Depends(get_db)):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    db.delete(dataset)
    db.commit()
    return {"message": f"Dataset {dataset_id} deleted"}


# ── Profile ───────────────────────────────────────────────────────────────────

@router.get("/datasets/{dataset_id}/profile")
def get_dataset_profile(
    dataset_id: int,
    target_column: str = None,
    db: Session = Depends(get_db)
):
    """
    Returns a full profile of the dataset:
    - row/column counts
    - per-column: dtype, missing %, unique count, top values, min/max/mean/std
    - if target_column provided: class distribution + imbalance warning
    """
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    if not dataset.content:
        raise HTTPException(status_code=404, detail="Dataset file not found")

    # profile_dataset() expects a file path — write to a temp file, profile
    # it, then let the OS clean it up automatically when the context exits.
    try:
        suffix = os.path.splitext(dataset.filename)[1] or ".csv"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
            tmp.write(dataset.content)
            tmp.flush()
            return profile_dataset(tmp.name, target_column)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))