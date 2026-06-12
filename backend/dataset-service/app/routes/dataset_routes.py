from fastapi import (
    APIRouter,
    Depends,
    UploadFile,
    File,
    HTTPException
)

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
    file_path = save_uploaded_file(file)

    dataset = Dataset(
        filename=file.filename,
        path=file_path
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

    try:
        return profile_dataset(dataset.path, target_column)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dataset file not found on disk")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))