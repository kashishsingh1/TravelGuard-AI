"""Base classes and interfaces for LLM providers."""

from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel, Field


class LLMResponse(BaseModel):
    """Normalized response from any LLM provider."""

    content: str = Field(..., description="Generated text content")
    provider: str = Field(..., description="Provider name (e.g., deepseek, grok)")
    model: str = Field(..., description="Model identifier used")
    fallback_used: bool = Field(default=False, description="Whether fallback provider was used")
    latency_ms: float = Field(default=0.0, description="Response latency in milliseconds")


class LLMProviderError(Exception):
    """Exception raised by LLM providers upon failure."""

    def __init__(self, provider: str, message: str, status_code: Optional[int] = None):
        super().__init__(f"[{provider}] {message}")
        self.provider = provider
        self.message = message
        self.status_code = status_code


class BaseLLMProvider(ABC):
    """Abstract base provider for LLM integration."""

    name: str = "base"
    model: str = ""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 150,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Generate a completion for the given prompt."""
        pass

    @abstractmethod
    async def health_check(self) -> LLMResponse:
        """Perform a minimal health check query."""
        pass
