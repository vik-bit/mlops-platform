from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.routes.gateway import router as gateway_router
from app.routes.health import router as health_router
from app.routes.auth import router as auth_router

from app.middleware.logging import LoggingMiddleware
from app.middleware.auth import AuthMiddleware

from shared.database import SessionLocal
from shared.models.user import User

from app.utils.password import hash_password
from fastapi.middleware.cors import CORSMiddleware
from shared.database import Base, engine


Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):

    db = SessionLocal()

    try:

        admin = db.query(User).filter(
            User.username == "admin"
        ).first()

        if not admin:

            admin = User(
                username="admin",
                password_hash=hash_password("admin123"),
                role="admin"
            )

            db.add(admin)

            db.commit()

            print("Admin user created")

    finally:
        db.close()

    yield


app = FastAPI(
    title="MLOps API Gateway",
    lifespan=lifespan
)

# CORS must be registered FIRST — before AuthMiddleware.
# FastAPI runs middleware in reverse order, so last-registered runs first.
# If AuthMiddleware runs before CORS, OPTIONS preflight gets a 401 with no
# CORS headers, causing "Failed to fetch" on every cross-origin POST/DELETE.
#
# FIX: allow_origins was missing the deployed Render frontend URL —
# only localhost entries were present, so every cross-origin request from
# https://mlops-frontend-5smr.onrender.com was correctly blocked by the
# browser (the gateway never even got a chance to reject it; CORS failures
# happen client-side before the request body is sent for a preflighted
# request). Added the real frontend origin below.
#
# NOTE: if you ever change the frontend's Render URL (e.g. redeploy under
# a different name/suffix), this list must be updated again — Render's
# .onrender.com URLs are not guaranteed stable across a full service
# recreate, only across normal redeploys of the same service.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "https://mlops-frontend-5smr.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(AuthMiddleware)

app.add_middleware(LoggingMiddleware)
app.include_router(health_router)

app.include_router(auth_router)



app.include_router(gateway_router)