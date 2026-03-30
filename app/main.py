from fastapi import FastAPI

from app.api.routes import router as api_router

app = FastAPI(title="Phase 0 RAG API")
app.include_router(api_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Phase 0 RAG API is running", "health": "/health"}


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
