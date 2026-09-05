"""Command-line interface for TravelGuard AI — Autonomous Test Intelligence."""

import argparse
import asyncio
import json
from pathlib import Path
import sys
from typing import Optional

# Ensure UTF-8 stdout on Windows console
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure backend directory is in sys.path
_repo_root = Path(__file__).resolve().parent.parent
_backend_dir = _repo_root / "backend"
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from travelguard.autonomous_pipeline import AutonomousQAEngine
from travelguard.change_detector import ChangeDetector, GitCommitDiffSource, GitWorkingTreeSource, FixtureChangeSource
from travelguard.demo import DEMO_SCENARIOS, create_demo_execution_results, load_scenario_diff, run_demo_scenario
from travelguard.models import AutonomousRunResult, ChangeSet, TestIntelligenceResult
from travelguard.pipeline import TestIntelligencePipeline
from travelguard.registry import get_journey_registry
from travelguard.test_inventory import get_test_inventory


def format_cli_report(change_set: ChangeSet, result: TestIntelligenceResult) -> str:
    """Format the Increment 3 intelligence output into an explainable terminal report."""
    divider = "=" * 50
    subdivider = "-" * 50

    lines = [
        divider,
        "TRAVELGUARD AI",
        "AUTONOMOUS TEST INTELLIGENCE",
        divider,
        "",
        "CHANGE",
        "Modified:",
    ]

    if not change_set.files:
        lines.append("  (No changed files detected)")
    else:
        status_map = {
            "modified": "M",
            "added": "A",
            "deleted": "D",
            "renamed": "R",
            "untracked": "?",
        }
        for f in change_set.files:
            s_code = status_map.get(f.status.value, "M")
            lines.append(f"  {s_code} {f.path}")

    lines.extend([
        "",
        "CHANGE TYPE:",
        f"{result.impact.change_type.upper()}" + (" (Behavioral)" if result.impact.is_behavioral else " (Cosmetic)"),
        "",
        subdivider,
        "BUSINESS IMPACT",
        subdivider,
    ])

    if result.impact.affected_journeys:
        j_names = ", ".join([j.journey_name for j in result.impact.affected_journeys])
        lines.append(f"Journey:\n{j_names}")
    else:
        lines.append("Journey:\nNone directly impacted")

    lines.extend([
        f"Risk:\n{result.impact.risk.level.upper()}",
        "",
        f"Risk Score:\n{result.impact.risk.score}/100",
        "",
        f"Business Impact:\n{result.impact.business_impact}",
        "",
        subdivider,
        "INTELLIGENT TEST SELECTION",
        subdivider,
    ])

    # 1. Render Selected Tests
    if result.selected_tests:
        for t in result.selected_tests:
            lines.append(f"{t.priority.value} ✓ {t.name} ({t.file})")
            lines.append(f"   Reason: {t.reason}")
            lines.append("")
    else:
        lines.append("No tests selected.")
        lines.append("")

    # 2. Render Skipped Tests
    if result.skipped_tests:
        for t in result.skipped_tests:
            lines.append(f"   ○ {t.name} ({t.file}) [SKIPPED]")
            lines.append(f"   Reason: {t.reason}")
            lines.append("")

    # 3. Coverage Analysis
    lines.extend([
        subdivider,
        "COVERAGE ANALYSIS",
        subdivider,
        f"Existing coverage:\n{result.coverage.status.value}",
        "",
    ])

    if result.coverage.missing_scenarios:
        for m in result.coverage.missing_scenarios:
            lines.append(f"Missing scenario:\n{m}")
            lines.append("")
    else:
        lines.append(f"Coverage Assessment:\n{result.coverage.reason}\n")

    # 4. AI Test Generation
    lines.extend([
        subdivider,
        "AI TEST GENERATION",
        subdivider,
    ])

    if result.generated_test:
        lines.append(f"Generated:\n{result.generated_test.file_path}")
        lines.append("")
        lines.append(f"Scenario:\n{result.generated_test.scenario_name}")
        lines.append("")
        lines.append(f"Validation:\n{result.generated_test.validation_status}")
        if result.generated_test.validation_details:
            lines.append(f"Details: {result.generated_test.validation_details}")
    else:
        lines.append("Status:\nNot required (existing test coverage is sufficient).")

    # Provider metadata
    lines.extend([
        "",
        subdivider,
        "AI ORCHESTRATION & CONFIDENCE",
        subdivider,
        f"Confidence: {int(result.impact.confidence * 100)}%",
        f"Provider:   {result.impact.provider_used.capitalize() if result.impact.provider_used else 'Groq'}"
        + (" (Fallback Engaged)" if result.impact.fallback_used else ""),
        divider,
    ])

    return "\n".join(lines)


