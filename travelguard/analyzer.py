"""AI-powered change analysis using primary DeepSeek and Grok fallback."""

import json
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional

# Ensure backend is in sys.path for app.llm imports
_repo_root = Path(__file__).resolve().parent.parent
_backend_dir = _repo_root / "backend"
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from app.llm.base import LLMResponse
from app.llm.router import LLMService, get_llm_service

from travelguard.journey_mapper import DeterministicMappingResult, JourneyMapper
from travelguard.models import (
    ChangeSet,
    ImpactAnalysisResult,
    JourneyCriticality,
    JourneyImpact,
    RiskAssessment,
)
from travelguard.recommender import TestRecommender
from travelguard.registry import JourneyRegistry, get_journey_registry
from travelguard.risk_engine import RiskEngine


SYSTEM_PROMPT = """You are TravelGuard AI, an expert Autonomous QA Engineer analyzing code changes for SkyBook, a mission-critical travel booking application.
The application workflow is:
Flight Search -> Flight Results -> Select Flight -> Passenger Details -> Book Flight -> Booking Confirmation.

You will be given a set of changed files, their Git diffs, and deterministically detected business journeys.
Your job is to analyze the business intent and risk of the changes.

You MUST respond ONLY with a valid JSON object. Do not include explanatory text before or after the JSON.
Do not wrap in markdown code blocks if possible, or use standard ```json ... ``` blocks.

The JSON schema must follow this structure:
{
  "summary": "<concise 1-sentence summary of the functional change>",
  "change_type": "<ui | api | business_logic | config | test | infra | cosmetic>",
  "is_behavioral": <true if change affects behavior/logic/contracts; false if purely cosmetic/formatting/docs>,
  "affected_journeys": [
    {
      "journey_id": "<journey identifier, e.g., flight_booking, flight_search, etc.>",
      "journey_name": "<journey name>",
      "impact_level": "<low | medium | high | critical>",
      "capability": "<specific customer capability impacted>"
    }
  ],
  "ai_risk_level": "<low | medium | high | critical>",
  "ai_risk_reason": "<1-2 sentence concise explanation of why this change carries this risk>",
  "recommended_tests": [
    "<test description or test name to verify this change>"
  ],
  "business_impact": "<explanation of user or business consequences if this change breaks>",
  "confidence": <float between 0.0 and 1.0>
}
"""


def extract_json_payload(raw_text: str) -> Dict[str, Any]:
    """Safely extract and parse JSON from raw LLM output, stripping markdown blocks if present."""
    text = raw_text.strip()
    if not text:
        raise ValueError("LLM returned empty response")

    # 1. Try direct json parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Extract from markdown code fence
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 3. Find outermost curly braces
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        json_candidate = text[start : end + 1]
        try:
            return json.loads(json_candidate)
        except json.JSONDecodeError as exc:
            # Try cleaning trailing commas
            cleaned = re.sub(r",\s*([\]}])", r"\1", json_candidate)
            try:
                return json.loads(cleaned)
            except Exception:
                raise ValueError(f"Malformed JSON returned by LLM: {str(exc)}") from exc

    raise ValueError(f"Could not extract valid JSON from LLM response: {text[:200]}")


