"""LLM infrastructure health and validation endpoint."""

from fastapi import APIRouter, Depends

from app.llm.router import LLMService, get_llm_service

router = APIRouter(prefix="/api/llm", tags=["llm"])


@router.get("/health")
async def llm_health(llm_service: LLMService = Depends(get_llm_service)):
    """
    Validate LLM provider connectivity across configured tiers:
    Primary (Groq) -> Fallback 1 (OpenRouter) -> Fallback 2 (Gemini).
    Returns structured provider health without exposing credentials.
    """
    result = await llm_service.health()
    return result
