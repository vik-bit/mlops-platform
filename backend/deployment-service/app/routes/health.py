from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    return {
        "service": "deployment-service",
        "status": "healthy"
    }