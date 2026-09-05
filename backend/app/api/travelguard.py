"""FastAPI router for TravelGuard AI Developer Console."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from travelguard.autonomous_pipeline import AutonomousQAEngine
from travelguard.change_detector import ChangeDetector, FixtureChangeSource, GitWorkingTreeSource
from travelguard.demo import (
    DEMO_SCENARIOS,
    DemoSUTContext,
    create_demo_execution_results,
    create_demo_selected_tests,
    load_scenario_diff,
)
from travelguard.execution_engine import TestExecutionEngine
from travelguard.pipeline import TestIntelligencePipeline
from travelguard.registry import get_journey_registry
from travelguard.test_inventory import get_test_inventory

router = APIRouter(prefix="/api/travelguard", tags=["travelguard"])


class RunRequest(BaseModel):
    scenario: Optional[str] = None
    mock_llm: bool = True
    healing_mode: str = "AUTO"


class AnalyzeRequest(BaseModel):
    scenario: Optional[str] = None
    mock_llm: bool = True


class SingleTestRequest(BaseModel):
    test_file: str
    test_id: str
    test_name: str


@router.post("/test-single")
def run_single_test(req: SingleTestRequest):
    """Execute a single test file from the developer console."""
    engine = TestExecutionEngine()
    try:
        res = engine.execute_single_file(req.test_file, req.test_id, req.test_name)
        return res.model_dump()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Test execution error: {str(exc)}")


@router.get("/config")
async def get_config():
    """Return available demo scenarios, registered business journeys, and test inventory."""
    inventory = get_test_inventory().get_all()
    journeys = get_journey_registry().list_journeys()

    demos = []
    for key, data in DEMO_SCENARIOS.items():
        demos.append({
            "key": key,
            "name": data.get("name", key),
            "description": data.get("description", ""),
            "fixture_file": data.get("fixture_file", ""),
            "type": data.get("type", "demo"),
        })

    return {
        "demos": demos,
        "journeys": [j.model_dump() for j in journeys],
        "inventory": [t.model_dump() for t in inventory],
    }


@router.post("/run")
async def run_autonomous(request: RunRequest):
    """Execute the Autonomous QA pipeline for a demo scenario or local working tree."""
    scenario_key = request.scenario
    demo_exec_results = None
    demo_selected_tests = None
    mock_impact = None
    diff_text = ""

    if scenario_key:
        scenario = DEMO_SCENARIOS.get(scenario_key) or DEMO_SCENARIOS.get(scenario_key.replace("_", "-"))
        if not scenario:
            raise HTTPException(status_code=400, detail=f"Unknown demo scenario: {scenario_key}")

        raw_diff = load_scenario_diff(scenario_key)
        diff_text = raw_diff
        source = FixtureChangeSource(raw_diff=raw_diff, fixture_name=scenario["name"])
        demo_exec_results = create_demo_execution_results(scenario_key)
        demo_selected_tests = create_demo_selected_tests(scenario_key)
        if request.mock_llm:
            mock_impact = scenario.get("mock_response")
        sut_context = DemoSUTContext(scenario_key)
    else:
        source = GitWorkingTreeSource()
        sut_context = DemoSUTContext("")

    detector = ChangeDetector(source=source)
    change_set = detector.get_change_set()

    engine = AutonomousQAEngine()

    with sut_context:
        try:
            result = await engine.run(
                change_set=change_set,
                mock_impact=mock_impact,
                demo_execution_results=demo_exec_results,
                mock_selected_tests=demo_selected_tests,
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Autonomous pipeline error: {str(exc)}")

    res_dict = result.model_dump()
    res_dict["change_set"] = change_set.model_dump()
    res_dict["raw_diff"] = change_set.raw_diff if not scenario_key else diff_text
    return res_dict


@router.post("/analyze")
async def run_analyze(request: AnalyzeRequest):
    """Execute the Test Intelligence Pipeline (change analysis, test selection, AI test generation)."""
    scenario_key = request.scenario
    pipeline = TestIntelligencePipeline()
    diff_text = ""

    if scenario_key:
        scenario = DEMO_SCENARIOS.get(scenario_key) or DEMO_SCENARIOS.get(scenario_key.replace("_", "-"))
        if not scenario:
            raise HTTPException(status_code=400, detail=f"Unknown demo scenario: {scenario_key}")

        raw_diff = load_scenario_diff(scenario_key)
        diff_text = raw_diff
        source = FixtureChangeSource(raw_diff=raw_diff, fixture_name=scenario["name"])
        mock_response = scenario.get("mock_response") if request.mock_llm else None
    else:
        source = GitWorkingTreeSource()
        mock_response = None

    detector = ChangeDetector(source=source)
    change_set = detector.get_change_set()

    try:
        intel_result = await pipeline.run(change_set=change_set, mock_response=mock_response)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Intelligence pipeline error: {str(exc)}")

    res_dict = intel_result.model_dump()
    res_dict["change_set"] = change_set.model_dump()
    res_dict["raw_diff"] = diff_text
    return res_dict


@router.get("/runs")
async def get_recent_runs():
    """List recent quality reports from artifacts/runs."""
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    runs_dir = repo_root / "artifacts" / "runs"

    if not runs_dir.exists():
        return {"runs": []}

    runs = []
    for run_file in sorted(runs_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:10]:
        try:
            with open(run_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                runs.append(data)
        except Exception:
            continue

    return {"runs": runs}
