"""Observability layer for TravelGuard AI: OpenTelemetry tracing & Prometheus metrics."""

import logging
import os
import time
from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional

logger = logging.getLogger("travelguard.observability")

# ─────────────────────────────────────────────────────────────────────────────
# OpenTelemetry Tracing Setup
# ─────────────────────────────────────────────────────────────────────────────
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

    # Check if a tracer provider is already registered
    _current_provider = trace.get_tracer_provider()
    if not isinstance(_current_provider, TracerProvider):
        _provider = TracerProvider()
        trace.set_tracer_provider(_provider)
    else:
        _provider = _current_provider

    tracer = trace.get_tracer("travelguard", "0.5.0")
    HAS_OTEL = True
except Exception as _otel_err:
    logger.debug(f"OpenTelemetry not fully configured: {_otel_err}")
    tracer = None
    HAS_OTEL = False


@contextmanager
def trace_span(name: str, attributes: Optional[Dict[str, Any]] = None) -> Generator[Any, None, None]:
    """Context manager for tracing an operation span."""
    if HAS_OTEL and tracer:
        with tracer.start_as_current_span(name) as span:
            if attributes:
                for k, v in attributes.items():
                    if isinstance(v, (str, int, float, bool)):
                        span.set_attribute(k, v)
                    else:
                        span.set_attribute(k, str(v))
            yield span
    else:
        yield None


# ─────────────────────────────────────────────────────────────────────────────
# Prometheus Metrics Setup
# ─────────────────────────────────────────────────────────────────────────────
try:
    from prometheus_client import (
        REGISTRY,
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )

    # Core TravelGuard Prometheus Metrics
    METRIC_TEST_RUNS = Counter(
        "travelguard_test_runs_total",
        "Total count of autonomous QA runs",
        ["status", "decision"],
    )
    METRIC_TEST_FAILURES = Counter(
        "travelguard_test_failures_total",
        "Total count of test failures encountered",
        ["classification"],
    )
    METRIC_TESTS_HEALED = Counter(
        "travelguard_tests_healed_total",
        "Total count of tests successfully self-healed",
    )
    METRIC_PRODUCT_DEFECTS = Counter(
        "travelguard_product_defects_total",
        "Total count of verified real product defects detected",
    )
    METRIC_ENV_FAILURES = Counter(
        "travelguard_environment_failures_total",
        "Total count of environment/infrastructure failures",
    )
    METRIC_LLM_REQUESTS = Counter(
        "travelguard_llm_requests_total",
        "Total count of LLM requests dispatched",
        ["provider"],
    )
    METRIC_LLM_FAILURES = Counter(
        "travelguard_llm_failures_total",
        "Total count of LLM request failures",
        ["provider"],
    )
    METRIC_HEALING_ATTEMPTS = Counter(
        "travelguard_healing_attempts_total",
        "Total count of self-healing patch attempts",
    )
    METRIC_HEALING_SUCCESS = Counter(
        "travelguard_healing_success_total",
        "Total count of self-healing successes verified on re-run",
    )
    METRIC_TEST_DURATION = Histogram(
        "travelguard_test_duration_seconds",
        "Duration of test execution in seconds",
        buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
    )
    METRIC_RELEASE_CONFIDENCE = Gauge(
        "travelguard_release_confidence",
        "Latest evaluated release confidence score (0.0 to 1.0)",
    )
    HAS_PROMETHEUS = True
except Exception as _prom_err:
    logger.debug(f"Prometheus client not initialized: {_prom_err}")
    HAS_PROMETHEUS = False


def record_run_metrics(
    status: str,
    decision: str,
    confidence: float,
    healed: int = 0,
    defects: int = 0,
    env_failures: int = 0,
    failures_by_type: Optional[Dict[str, int]] = None,
) -> None:
    """Record summary metrics for an autonomous run."""
    if not HAS_PROMETHEUS:
        return

    try:
        METRIC_TEST_RUNS.labels(status=status, decision=decision).inc()
        METRIC_RELEASE_CONFIDENCE.set(confidence)
        if healed > 0:
            METRIC_TESTS_HEALED.inc(healed)
        if defects > 0:
            METRIC_PRODUCT_DEFECTS.inc(defects)
        if env_failures > 0:
            METRIC_ENV_FAILURES.inc(env_failures)
        if failures_by_type:
            for cls_name, count in failures_by_type.items():
                METRIC_TEST_FAILURES.labels(classification=cls_name).inc(count)
    except Exception as exc:
        logger.debug(f"Error recording Prometheus metrics: {exc}")


def get_prometheus_metrics_text() -> str:
    """Return latest Prometheus metrics text for /metrics endpoint."""
    if not HAS_PROMETHEUS:
        return "# Prometheus metrics not available\n"
    return generate_latest(REGISTRY).decode("utf-8")
