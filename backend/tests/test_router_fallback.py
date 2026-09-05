"""Automated tests proving the 3-tier provider fallback logic (Groq -> OpenRouter -> Gemini)."""

import pytest
from app.llm.base import BaseLLMProvider, LLMProviderError, LLMResponse
from app.llm.router import LLMService


class MockProvider(BaseLLMProvider):
    """Configurable mock provider for test isolation."""

    def __init__(self, name: str, model: str, should_succeed: bool = True, error_msg: str = "Provider error"):
        self.name = name
        self.model = model
        self.should_succeed = should_succeed
        self.error_msg = error_msg
        self.call_count = 0

    async def generate(self, prompt: str, system_prompt=None, max_tokens=150, temperature=0.7) -> LLMResponse:
        self.call_count += 1
        if not self.should_succeed:
            raise LLMProviderError(provider=self.name, message=self.error_msg, status_code=500)
        return LLMResponse(
            content=f"Response from {self.name}",
            provider=self.name,
            model=self.model,
            fallback_used=False,
            latency_ms=10.0,
        )

    async def health_check(self) -> LLMResponse:
        return await self.generate("ping")


@pytest.mark.asyncio
async def test_case_1_groq_succeeds():
    """CASE 1: Groq succeeds. Expected: Only Groq is used, no fallbacks attempted."""
    groq = MockProvider("groq", "openai/gpt-oss-120b", should_succeed=True)
    openrouter = MockProvider("openrouter", "openrouter/free", should_succeed=True)
    gemini = MockProvider("gemini", "gemini-3-flash-preview", should_succeed=True)

    service = LLMService(providers=[groq, openrouter, gemini])
    response = await service.generate("Test prompt")

    assert response.provider == "groq"
    assert response.model == "openai/gpt-oss-120b"
    assert response.fallback_used is False
    assert groq.call_count == 1
    assert openrouter.call_count == 0
    assert gemini.call_count == 0


@pytest.mark.asyncio
async def test_case_2_groq_fails_openrouter_succeeds():
    """CASE 2: Groq fails. Expected: OpenRouter is used, Gemini not attempted."""
    groq = MockProvider("groq", "openai/gpt-oss-120b", should_succeed=False, error_msg="rate_limit")
    openrouter = MockProvider("openrouter", "openrouter/free", should_succeed=True)
    gemini = MockProvider("gemini", "gemini-3-flash-preview", should_succeed=True)

    service = LLMService(providers=[groq, openrouter, gemini])
    response = await service.generate("Test prompt")

    assert response.provider == "openrouter"
    assert response.model == "openrouter/free"
    assert response.fallback_used is True
    assert groq.call_count == 1
    assert openrouter.call_count == 1
    assert gemini.call_count == 0


@pytest.mark.asyncio
async def test_case_3_groq_and_openrouter_fail_gemini_succeeds():
    """CASE 3: Groq fails, OpenRouter fails. Expected: Gemini is used."""
    groq = MockProvider("groq", "openai/gpt-oss-120b", should_succeed=False, error_msg="rate_limit")
    openrouter = MockProvider("openrouter", "openrouter/free", should_succeed=False, error_msg="upstream_timeout")
    gemini = MockProvider("gemini", "gemini-3-flash-preview", should_succeed=True)

    service = LLMService(providers=[groq, openrouter, gemini])
    response = await service.generate("Test prompt")

    assert response.provider == "gemini"
    assert response.model == "gemini-3-flash-preview"
    assert response.fallback_used is True
    assert groq.call_count == 1
    assert openrouter.call_count == 1
    assert gemini.call_count == 1


@pytest.mark.asyncio
async def test_case_4_all_providers_fail():
    """CASE 4: All providers fail. Expected: Controlled ALL_LLM_PROVIDERS_FAILED error."""
    groq = MockProvider("groq", "openai/gpt-oss-120b", should_succeed=False, error_msg="rate_limit")
    openrouter = MockProvider("openrouter", "openrouter/free", should_succeed=False, error_msg="model_not_found")
    gemini = MockProvider("gemini", "gemini-3-flash-preview", should_succeed=False, error_msg="quota_exceeded")

    service = LLMService(providers=[groq, openrouter, gemini])

    with pytest.raises(LLMProviderError) as exc_info:
        await service.generate("Test prompt")

    assert "ALL_LLM_PROVIDERS_FAILED" in str(exc_info.value)
    assert groq.call_count == 1
    assert openrouter.call_count == 1
    assert gemini.call_count == 1


@pytest.mark.asyncio
async def test_3_tier_health_reporting():
    """Verify health() returns structured primary and fallback statuses."""
    groq = MockProvider("groq", "openai/gpt-oss-120b", should_succeed=True)
    groq.api_key = "test_key_groq"
    openrouter = MockProvider("openrouter", "openrouter/free", should_succeed=False, error_msg="timeout")
    openrouter.api_key = "test_key_openrouter"
    gemini = MockProvider("gemini", "gemini-3-flash-preview", should_succeed=True)
    gemini.api_key = ""  # Unconfigured

    service = LLMService(providers=[groq, openrouter, gemini])
    health = await service.health()

    assert health["success"] is True
    assert health["primary"]["provider"] == "groq"
    assert health["primary"]["status"] == "available"

    fallbacks = health["fallbacks"]
    assert len(fallbacks) == 2
    assert fallbacks[0]["provider"] == "openrouter"
    assert fallbacks[0]["status"] == "failed"
    assert fallbacks[1]["provider"] == "gemini"
    assert fallbacks[1]["status"] == "unconfigured"