async def handle_analyze(args: argparse.Namespace) -> int:
    """Execute the Increment 3 test intelligence pipeline."""
    pipeline = TestIntelligencePipeline()

    if args.demo:
        scenario = DEMO_SCENARIOS.get(args.demo)
        if not scenario:
            print(f"Error: Unknown demo scenario '{args.demo}'", file=sys.stderr)
            return 1
        print(f"[TravelGuard] Running demo scenario: {scenario['name']}...")
        raw_diff = load_scenario_diff(args.demo)
        source = FixtureChangeSource(raw_diff=raw_diff, fixture_name=scenario["name"])
        detector = ChangeDetector(source=source)
        change_set = detector.get_change_set()
        mock_payload = scenario.get("mock_response") if args.mock_llm else None
    elif args.ref:
        print(f"[TravelGuard] Detecting changes against Git ref: {args.ref}...")
        source = GitCommitDiffSource(base_ref=args.ref)
        detector = ChangeDetector(source=source)
        change_set = detector.get_change_set()
        mock_payload = None
    else:
        print("[TravelGuard] Detecting changes in working tree...")
        source = GitWorkingTreeSource()
        detector = ChangeDetector(source=source)
        change_set = detector.get_change_set()
        mock_payload = None

    try:
        result = await pipeline.run(change_set=change_set, mock_response=mock_payload)
    except Exception as exc:
        print(f"[TravelGuard Error] Pipeline failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result.model_dump(), indent=2))
    else:
        print("\n" + format_cli_report(change_set, result) + "\n")

    return 0


def handle_journeys(args: argparse.Namespace) -> int:
    """Display registered business journeys."""
    registry = get_journey_registry()
    journeys = registry.list_journeys()

    print("\n" + "=" * 60)
    print("TRAVELGUARD — REGISTERED BUSINESS JOURNEYS")
    print("=" * 60)
    for j in journeys:
        print(f"\n[{j.workflow_stage}] {j.name} (ID: {j.id})")
        print(f"    Criticality: {j.criticality.value.upper()}")
        print(f"    Description: {j.description}")
        print(f"    Components:  {', '.join(j.components) or 'None'}")
        print(f"    Frontend:    {', '.join(j.frontend_paths) or 'None'}")
        print(f"    API Routes:  {', '.join(j.api_paths) or 'None'}")
        print(f"    Tests:       {len(j.tests)} registered candidate tests")
    print("\n" + "=" * 60 + "\n")
    return 0


def handle_test_inventory(args: argparse.Namespace) -> int:
    """Display registered test inventory."""
    inventory = get_test_inventory()
    tests = inventory.get_all()

    print("\n" + "=" * 60)
    print("TRAVELGUARD — REGISTERED TEST INVENTORY")
    print("=" * 60)
    for t in tests:
        print(f"\nTest ID:     {t.id}")
        print(f"  Name:        {t.name}")
        print(f"  File:        {t.file}")
        print(f"  Tier:        {t.priority_tier.value}")
        print(f"  Criticality: {t.criticality.upper()}")
        print(f"  Journeys:    {', '.join(t.business_journeys)}")
        print(f"  Description: {t.description}")
        print(f"  Duration:    ~{t.expected_duration_ms}ms")
    print("\n" + "=" * 60 + "\n")
    return 0


def handle_demo_list(args: argparse.Namespace) -> int:
    """List available demo scenarios."""
    print("\n" + "=" * 60)
    print("TRAVELGUARD — HACKATHON DEMO SCENARIOS")
    print("=" * 60)
    for k, s in DEMO_SCENARIOS.items():
        print(f"\nScenario Key: {k}")
        print(f"  Title:       {s['name']}")
        print(f"  Description: {s['description']}")
        print(f"  Fixture:     {s['fixture_file']}")
        print(f"  Command:     python -m travelguard analyze --demo {k}")
    print("\n" + "=" * 60 + "\n")
    return 0


def _format_autonomous_report(result: AutonomousRunResult) -> str:
    """Format the Increment 4 autonomous run result as a terminal report."""
    divider = "=" * 60
    sub = "-" * 60
    qr = result.quality_report

    status_emoji = {
        "PASS": "[PASS]",
        "PASS_WITH_HEALING": "[HEALED]",
        "FAIL": "[FAIL]",
        "REAL_DEFECT": "[DEFECT]",
        "ENVIRONMENT_FAILURE": "[ENV FAIL]",
        "BLOCKED": "[BLOCKED]",
    }.get(qr.status.value, "[?]")

    lines = [
        divider,
        "TRAVELGUARD AI — AUTONOMOUS QA REPORT",
        f"Run ID  : {qr.run_id}",
        f"Status  : {status_emoji} {qr.status.value}",
        f"Confidence: {int(qr.release_confidence * 100)}%",
        divider,
        "",
        sub,
        "TEST EXECUTION SUMMARY",
        sub,
        f"  Selected : {qr.selected_tests}",
        f"  Skipped  : {qr.skipped_tests}",
        f"  Passed   : {qr.passed}",
        f"  Failed   : {qr.failed}",
        f"  Healed   : {qr.healed}",
        "",
    ]

    if result.diagnosis_results:
        lines += [sub, "FAILURE DIAGNOSIS", sub]
        for d in result.diagnosis_results:
            lines.append(f"  Test     : {d.test_id}")
            lines.append(f"  Class    : {d.classification.value} (conf={d.confidence:.0%})")
            lines.append(f"  Summary  : {d.summary}")
            lines.append(f"  Action   : {d.recommended_action}")
            lines.append("")

    if result.healing_results:
        lines += [sub, "SELF-HEALING OUTCOME", sub]
        for h in result.healing_results:
            lines.append(f"  Test     : {h.test_id}")
            lines.append(f"  Status   : {h.status.value}")
            lines.append(f"  Reason   : {h.reason}")
            if h.original_locator:
                lines.append(f"  Old      : {h.original_locator}")
            if h.replacement_locator:
                lines.append(f"  New      : {h.replacement_locator}")
            lines.append("")

    lines += [
        sub,
        "VERDICT",
        sub,
        f"  {qr.summary}",
        "",
        divider,
    ]
    return "\n".join(lines)


async def handle_autonomous_demo(args: argparse.Namespace) -> int:
    """Execute the Increment 4 Autonomous QA pipeline for a demo scenario."""
    scenario_key = args.demo
    scenario = DEMO_SCENARIOS.get(scenario_key) or DEMO_SCENARIOS.get(scenario_key.replace("_", "-"))
    if not scenario:
        print(f"Error: Unknown scenario '{scenario_key}'", file=sys.stderr)
        print(f"Available: {list(DEMO_SCENARIOS.keys())}", file=sys.stderr)
        return 1

    print(f"\n[TravelGuard] Autonomous QA Demo — {scenario['name']}")
    print(f"[TravelGuard] Loading fixture: {scenario['fixture_file']}")

    # Load change set from fixture
    from travelguard.change_detector import ChangeDetector, FixtureChangeSource
    raw_diff = load_scenario_diff(scenario_key)
    source = FixtureChangeSource(raw_diff=raw_diff, fixture_name=scenario["name"])
    detector = ChangeDetector(source=source)
    change_set = detector.get_change_set()

    # Create deterministic execution results for demo
    demo_exec_results = create_demo_execution_results(scenario_key)

    engine = AutonomousQAEngine()
    mock_impact = scenario.get("mock_response") if args.mock_llm else None

    try:
        result = await engine.run(
            change_set=change_set,
            mock_impact=mock_impact,
            demo_execution_results=demo_exec_results,
        )
    except Exception as exc:
        print(f"[TravelGuard Error] Autonomous pipeline failed: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1

    if args.json:
        print(json.dumps(result.model_dump(), indent=2))
    else:
        print("\n" + _format_autonomous_report(result) + "\n")

    # Return non-zero exit code when a real defect is detected
    qr = result.quality_report
    if qr.real_defects > 0:
        return 2
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="travelguard",
        description="TravelGuard AI — Autonomous Test Intelligence Platform",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: analyze
    analyze_parser = subparsers.add_parser("analyze", help="Analyze repository code changes and select/generate tests")
    analyze_parser.add_argument(
        "--ref",
        "-r",
        type=str,
        default=None,
        help="Git commit or branch ref to diff against (e.g., HEAD~1, main)",
    )
    analyze_parser.add_argument(
        "--demo",
        "-d",
        type=str,
        default=None,
        choices=list(DEMO_SCENARIOS.keys()),
        help="Run a predefined deterministic demo scenario (scenario_a, scenario_b, scenario_c, scenario_d)",
    )
    analyze_parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw structured JSON instead of formatted text",
    )
    analyze_parser.add_argument(
        "--mock-llm",
        action="store_true",
        help="Use deterministic mock LLM response (for offline verification and tests)",
    )

    # Command: journeys
    subparsers.add_parser("journeys", help="List registered business user journeys")

    # Command: test-inventory
    subparsers.add_parser("test-inventory", help="List registered test inventory")

    # Command: demo
    subparsers.add_parser("demo", help="List available hackathon demo scenarios")

    # Command: autonomous-demo
    auto_parser = subparsers.add_parser(
        "autonomous-demo",
        help="Run the full Increment 4 autonomous QA pipeline for a demo scenario",
    )
    auto_parser.add_argument(
        "--demo",
        "-d",
        type=str,
        required=True,
        choices=["booking-ui-drift", "booking-api-defect", "environment-failure",
                 "booking_ui_drift", "booking_api_defect", "environment_failure"],
        help="Demo scenario to run: booking-ui-drift | booking-api-defect | environment-failure",
    )
    auto_parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of formatted report",
    )
    auto_parser.add_argument(
        "--mock-llm",
        action="store_true",
        help="Use deterministic mock LLM responses (offline/CI mode)",
    )

    return parser


def main() -> None:
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        args.command = "analyze"
        args.ref = None
        args.demo = None
        args.json = False
        args.mock_llm = False

    if args.command == "analyze":
        exit_code = asyncio.run(handle_analyze(args))
    elif args.command == "autonomous-demo":
        exit_code = asyncio.run(handle_autonomous_demo(args))
    elif args.command == "journeys":
        exit_code = handle_journeys(args)
    elif args.command == "test-inventory":
        exit_code = handle_test_inventory(args)
    elif args.command == "demo":
        exit_code = handle_demo_list(args)
    else:
        parser.print_help()
        exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
