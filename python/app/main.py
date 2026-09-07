from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import settings
from app.rag.memory_summary import start_memory_summary_worker, stop_memory_summary_worker


app = FastAPI(title=settings.app_name, debug=settings.debug)
origins = ["*"] if settings.cors_origins == "*" else [item.strip() for item in settings.cors_origins.split(",") if item.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.on_event("startup")
def start_background_workers() -> None:
    start_memory_summary_worker()


@app.on_event("shutdown")
def stop_background_workers() -> None:
    stop_memory_summary_worker()


@app.get("/actuator/health")
def health() -> dict:
    return {"status": "UP", "service": settings.app_name}


@app.get("/")
def root() -> dict:
    return {"name": settings.app_name, "docs": "/docs", "health": "/actuator/health"}
