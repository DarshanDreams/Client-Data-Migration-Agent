from fastapi import FastAPI

from app.api.routes import router
from app.config import settings
from app.observability.logging import configure_logging


configure_logging(settings.log_level)

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "Autonomous client-data migration agent "
        "with human-in-the-loop escalation."
    ),
)

app.include_router(router)


@app.get("/")
def root():
    return {
        "service": settings.app_name,
        "status": "running",
        "docs": "/docs",
    }
