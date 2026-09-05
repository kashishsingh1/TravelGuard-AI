"""Unit tests for LLM provider abstraction and fallback logic."""

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
    """Verify primary provider is used when it succeeds."""
    primary = MockWorkingProvider("deepseek", "deepseek-v4-flash")
    fallback = MockWorkingProvider("groq", "llama-3.3-70b-versatile")

    service = LLMService(primary=primary, fallback=fallback)
    response = await service.generate("Test prompt")

    assert response.provider == "deepseek"
    assert response.model == "deepseek-v4-flash"
    assert response.fallback_used is False


@pytest.mark.asyncio
async def test_llm_fallback_on_primary_failure():
    """Verify fallback provider is used when primary fails."""
    primary = MockFailingProvider("deepseek", "deepseek-v4-flash", "Rate limit exceeded")
    fallback = MockWorkingProvider("groq", "llama-3.3-70b-versatile")

    service = LLMService(primary=primary, fallback=fallback)
    response = await service.generate("Test prompt")

    assert response.provider == "groq"
    assert response.model == "llama-3.3-70b-versatile"
    assert response.fallback_used is True


@pytest.mark.asyncio
async def test_llm_both_fail_raises_error():
    """Verify clean exception when both primary and fallback fail."""
    primary = MockFailingProvider("deepseek", "deepseek-v4-flash", "Auth failure")
    fallback = MockFailingProvider("groq", "llama-3.3-70b-versatile", "Network unreachable")

    service = LLMService(primary=primary, fallback=fallback)
    with pytest.raises(LLMProviderError) as exc_info:
        await service.generate("Test prompt")

    assert "Both primary (deepseek) and fallback (groq) failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_llm_health_with_fallback():
    """Verify health() returns structured fallback info."""
    primary = MockFailingProvider("deepseek", "deepseek-v4-flash", "DeepSeek API key missing")
    fallback = MockWorkingProvider("groq", "llama-3.3-70b-versatile")

    service = LLMService(primary=primary, fallback=fallback)
    health = await service.health()

    assert health["success"] is True
    assert health["provider"] == "groq"
    assert health["model"] == "llama-3.3-70b-versatile"
    assert health["fallback_used"] is True
