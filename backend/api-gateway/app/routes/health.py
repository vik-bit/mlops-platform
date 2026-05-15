from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    return {
        "service": "api-gateway",
        "status": "healthy"
    }