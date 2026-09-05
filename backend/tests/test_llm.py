"""Unit tests for LLM provider abstraction and multi-tier fallback logic."""

import pytest
from app.llm.base import BaseLLMProvider, LLMProviderError, LLMResponse
from app.llm.router import LLMService


class MockWorkingProvider(BaseLLMProvider):
    """Mock provider that always succeeds."""

    def __init__(self, name: str, model: str):
        self.name = name
        self.model = model

    async def generate(self, prompt: str, system_prompt=None, max_tokens=150, temperature=0.7):
        return LLMResponse(
            content=f"Hello from {self.name}",
            provider=self.name,
            model=self.model,
            fallback_used=False,
            latency_ms=15.0,
        )

    async def health_check(self):
        return await self.generate("ping")


class MockFailingProvider(BaseLLMProvider):
    """Mock provider that always fails."""

    def __init__(self, name: str, model: str, error_msg: str = "Connection timed out"):
        self.name = name
        self.model = model
        self.error_msg = error_msg

    async def generate(self, prompt: str, system_prompt=None, max_tokens=150, temperature=0.7):
        raise LLMProviderError(provider=self.name, message=self.error_msg, status_code=504)

    async def health_check(self):
        raise LLMProviderError(provider=self.name, message=self.error_msg, status_code=504)


@pytest.mark.asyncio
async def test_llm_primary_success():
    """Verify primary provider (groq) is used when it succeeds."""
    primary = MockWorkingProvider("groq", "openai/gpt-oss-120b")
    fallback = MockWorkingProvider("openrouter", "openrouter/free")

    service = LLMService(providers=[primary, fallback])
    response = await service.generate("Test prompt")

    assert response.provider == "groq"
    assert response.model == "openai/gpt-oss-120b"
    assert response.fallback_used is False


@pytest.mark.asyncio
async def test_llm_fallback_on_primary_failure():
    """Verify fallback provider (openrouter) is used when primary fails."""
    primary = MockFailingProvider("groq", "openai/gpt-oss-120b", "Rate limit exceeded")
    fallback = MockWorkingProvider("openrouter", "openrouter/free")

    service = LLMService(providers=[primary, fallback])
    response = await service.generate("Test prompt")

    assert response.provider == "openrouter"
    assert response.model == "openrouter/free"
    assert response.fallback_used is True


@pytest.mark.asyncio
async def test_llm_both_fail_raises_error():
    """Verify clean exception when all providers fail."""
    primary = MockFailingProvider("groq", "openai/gpt-oss-120b", "Auth failure")
    fallback = MockFailingProvider("openrouter", "openrouter/free", "Network unreachable")

    service = LLMService(providers=[primary, fallback])
    with pytest.raises(LLMProviderError) as exc_info:
        await service.generate("Test prompt")

    assert "ALL_LLM_PROVIDERS_FAILED" in str(exc_info.value)
