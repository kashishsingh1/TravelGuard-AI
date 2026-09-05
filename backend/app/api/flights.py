"""Flight search and catalogue API endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Query

from app.models.flight import Flight

router = APIRouter(prefix="/api/flights", tags=["flights"])

# Deterministic mock flights for SkyBook SUT
MOCK_FLIGHTS: List[dict] = [
    {
        "id": "FL-001",
        "airline": "IndiGo",
        "flight_number": "6E-1405",
        "origin": "Delhi",
        "destination": "Dubai",
        "departure_time": "14:30",
        "arrival_time": "17:20",
        "duration": "4h 20m",
        "price": 18450,
        "stops": "Non-stop",
    },
    {
        "id": "FL-002",
        "airline": "Air India",
        "flight_number": "AI-995",
        "origin": "Delhi",
        "destination": "Dubai",
        "departure_time": "18:10",
        "arrival_time": "21:05",
        "duration": "4h 25m",
        "price": 21200,
        "stops": "Non-stop",
    },
    {
        "id": "FL-003",
        "airline": "Emirates",
        "flight_number": "EK-511",
        "origin": "Delhi",
        "destination": "Dubai",
        "departure_time": "09:15",
        "arrival_time": "12:00",
        "duration": "4h 15m",
        "price": 29800,
        "stops": "Non-stop",
    },
    {
        "id": "FL-004",
        "airline": "SpiceJet",
        "flight_number": "SG-15",
        "origin": "Delhi",
        "destination": "Dubai",
        "departure_time": "22:00",
        "arrival_time": "00:50",
        "duration": "4h 20m",
        "price": 16900,
        "stops": "Non-stop",
    },
]


@router.get("", response_model=dict)
async def get_flights(
    origin: Optional[str] = Query(None, description="Departure city"),
    destination: Optional[str] = Query(None, description="Arrival city"),
    date: Optional[str] = Query(None, description="Flight date (YYYY-MM-DD)"),
):
    """Retrieve available flights matching criteria, or all mock flights."""
    if not origin or not destination:
        return {"flights": MOCK_FLIGHTS, "count": len(MOCK_FLIGHTS)}

    orig_clean = origin.strip().lower()
    dest_clean = destination.strip().lower()

    # Filter matching origin & destination
    matching = [
        f
        for f in MOCK_FLIGHTS
        if f["origin"].lower() == orig_clean and f["destination"].lower() == dest_clean
    ]

    # If no direct match in mock database, generate deterministic route flights
    if not matching:
        orig_title = origin.strip().title()
        dest_title = destination.strip().title()
        matching = [
            {
                "id": f"FL-GEN-1",
                "airline": "SkyAir Direct",
                "flight_number": "SK-101",
                "origin": orig_title,
                "destination": dest_title,
                "departure_time": "08:00",
                "arrival_time": "11:30",
                "duration": "3h 30m",
                "price": 14500,
                "stops": "Non-stop",
            },
            {
                "id": f"FL-GEN-2",
                "airline": "Global Wings",
                "flight_number": "GW-440",
                "origin": orig_title,
                "destination": dest_title,
                "departure_time": "16:45",
                "arrival_time": "20:15",
                "duration": "3h 30m",
                "price": 17800,
                "stops": "Non-stop",
            },
        ]

    return {
        "flights": matching,
        "count": len(matching),
        "query": {"origin": origin, "destination": destination, "date": date},
    }
