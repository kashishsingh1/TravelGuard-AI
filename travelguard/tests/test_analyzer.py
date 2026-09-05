"""Unit tests for AI change impact analyzer and structured response parsing."""

import json
from pathlib import Path
import sys
import pytest

# Ensure backend in sys.path
_repo_root = Path(__file__).resolve().parent.parent.parent
_backend_dir = _repo_root / "backend"
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from app.llm.base import BaseLLMProvider, LLMProviderError, LLMResponse
from app.llm.router import LLMService

from travelguard.analyzer import ChangeImpactAnalyzer, extract_json_payload
from travelguard.models import ChangeSet, FileChange, ImpactAnalysisResult


class MockAnalyzerProvider(BaseLLMProvider):
    """Mock LLM provider returning controlled JSON payload."""

    def __init__(self, name: str, model: str, response_text: str, should_fail: bool = False):
        self.name = name
        self.model = model
        self.response_text = response_text
        self.should_fail = should_fail

    async def generate(self, prompt: str, system_prompt=None, max_tokens=150, temperature=0.7):
        if self.should_fail:
            raise LLMProviderError(self.name, f"{self.name} simulated outage", 500)
        return LLMResponse(
            content=self.response_text,
            provider=self.name,
            model=self.model,
            fallback_used=False,
            latency_ms=25.0,
        )

    async def health_check(self):
        return await self.generate("ping")


def test_extract_json_from_plain_text():
    """Verify extracting valid JSON from clean text."""
    payload = {"summary": "Clean test", "change_type": "ui"}
    result = extract_json_payload(json.dumps(payload))
    assert result["summary"] == "Clean test"


def test_extract_json_from_markdown_block():
    """Verify extracting JSON wrapped in markdown code fence."""
    raw = """Here is the impact analysis:
```json
{
  "summary": "Markdown fenced change",
  "change_type": "api"
}
```
Thank you."""
    result = extract_json_payload(raw)
    assert result["summary"] == "Markdown fenced change"
    assert result["change_type"] == "api"


def test_extract_json_with_trailing_commas():
    """Verify recovery when JSON contains common syntax mistakes like trailing commas."""
    raw = '{\n  "summary": "Trailing comma test",\n  "change_type": "config",\n}'
    result = extract_json_payload(raw)
    assert result["summary"] == "Trailing comma test"


def test_extract_json_raises_on_unrecoverable_input():
    """Verify clear ValueError is raised when LLM returns invalid JSON."""
    with pytest.raises(ValueError) as exc:
        extract_json_payload("This is purely arbitrary text with no JSON braces whatsoever.")
    assert "Could not extract valid JSON" in str(exc.value)


@pytest.mark.asyncio
async def test_analyzer_end_to_end_with_primary_llm():
    """Verify end-to-end analysis using primary LLM provider."""
    mock_json = json.dumps({
        "summary": "Flight search form submit button altered",
        "change_type": "ui",
        "is_behavioral": True,
        "affected_journeys": [
            {
                "journey_id": "flight_search",
                "journey_name": "Flight Search",
                "impact_level": "medium",
                "capability": "Flight searching",
            }
        ],
        "ai_risk_level": "medium",
        "ai_risk_reason": "Changes submission button in flight search form.",
        "recommended_tests": ["Flight Search E2E (tests/e2e/search.spec.ts)"],
        "business_impact": "Users might face delays initiating flight queries.",
        "confidence": 0.92,
    })

    primary = MockAnalyzerProvider("groq", "openai/gpt-oss-120b", mock_json)
    fallback = MockAnalyzerProvider("openrouter", "openrouter/free", mock_json)
    llm_service = LLMService(providers=[primary, fallback])

    analyzer = ChangeImpactAnalyzer(llm_service=llm_service)
    cs = ChangeSet(files=[FileChange(path="frontend/src/components/SearchForm.tsx", additions=3, deletions=1)])

    result: ImpactAnalysisResult = await analyzer.analyze(cs)

    assert result.summary == "Flight search form submit button altered"
    assert result.provider_used == "groq"
    assert result.fallback_used is False
    assert result.risk.level in ("medium", "high")
    assert any(j.journey_id == "flight_search" for j in result.affected_journeys)


@pytest.mark.asyncio
async def test_analyzer_fallback_to_openrouter_on_primary_failure():
    """Verify analyzer engages OpenRouter fallback provider when Groq fails."""
    mock_json = json.dumps({
        "summary": "Booking route changed",
        "change_type": "api",
        "is_behavioral": True,
        "affected_journeys": [
            {
                "journey_id": "flight_booking",
                "journey_name": "Flight Booking & Confirmation",
                "impact_level": "critical",
                "capability": "Flight booking API",
            }
        ],
        "ai_risk_level": "critical",
        "ai_risk_reason": "Core booking route payload structure altered.",
        "recommended_tests": ["Booking Creation API (backend/tests/test_api.py::test_booking_success)"],
        "business_impact": "Failed ticket bookings.",
        "confidence": 0.96,
    })

    primary_failing = MockAnalyzerProvider("groq", "openai/gpt-oss-120b", "", should_fail=True)
    fallback_working = MockAnalyzerProvider("openrouter", "openrouter/free", mock_json)
    llm_service = LLMService(providers=[primary_failing, fallback_working])

    analyzer = ChangeImpactAnalyzer(llm_service=llm_service)
    cs = ChangeSet(files=[FileChange(path="backend/app/api/booking.py", additions=10, deletions=2)])

    result: ImpactAnalysisResult = await analyzer.analyze(cs)

    assert result.provider_used == "openrouter"
    assert result.fallback_used is True
    assert result.risk.level == "critical"
