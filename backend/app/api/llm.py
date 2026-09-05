"""LLM infrastructure health and validation endpoint."""

from fastapi import APIRouter, Depends

from app.llm.router import LLMService, get_llm_service

router = APIRouter(prefix="/api/llm", tags=["llm"])


@router.get("/health")
async def llm_health(llm_service: LLMService = Depends(get_llm_service)):
    """
    Validate LLM provider connectivity.
    Pings Primary (DeepSeek), falling back to Secondary (Grok).
    Returns provider metadata without exposing credentials.
    """
    result = await llm_service.health()
    return result
