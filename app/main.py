"""Entry point for the SMARTROSE FastAPI backend."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging_config import configure_logging

# Configure application-wide logging as soon as the app loads
configure_logging()

# Create the FastAPI instance with basic metadata
app = FastAPI(
    title="SMARTROSE Backend",
    version=settings.api_version,
    description="API gateway for SMARTROSE data ingestion and predictions.",
)

# Allow cross-origin requests while prototyping; tighten for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
async def health() -> dict:
    """Simple liveness probe to confirm the service is up."""
    return {"status": "ok", "message": "SMARTROSE backend healthy"}


# Mount versioned API routes under /api
app.include_router(api_router, prefix="/api")

