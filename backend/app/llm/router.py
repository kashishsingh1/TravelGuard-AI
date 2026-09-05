"""LLM Router with configurable 3-tier fallback orchestration (Groq -> OpenRouter -> Gemini)."""

import logging
from typing import Any, Dict, List, Optional

from app.config import Settings, get_settings
from app.llm.base import BaseLLMProvider, LLMProviderError, LLMResponse
from app.llm.gemini import GeminiProvider
from app.llm.groq import GroqProvider
from app.llm.openrouter import OpenRouterProvider

logger = logging.getLogger("travelguard.llm")


class LLMService:
    """
    Orchestrates LLM completions across a multi-tier provider chain:
    Primary: Groq -> Fallback 1: OpenRouter -> Fallback 2: Gemini -> ALL_LLM_PROVIDERS_FAILED
    """

    def __init__(
        self,
        providers: Optional[List[BaseLLMProvider]] = None,
        settings: Optional[Settings] = None,
    ):
        self.settings = settings or get_settings()

        if providers is not None:
            self.providers = providers
        else:
            self.providers = self._build_providers_from_config()

    def _build_providers_from_config(self) -> List[BaseLLMProvider]:
        """Build provider instances according to configured provider order."""
        provider_map = {
            "groq": lambda: GroqProvider(
                api_key=self.settings.GROQ_API_KEY,
                model=self.settings.GROQ_MODEL,
                base_url=self.settings.GROQ_BASE_URL,
            ),
            "openrouter": lambda: OpenRouterProvider(
                api_key=self.settings.OPENROUTER_API_KEY,
                model=self.settings.OPENROUTER_MODEL,
                base_url=self.settings.OPENROUTER_BASE_URL,
            ),
            "gemini": lambda: GeminiProvider(
                api_key=self.settings.GEMINI_API_KEY,
                model=self.settings.GEMINI_MODEL,
                base_url=self.settings.GEMINI_BASE_URL,
            ),
        }

        built: List[BaseLLMProvider] = []
        for name in self.settings.provider_order_list:
            factory = provider_map.get(name.lower())
            if factory:
                built.append(factory())
            else:
                logger.warning(f"[LLM] Unknown provider '{name}' in LLM_PROVIDER_ORDER; skipped.")

        # Fallback to standard 3-tier default if none matched
        if not built:
            built = [
                provider_map["groq"](),
                provider_map["openrouter"](),
                provider_map["gemini"](),
            ]
        return built

    @property
    def primary(self) -> BaseLLMProvider:
        """First provider in the configured chain."""
        return self.providers[0]

    @property
    def fallbacks(self) -> List[BaseLLMProvider]:
        """Subsequent fallback providers in the chain."""
        return self.providers[1:]

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 150,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """
        Execute completion through provider chain with sequential fallback.
        Logs each attempt and reason for failure.
        """
        logger.info("[LLM] Request started")
        failures = []

        for idx, provider in enumerate(self.providers, start=1):
            logger.info(f"[LLM] Provider {idx}: {provider.name.capitalize()}")
            logger.info(f"[LLM] Model: {provider.model}")

            try:
                response = await provider.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                logger.info(f"[LLM] Status: SUCCESS (provider: {provider.name})")
                # Mark fallback_used if not the primary provider
                response.fallback_used = (idx > 1)
                return response
            except Exception as exc:
                reason = getattr(exc, "message", str(exc))
                logger.warning(f"[LLM] Status: FAILED")
                logger.warning(f"[LLM] Reason: {reason}")
                failures.append(f"{provider.name}: {reason}")

        # All providers in the chain failed
        joined_reasons = "; ".join(failures)
        logger.error(f"[LLM] ALL_LLM_PROVIDERS_FAILED. Details: {joined_reasons}")
        raise LLMProviderError(
            provider="router",
            message=f"ALL_LLM_PROVIDERS_FAILED: {joined_reasons}",
            status_code=502,
        )

    async def health(self) -> Dict[str, Any]:
        """
        Validate connectivity for all configured tiers in the chain.
        Returns detailed status for primary and fallbacks without exposing secrets.
        """
        logger.info("[LLM] Health check started across configured providers")
        statuses = []
        any_available = False

        for provider in self.providers:
            info: Dict[str, Any] = {
                "provider": provider.name,
                "model": provider.model,
            }
            if not getattr(provider, "api_key", None):
                info["status"] = "unconfigured"
                info["error"] = f"API key not set for {provider.name}"
            else:
                try:
                    await provider.health_check()
                    info["status"] = "available"
                    any_available = True
                except Exception as exc:
                    reason = getattr(exc, "message", str(exc))
                    info["status"] = "failed"
                    info["error"] = reason

            statuses.append(info)

        primary_info = statuses[0] if statuses else {"provider": "none", "status": "unconfigured"}
        fallbacks_info = statuses[1:] if len(statuses) > 1 else []

        return {
            "success": any_available,
            "primary": primary_info,
            "fallbacks": fallbacks_info,
        }


_llm_service_instance: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """FastAPI dependency for accessing the LLM service."""
    global _llm_service_instance
    if _llm_service_instance is None:
        _llm_service_instance = LLMService()
    return _llm_service_instance
