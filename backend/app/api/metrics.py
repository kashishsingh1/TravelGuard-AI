"""Prometheus metrics endpoint for SkyBook and TravelGuard AI."""

from fastapi import APIRouter, Response
from travelguard.observability import get_prometheus_metrics_text

router = APIRouter(tags=["Observability"])


@router.get("/metrics", summary="Prometheus metrics")
@router.get("/api/metrics", summary="Prometheus metrics (API alias)")
async def metrics():
    """Return Prometheus-compatible metrics text format."""
    content = get_prometheus_metrics_text()
    return Response(content=content, media_type="text/plain; version=0.0.4; charset=utf-8")
