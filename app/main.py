from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import health, com1, com2, com3, com4
from app.core.config import settings

app = FastAPI(
    title="SmartRose Backend API",
    description="FastAPI backend for SmartRose application",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(com1.router, prefix="/api/v1", tags=["com1"])
app.include_router(com2.router, prefix="/api/v1", tags=["com2"])
app.include_router(com3.router, prefix="/api/v1", tags=["com3"])
app.include_router(com4.router, prefix="/api/v1", tags=["com4"])


@app.get("/")
async def root():
    return {"message": "Welcome to SmartRose Backend API"}


