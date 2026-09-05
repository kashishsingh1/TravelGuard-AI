"""LLM Router with observable primary (DeepSeek) to fallback (Grok) orchestration."""

import logging
from typing import Any, Dict, Optional

from app.config import Settings, get_settings
from app.llm.base import BaseLLMProvider, LLMProviderError, LLMResponse
from app.llm.deepseek import DeepSeekProvider
from app.llm.groq import GroqProvider

logger = logging.getLogger("travelguard.llm")


class LLMService:
    """Orchestrates LLM requests with resilient, observable fallback."""

    def __init__(
        self,
        primary: Optional[BaseLLMProvider] = None,
        fallback: Optional[BaseLLMProvider] = None,
        settings: Optional[Settings] = None,
    ):
        self.settings = settings or get_settings()
        self.primary = primary or DeepSeekProvider(
            api_key=self.settings.DEEPSEEK_API_KEY,
            model=self.settings.DEEPSEEK_MODEL,
            base_url=self.settings.DEEPSEEK_BASE_URL,
        )
        self.fallback = fallback or GroqProvider(
            api_key=self.settings.GROQ_API_KEY,
            model=self.settings.GROQ_MODEL,
            base_url=self.settings.GROQ_BASE_URL,
        )

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 150,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Call primary provider, automatically falling back to secondary upon failure."""
        logger.info(f"[LLM] Primary provider: {self.primary.name.capitalize()}")
        logger.info(f"[LLM] Model: {self.primary.model}")

        try:
            response = await self.primary.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            logger.info(f"[LLM] Success ({self.primary.name})")
            return response
        except Exception as exc:
            reason = getattr(exc, "message", str(exc))
            logger.warning(f"[LLM] Request failed: {reason}")
            logger.info(f"[LLM] Falling back to {self.fallback.name.capitalize()}")
            logger.info(f"[LLM] Model: {self.fallback.model}")

            try:
                response = await self.fallback.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                response.fallback_used = True
                logger.info(f"[LLM] Success (fallback: {self.fallback.name})")
                return response
            except Exception as fallback_exc:
                fallback_reason = getattr(fallback_exc, "message", str(fallback_exc))
                logger.error(f"[LLM] Fallback provider failed: {fallback_reason}")
                raise LLMProviderError(
                    provider="router",
                    message=(
                        f"Both primary ({self.primary.name}) and fallback ({self.fallback.name}) failed. "
                        f"Primary error: {reason}. Fallback error: {fallback_reason}"
                    ),
                    status_code=502,
                ) from fallback_exc

    async def health(self) -> Dict[str, Any]:
        """Perform a minimal health check query across providers."""
        logger.info(f"[LLM] Health check: testing Primary provider ({self.primary.name})")
        logger.info(f"[LLM] Model: {self.primary.model}")

        try:
            await self.primary.health_check()
            logger.info(f"[LLM] Health check: Primary ({self.primary.name}) is healthy")
            return {
                "success": True,
                "provider": self.primary.name,
                "model": self.primary.model,
            }
        except Exception as primary_exc:
            reason = getattr(primary_exc, "message", str(primary_exc))
            logger.warning(f"[LLM] Request failed: {reason}")
            logger.info(f"[LLM] Falling back to {self.fallback.name.capitalize()}")
            logger.info(f"[LLM] Model: {self.fallback.model}")

            try:
                await self.fallback.health_check()
                logger.info(f"[LLM] Success (fallback: {self.fallback.name})")
                return {
                    "success": True,
                    "provider": self.fallback.name,
                    "model": self.fallback.model,
                    "fallback_used": True,
                }
            except Exception as fallback_exc:
                fallback_reason = getattr(fallback_exc, "message", str(fallback_exc))
                logger.error(f"[LLM] Both providers failed: primary='{reason}', fallback='{fallback_reason}'")
                return {
                    "success": False,
                    "error": (
                        f"Primary ({self.primary.name}) failed: {reason}. "
                        f"Fallback ({self.fallback.name}) failed: {fallback_reason}"
                    ),
                }


_llm_service_instance: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """FastAPI dependency for accessing the LLM service."""
    global _llm_service_instance
    if _llm_service_instance is None:
        _llm_service_instance = LLMService()
    return _llm_service_instance
