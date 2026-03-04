from fastapi import FastAPI
from app.api import health, events, reprocess

def create_app():
    app = FastAPI(title="Transaction Extraction Service")

    app.include_router(health.router, prefix="/health")
    app.include_router(events.router, prefix="/events")
    app.include_router(reprocess.router, prefix="/reprocess")

    return app

app = create_app()