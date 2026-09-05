"""Main FastAPI application for SkyBook and TravelGuard foundation."""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.booking import router as booking_router
from app.api.flights import router as flights_router
from app.api.health import router as health_router
from app.api.llm import router as llm_router
from app.api.metrics import router as metrics_router
from app.api.travelguard import router as travelguard_router
from app.config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("travelguard")

settings = get_settings()

app = FastAPI(
    title="SkyBook API — TravelGuard SUT",
    description="System Under Test (SUT) backend and LLM provider integration for TravelGuard AI.",
    version="0.1.0",
)

# Enable CORS for frontend applications
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(health_router)
app.include_router(flights_router)
app.include_router(booking_router)
app.include_router(llm_router)
app.include_router(metrics_router)
app.include_router(travelguard_router)


@app.get("/")
async def root():
    """Root metadata endpoint."""
    return {
        "app": "SkyBook Travel API",
        "role": "System Under Test (SUT) for TravelGuard AI",
        "increment": 1,
        "docs_url": "/docs",
    }
