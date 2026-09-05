"""Unit tests for OpenTelemetry tracing and Prometheus metrics in TravelGuard AI."""

import pytest
from travelguard.observability import (
    HAS_PROMETHEUS,
    get_prometheus_metrics_text,
    record_run_metrics,
    trace_span,
)


class TestObservability:
    """Validate tracing span lifecycle and metrics emission."""

    def test_trace_span_context_manager(self):
        with trace_span("travelguard.test_span", {"test.attr": "value"}) as span:
            pass  # Successfully entered and exited without error

    def test_record_run_metrics_and_prometheus_export(self):
        if not HAS_PROMETHEUS:
            pytest.skip("Prometheus client not installed")

        record_run_metrics(
            status="PASS_WITH_HEALING",
            decision="ALLOW_WITH_AUDIT",
            confidence=0.95,
            healed=1,
            defects=0,
            env_failures=0,
        )

        metrics_text = get_prometheus_metrics_text()
        assert "travelguard_release_confidence" in metrics_text
        assert "travelguard_test_runs_total" in metrics_text
        assert "travelguard_tests_healed_total" in metrics_text
