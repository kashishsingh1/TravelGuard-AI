"""API unit tests for health, flights, and booking."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_check():
    """Verify /api/health returns status ok."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/health")
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_flights_catalogue():
    """Verify /api/flights returns default list of flights."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/flights")
        assert res.status_code == 200
        data = res.json()
        assert "flights" in data
        assert len(data["flights"]) >= 4
        # Verify first flight structure
        f = data["flights"][0]
        assert "id" in f
        assert "airline" in f
        assert "price" in f


@pytest.mark.asyncio
async def test_flights_search_filter():
    """Verify searching flights from Delhi to Dubai returns matches."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/flights?origin=Delhi&destination=Dubai&date=2026-09-15")
        assert res.status_code == 200
        data = res.json()
        assert len(data["flights"]) >= 2
        for f in data["flights"]:
            assert f["origin"].lower() == "delhi"
            assert f["destination"].lower() == "dubai"


@pytest.mark.asyncio
async def test_booking_success():
    """Verify /api/book creates a booking and returns booking_id."""
    payload = {
        "flight_id": "FL-001",
        "flight_airline": "IndiGo",
        "origin": "Delhi",
        "destination": "Dubai",
        "price": 18450,
        "passenger": {
            "full_name": "John Doe",
            "email": "john.doe@example.com",
            "phone": "+91 98765 43210",
        },
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/api/book", json=payload)
        assert res.status_code == 201
        data = res.json()
        assert data["success"] is True
        assert data["booking_id"].startswith("SKB-")
        assert data["passenger_name"] == "John Doe"


@pytest.mark.asyncio
async def test_booking_validation_failure():
    """Verify /api/book rejects empty/invalid passenger data."""
    payload = {
        "flight_id": "FL-001",
        "flight_airline": "IndiGo",
        "origin": "Delhi",
        "destination": "Dubai",
        "price": 18450,
        "passenger": {
            "full_name": "",  # Invalid: empty name
            "email": "not-an-email",
            "phone": "",
        },
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/api/book", json=payload)
        assert res.status_code in (400, 422)
