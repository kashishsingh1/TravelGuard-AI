"""System health check API endpoint."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
async def health_check():
    """System health probe returning simple status indicator."""
    return {"status": "ok"}
