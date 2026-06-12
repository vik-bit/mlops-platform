from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Request

from sqlalchemy.orm import Session

from shared.database import SessionLocal
from shared.schemas.auth import RegisterRequest
from app.utils.password import hash_password

from shared.models.user import User

from fastapi.security import HTTPBearer

security = HTTPBearer()
from shared.schemas.auth import (
    LoginRequest,
    LoginResponse
)

from app.utils.password import verify_password
from app.utils.jwt_handler import create_access_token


router = APIRouter(tags=["Authentication"])


def get_db():

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


@router.post(
    "/login",
    response_model=LoginResponse
)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):

    user = db.query(User).filter(
        User.username == request.username
    ).first()

    if not user:

        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    if not verify_password(
        request.password,
        user.password_hash
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    token = create_access_token(
        {
            "user_id": user.id,
            "username": user.username,
            "role": user.role
        }
    )

    return {
        "access_token": token,
        "token_type": "bearer"
    }

from fastapi import Security

@router.get("/me")
def me(
    request: Request,
    credentials = Security(security)
):
    return request.state.user

@router.post("/users")
def create_user(
    request: Request,
    user_data: RegisterRequest,
    db: Session = Depends(get_db)
):

    if request.state.user.get("role") != "admin":

        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    existing = db.query(User).filter(
        User.username == user_data.username
    ).first()

    if existing:

        raise HTTPException(
            status_code=400,
            detail="Username already exists"
        )

    user = User(
        username=user_data.username,
        password_hash=hash_password(
            user_data.password
        ),
        role=user_data.role
    )

    db.add(user)

    db.commit()

    return {
        "message": "User created"
    }
@router.get("/users")
def list_users(
    request: Request,
    db: Session = Depends(get_db)
):

    if request.state.user.get("role") != "admin":

        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    users = db.query(User).all()

    return [
        {
            "id": u.id,
            "username": u.username,
            "role": u.role
        }
        for u in users
    ]