class ChangeImpactAnalyzer:
    """Orchestrates change analysis: deterministic mapping -> LLM reasoning -> risk scoring -> test recommendation."""

    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        registry: Optional[JourneyRegistry] = None,
        mapper: Optional[JourneyMapper] = None,
        risk_engine: Optional[RiskEngine] = None,
        recommender: Optional[TestRecommender] = None,
    ):
        self.llm_service = llm_service
        self.registry = registry or get_journey_registry()
        self.mapper = mapper or JourneyMapper(self.registry)
        self.risk_engine = risk_engine or RiskEngine()
        self.recommender = recommender or TestRecommender()

    def _get_llm_service(self) -> LLMService:
        if self.llm_service is None:
            self.llm_service = get_llm_service()
        return self.llm_service

    def build_prompt(self, change_set: ChangeSet, det_result: DeterministicMappingResult) -> str:
        """Construct the prompt sent to the LLM."""
        diff_snippets = []
        for file in change_set.files:
            file_diff = file.diff
            # Truncate overly long individual diffs to prevent context blowup
            if len(file_diff) > 2500:
                file_diff = file_diff[:2500] + "\n... [diff truncated]"
            diff_snippets.append(
                f"### File: {file.path} ({file.status.value}, +{file.additions}, -{file.deletions})\n"
                f"```diff\n{file_diff}\n```"
            )

        known_journeys_info = "\n".join(
            f"- {j.name} (ID: {j.id}, Criticality: {j.criticality.value}): {j.description}"
            for j in det_result.journeys
        ) or "None detected deterministically."

        candidate_tests_info = "\n".join(f"- {t}" for t in det_result.candidate_tests) or "No pre-mapped tests."

        prompt = f"""SkyBook Travel Application Change Impact Analysis

CHANGED FILES ({len(change_set.files)}):
{chr(10).join(f"- {f.path} ({f.status.value})" for f in change_set.files)}

DETERMINISTICALLY MAPPED JOURNEYS:
{known_journeys_info}

PRE-MAPPED CANDIDATE TESTS:
{candidate_tests_info}

GIT DIFF PATCHES:
{"".join(diff_snippets)}

Please analyze this change and provide your response strictly conforming to the requested JSON schema.
"""
        return prompt

    async def analyze(
        self,
        change_set: ChangeSet,
        mock_response: Optional[Dict[str, Any]] = None,
    ) -> ImpactAnalysisResult:
        """Analyze a change set and produce a complete validated ImpactAnalysisResult."""
        if not change_set.files:
            # Empty change set
            return ImpactAnalysisResult(
                summary="No changes detected in the selected source.",
                change_type="none",
                is_behavioral=False,
                affected_journeys=[],
                risk=RiskAssessment(
                    level="low",
                    score=0,
                    reason="No files modified or added.",
                ),
                recommended_tests=[],
                business_impact="None. Working tree or commit range is clean.",
                confidence=1.0,
                provider_used="deterministic",
                fallback_used=False,
            )

        # 1. Deterministic mapping first
        det_result = self.mapper.map_change_set(change_set)

        # 2. LLM Analysis
        provider_name = "mock"
        fallback_used = False

        if mock_response is not None:
            parsed_json = mock_response
        else:
            service = self._get_llm_service()
            prompt = self.build_prompt(change_set, det_result)
            llm_res: LLMResponse = await service.generate(
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT,
                max_tokens=800,
                temperature=0.2,
            )
            provider_name = llm_res.provider
            fallback_used = llm_res.fallback_used
            parsed_json = extract_json_payload(llm_res.content)

        # 3. Extract and normalize LLM fields
        summary = parsed_json.get("summary", "Application modifications detected.")
        change_type = str(parsed_json.get("change_type", "ui")).lower()
        is_behavioral = bool(parsed_json.get("is_behavioral", True))
        business_impact = parsed_json.get(
            "business_impact",
            "Customer travel experience or booking workflow may be affected.",
        )
        confidence = float(parsed_json.get("confidence", 0.9))
        ai_risk_level = str(parsed_json.get("ai_risk_level", "medium")).lower()
        ai_risk_reason = parsed_json.get("ai_risk_reason")

        # 4. Map affected journeys
        affected_journeys: List[JourneyImpact] = []
        raw_journeys = parsed_json.get("affected_journeys", [])
        if raw_journeys:
            for rj in raw_journeys:
                j_id = rj.get("journey_id", rj.get("journey", "unknown"))
                j_name = rj.get("journey_name", j_id.replace("_", " ").title())
                impact_lvl = rj.get("impact_level", rj.get("impact", "medium")).lower()
                cap = rj.get("capability", "Booking capabilities")
                affected_journeys.append(
                    JourneyImpact(
                        journey_id=j_id,
                        journey_name=j_name,
                        impact_level=impact_lvl,
                        capability=cap,
                    )
                )

        # If LLM didn't return affected journeys, fall back to deterministic matches
        if not affected_journeys and det_result.journeys:
            for j in det_result.journeys:
                affected_journeys.append(
                    JourneyImpact(
                        journey_id=j.id,
                        journey_name=j.name,
                        impact_level=j.criticality.value,
                        capability=j.description,
                    )
                )

        # 5. Calculate transparent risk score
        highest_crit = det_result.highest_criticality
        risk = self.risk_engine.evaluate(
            change_set=change_set,
            highest_criticality=highest_crit,
            change_type=change_type,
            is_behavioral=is_behavioral,
            ai_risk_hint=ai_risk_level,
            ai_reason=ai_risk_reason,
        )

        # 6. Test recommendations
        raw_ai_tests = parsed_json.get("recommended_tests", [])
        recommended_tests = self.recommender.recommend(
            journeys=det_result.journeys,
            change_type=change_type,
            is_behavioral=is_behavioral,
            ai_recommended=raw_ai_tests,
        )

        return ImpactAnalysisResult(
            summary=summary,
            change_type=change_type,
            is_behavioral=is_behavioral,
            affected_journeys=affected_journeys,
            risk=risk,
            recommended_tests=recommended_tests,
            business_impact=business_impact,
            confidence=round(confidence, 2),
            provider_used=provider_name,
            fallback_used=fallback_used,
        )
