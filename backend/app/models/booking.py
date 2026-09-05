"""Booking models for SkyBook."""

from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class PassengerDetails(BaseModel):
    """Passenger information."""

    full_name: str = Field(..., min_length=2, max_length=100, description="Full name of passenger")
    email: EmailStr = Field(..., description="Valid email address")
    phone: str = Field(..., min_length=7, max_length=20, description="Phone number")


class BookingRequest(BaseModel):
    """Flight booking request payload."""

    flight_id: str = Field(..., description="ID of the selected flight")
    flight_airline: str = Field(..., description="Airline name")
    flight_number: str = Field(default="", description="Flight number")
    origin: str = Field(..., description="Flight origin")
    destination: str = Field(..., description="Flight destination")
    departure_time: str = Field(default="", description="Departure time")
    price: int = Field(..., description="Flight price in INR")
    passenger: PassengerDetails = Field(..., description="Passenger details")


class BookingResponse(BaseModel):
    """Booking confirmation response."""

    success: bool
    booking_id: str
    message: str = "Booking confirmed successfully"
    flight_id: Optional[str] = None
    passenger_name: Optional[str] = None
    route: Optional[str] = None
    created_at: Optional[str] = None
