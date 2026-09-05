"""OpenRouter secondary LLM provider implementation."""

import time
from typing import Optional
import httpx

from app.llm.base import BaseLLMProvider, LLMProviderError, LLMResponse


class OpenRouterProvider(BaseLLMProvider):
    """OpenRouter fallback LLM provider using OpenAI-compatible API protocol."""

    def __init__(
        self,
        api_key: str,
        model: str = "openrouter/free",
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: float = 15.0,
    ):
        self.name = "openrouter"
        self.api_key = api_key.strip() if api_key else ""
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 150,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Execute chat completion request to OpenRouter."""
        if not self.api_key:
            raise LLMProviderError(
                provider=self.name,
                message="OPENROUTER_API_KEY is not set or empty",
                status_code=401,
            )

        endpoint = f"{self.base_url}/chat/completions"
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/kashishsingh1/TravelGuard-AI",
            "X-Title": "TravelGuard AI",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        start_time = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(endpoint, json=payload, headers=headers)
                latency = (time.perf_counter() - start_time) * 1000

                if response.status_code != 200:
                    error_msg = f"HTTP {response.status_code}"
                    try:
                        err_json = response.json()
                        if "error" in err_json:
                            err_val = err_json["error"]
                            if isinstance(err_val, dict) and "message" in err_val:
                                error_msg += f": {err_val['message']}"
                            else:
                                error_msg += f": {err_val}"
                    except Exception:
                        error_msg += f": {response.text[:100]}"

                    raise LLMProviderError(
                        provider=self.name,
                        message=error_msg,
                        status_code=response.status_code,
                    )

                data = response.json()
                msg = data["choices"][0]["message"]
                content = msg.get("content") or msg.get("reasoning") or ""
                return LLMResponse(
                    content=content,
                    provider=self.name,
                    model=self.model,
                    fallback_used=True,
                    latency_ms=round(latency, 2),
                )
        except httpx.TimeoutException as exc:
            raise LLMProviderError(
                provider=self.name,
                message=f"Request timed out after {self.timeout}s: {exc}",
                status_code=504,
            ) from exc
        except httpx.ConnectError as exc:
            raise LLMProviderError(
                provider=self.name,
                message=f"Connection failed: {exc}",
                status_code=503,
            ) from exc
        except LLMProviderError:
            raise
        except Exception as exc:
            raise LLMProviderError(
                provider=self.name,
                message=f"Unexpected error: {str(exc)}",
                status_code=500,
            ) from exc

    async def health_check(self) -> LLMResponse:
        """Minimal health check query."""
        return await self.generate(
            prompt="Respond with 'pong'",
            system_prompt="You are a health probe. Reply with only 'pong'.",
            max_tokens=60,
            temperature=0.0,
        )
