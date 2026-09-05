"""Unit tests for the autonomous-run CLI command in TravelGuard AI."""

import argparse
import pytest
from travelguard.cli import build_parser


class TestCLIAutonomousRun:
    """Validate argument parsing and configuration for autonomous-run command."""

    def test_autonomous_run_subcommand_registered(self):
        parser = build_parser()
        args = parser.parse_args(["autonomous-run"])
        assert args.command == "autonomous-run"
        assert args.healing_mode == "AUTO"
        assert args.quality_gate is True
        assert args.json is False
        assert args.mock_llm is False

    def test_autonomous_run_with_demo_option(self):
        parser = build_parser()
        args = parser.parse_args(["autonomous-run", "--demo", "booking-ui-drift", "--mock-llm"])
        assert args.command == "autonomous-run"
        assert args.demo == "booking-ui-drift"
        assert args.mock_llm is True

    def test_autonomous_run_with_json_and_ref(self):
        parser = build_parser()
        args = parser.parse_args(["autonomous-run", "--ref", "HEAD~1", "--json"])
        assert args.command == "autonomous-run"
        assert args.ref == "HEAD~1"
        assert args.json is True

    def test_autonomous_run_with_propose_only_mode(self):
        parser = build_parser()
        args = parser.parse_args(["autonomous-run", "--healing-mode", "PROPOSE_ONLY"])
        assert args.healing_mode == "PROPOSE_ONLY"

    def test_autonomous_demo_subcommand_registered(self):
        parser = build_parser()
        args = parser.parse_args(["autonomous-demo", "--demo", "booking-ui-drift", "--mock-llm"])
        assert args.command == "autonomous-demo"
        assert args.demo == "booking-ui-drift"
        assert args.mock_llm is True

    @pytest.mark.asyncio
    async def test_autonomous_demo_ui_drift_allowed(self):
        from travelguard.cli import handle_autonomous_demo
        parser = build_parser()
        args = parser.parse_args(["autonomous-demo", "--demo", "booking-ui-drift", "--mock-llm"])
        exit_code = await handle_autonomous_demo(args)
        assert exit_code == 0

    @pytest.mark.asyncio
    async def test_autonomous_demo_api_defect_blocked(self):
        from travelguard.cli import handle_autonomous_demo
        parser = build_parser()
        args = parser.parse_args(["autonomous-demo", "--demo", "booking-api-defect", "--mock-llm"])
        exit_code = await handle_autonomous_demo(args)
        assert exit_code == 2

    @pytest.mark.asyncio
    async def test_autonomous_demo_env_failure_blocked(self):
        from travelguard.cli import handle_autonomous_demo
        parser = build_parser()
        args = parser.parse_args(["autonomous-demo", "--demo", "environment-failure", "--mock-llm"])
        exit_code = await handle_autonomous_demo(args)
        assert exit_code == 3

