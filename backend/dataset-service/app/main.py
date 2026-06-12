from fastapi import FastAPI

from shared.database import engine, Base

from app.routes.dataset_routes import router


Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Dataset Service"
)

app.include_router(router)


@app.get("/health")
def health():

    return {
        "status": "ok"
    }