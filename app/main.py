"""Entry point for the SMARTROSE FastAPI backend."""

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging_config import configure_logging
from app.db.mongodb import close_db, init_db
from app.ml.inm.inm_inference import is_model_available as inm_model_available

# Configure application-wide logging as soon as the app loads
configure_logging()
logger = logging.getLogger(__name__)

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


@app.on_event("startup")
async def on_startup() -> None:
    """Warm up Mongo connection and verify reachability with a ping."""
    try:
        await init_db()
        # Verification log: confirm INM ML model availability at startup (DEV safety check)
        available = inm_model_available()
        logger.info("INM ML model availability check", extra={"ml_model_loaded": available})
        logger.info("Startup checks completed")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Startup failed during Mongo initialization")
        raise exc


@app.on_event("shutdown")
async def on_shutdown() -> None:
    """Close Mongo client cleanly."""
    await close_db()


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Log every HTTPException so error responses are traceable."""
    logger.error(
        "HTTP exception",
        extra={"path": request.url.path, "status_code": exc.status_code},
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Log request validation errors for visibility."""
    logger.error(
        "Request validation error",
        extra={"path": request.url.path, "errors": exc.errors()},
    )
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all logger for unexpected errors to satisfy request error logging."""
    logger.exception(
        "Unhandled server error",
        extra={"path": request.url.path},
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.get("/health", tags=["health"])
async def health() -> dict:
    """Simple liveness probe to confirm the service is up."""
    return {"status": "ok", "message": "SMARTROSE backend healthy"}


# Mount versioned API routes under /api
app.include_router(api_router, prefix="/api")









