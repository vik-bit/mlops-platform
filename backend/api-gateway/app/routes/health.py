from fastapi import APIRouter

from app.utils.jwt_handler import create_access_token


router = APIRouter()


@router.get("/health")
def health():

    return {
        "status": "gateway-running"
    }




    token = create_access_token({
        "user": "admin"
    })

    return {
        "access_token": token,
        "token_type": "bearer"
    }