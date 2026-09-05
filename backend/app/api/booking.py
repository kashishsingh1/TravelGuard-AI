"""Booking management API endpoints."""

import random
from datetime import datetime, timezone
from typing import Dict, List
from fastapi import APIRouter, HTTPException, status

from app.models.booking import BookingRequest, BookingResponse

router = APIRouter(prefix="/api/book", tags=["booking"])

# In-memory storage for demonstration / verification
IN_MEMORY_BOOKINGS: List[Dict] = []
BOOKING_COUNTER = 82931


@router.post("", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
async def create_booking(payload: BookingRequest):
    """Create a new flight booking."""
    global BOOKING_COUNTER

    # Basic business validation
    if not payload.passenger.full_name or len(payload.passenger.full_name.strip()) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Valid passenger full name is required",
        )

    if not payload.passenger.phone or len(payload.passenger.phone.strip()) < 7:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Valid phone number is required",
        )

    # Generate booking ID (deterministic pattern SKB-xxxxx)
    booking_id = f"SKB-{BOOKING_COUNTER}"
    BOOKING_COUNTER += 1

    record = {
        "booking_id": booking_id,
        "flight_id": payload.flight_id,
        "airline": payload.flight_airline,
        "origin": payload.origin,
        "destination": payload.destination,
        "price": payload.price,
        "passenger": payload.passenger.model_dump(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    IN_MEMORY_BOOKINGS.append(record)

    return BookingResponse(
        success=True,
        booking_id=booking_id,
        message="Booking confirmed successfully",
        flight_id=payload.flight_id,
        passenger_name=payload.passenger.full_name,
        route=f"{payload.origin} → {payload.destination}",
        created_at=record["created_at"],
    )


@router.get("/recent")
async def get_recent_bookings():
    """Retrieve recent bookings in memory (helper for inspection)."""
    return {"bookings": IN_MEMORY_BOOKINGS}
