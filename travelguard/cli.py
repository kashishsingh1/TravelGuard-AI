"""Command-line interface for TravelGuard AI."""

import argparse
import asyncio
import json
import os
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

from travelguard.analyzer import ChangeImpactAnalyzer
from travelguard.change_detector import ChangeDetector, GitCommitDiffSource, GitWorkingTreeSource
from travelguard.demo import DEMO_SCENARIOS, run_demo_scenario
from travelguard.models import ChangeSet, ImpactAnalysisResult
from travelguard.registry import get_journey_registry


def format_cli_report(change_set: ChangeSet, result: ImpactAnalysisResult) -> str:
    """Format the analysis result into a clean, human-readable terminal report."""
    divider = "=" * 50
    subdivider = "-" * 50

    lines = [
        divider,
        "TRAVELGUARD AI",
        "CHANGE IMPACT ANALYSIS",
        divider,
        "",
        "Changed Files:",
        "",
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
        subdivider,
        "CHANGE SUMMARY",
        subdivider,
        "",
        f"{result.summary}",
        "",
        "Change Type:",
        f"{result.change_type.upper()}" + (" (Behavioral)" if result.is_behavioral else " (Cosmetic)"),
        "",
        subdivider,
        "BUSINESS IMPACT",
        subdivider,
        "",
    ])

    if result.affected_journeys:
        for j in result.affected_journeys:
            lines.append(f"Affected Journey:\n{j.journey_name}")
            lines.append(f"Capability:\n{j.capability}")
            lines.append(f"Impact Level:\n{j.impact_level.upper()}")
            lines.append("")
    else:
        lines.append("Affected Journey:\nNone detected\n")

    lines.append(f"Business Impact:\n{result.business_impact}\n")

    lines.extend([
        subdivider,
        "RISK",
        subdivider,
        "",
        f"Risk Level:\n{result.risk.level.upper()}",
        "",
        f"Risk Score:\n{result.risk.score}/100",
        "",
        f"Reason:\n{result.risk.reason}",
        "",
        subdivider,
        "RECOMMENDED TESTS",
        subdivider,
        "",
    ])

    if result.recommended_tests:
        for t in result.recommended_tests:
            lines.append(f"✓ {t}")
    else:
        lines.append("  (No tests recommended)")

    lines.extend([
        "",
        subdivider,
        "AI CONFIDENCE & ORCHESTRATION",
        subdivider,
        "",
        f"Confidence: {int(result.confidence * 100)}%",
    ])

    if result.provider_used:
        prov_str = result.provider_used.capitalize()
        if result.fallback_used:
            prov_str += " (Fallback Engaged)"
        lines.append(f"Provider:   {prov_str}")

    lines.extend([
        "",
        divider,
    ])

    return "\n".join(lines)


async def handle_analyze(args: argparse.Namespace) -> int:
    """Handle the 'analyze' command."""
    use_mock_llm = getattr(args, "mock_llm", False)

    # 1. Demo Mode
    if args.demo:
        scenario_key = args.demo.lower()
        if scenario_key not in DEMO_SCENARIOS:
            print(f"Error: Unknown scenario '{args.demo}'. Available: {', '.join(DEMO_SCENARIOS.keys())}", file=sys.stderr)
            return 1

        print(f"[TravelGuard] Running demo scenario: {DEMO_SCENARIOS[scenario_key]['name']}...")
        try:
            change_set, result = await run_demo_scenario(scenario_key=scenario_key, use_mock_llm=use_mock_llm)
        except Exception as exc:
            # If live LLM call fails without API keys and user didn't specify --mock-llm, attempt mock fallback
            if not use_mock_llm and ("API key" in str(exc) or "401" in str(exc)):
                print(f"[TravelGuard] Notice: Live LLM call failed ({exc}). Falling back to deterministic demo fixture.")
                change_set, result = await run_demo_scenario(scenario_key=scenario_key, use_mock_llm=True)
            else:
                print(f"Error executing analysis: {exc}", file=sys.stderr)
                return 1

    # 2. Live Git working tree or commit ref
    else:
        if args.ref:
            print(f"[TravelGuard] Inspecting changes against git ref: {args.ref}...")
            source = GitCommitDiffSource(base_ref=args.ref)
        else:
            print("[TravelGuard] Inspecting git working tree changes...")
            source = GitWorkingTreeSource()

        detector = ChangeDetector(source=source)
        change_set = detector.get_change_set()

        if not change_set.files:
            print("\n[TravelGuard] No code changes detected in the current working tree or specified ref.")
            print("Tip: You can run a demo scenario via: python -m travelguard analyze --demo scenario_a\n")
            return 0

        analyzer = ChangeImpactAnalyzer()
        try:
            result = await analyzer.analyze(change_set=change_set)
        except Exception as exc:
            print(f"Error executing LLM analysis: {exc}", file=sys.stderr)
            return 1

    # Output formatting
    if getattr(args, "json", False):
        print(result.model_dump_json(indent=2))
    else:
        print("\n" + format_cli_report(change_set, result))

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


def build_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="travelguard",
        description="TravelGuard AI — Change Detection & Business Impact Analysis",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: analyze
    analyze_parser = subparsers.add_parser("analyze", help="Analyze repository code changes")
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
        help="Run a predefined deterministic demo scenario (scenario_a, scenario_b, scenario_c)",
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

    # Command: demo
    subparsers.add_parser("demo", help="List available hackathon demo scenarios")

    return parser


def main() -> None:
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        # Default to analyze if no command specified
        args.command = "analyze"
        args.ref = None
        args.demo = None
        args.json = False
        args.mock_llm = False

    if args.command == "analyze":
        exit_code = asyncio.run(handle_analyze(args))
    elif args.command == "journeys":
        exit_code = handle_journeys(args)
    elif args.command == "demo":
        exit_code = handle_demo_list(args)
    else:
        parser.print_help()
        exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
