from fastapi import FastAPI

app = FastAPI(title="Phase 0 RAG API")


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Phase 0 RAG API is running", "health": "/health"}


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
