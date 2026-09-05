"""Flight models for SkyBook."""

from typing import List, Optional
from pydantic import BaseModel, Field


class Flight(BaseModel):
    """Flight information schema."""

    id: str = Field(..., description="Unique flight identifier")
    airline: str = Field(..., description="Airline name (e.g., IndiGo, Air India)")
    flight_number: str = Field(..., description="Flight code, e.g. 6E-105")
    origin: str = Field(..., description="Departure city or airport code")
    destination: str = Field(..., description="Arrival city or airport code")
    departure_time: str = Field(..., description="Departure time (e.g., 14:30)")
    arrival_time: str = Field(..., description="Arrival time (e.g., 17:20)")
    duration: str = Field(..., description="Flight duration (e.g., 3h 50m)")
    price: int = Field(..., description="Price in INR (e.g., 18450)")
    stops: str = Field(default="Non-stop", description="Stops description")


class FlightSearchQuery(BaseModel):
    """Search request query parameters."""

    origin: str = Field(..., min_length=2)
    destination: str = Field(..., min_length=2)
    date: str = Field(..., min_length=4)


class FlightSearchResponse(BaseModel):
    """Flight search response envelope."""

    flights: List[Flight]
    count: int
    query: Optional[dict] = None
