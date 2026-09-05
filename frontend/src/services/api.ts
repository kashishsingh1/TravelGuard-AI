import { BookingResponse, Flight, FlightSearchParams, PassengerDetails } from '../types';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

export class ApiError extends Error {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export async function searchFlights(params: FlightSearchParams): Promise<Flight[]> {
  const query = new URLSearchParams({
    origin: params.origin,
    destination: params.destination,
    date: params.date,
  });

  try {
    const res = await fetch(`${API_BASE}/api/flights?${query.toString()}`);
    if (!res.ok) {
      throw new ApiError(`Failed to fetch flights: HTTP ${res.status}`, res.status);
    }
    const data = await res.json();
    return data.flights || [];
  } catch (err) {
    if (err instanceof ApiError) throw err;
    throw new ApiError('Backend service unavailable. Please ensure the backend server is running on port 8000.');
  }
}

export async function createBooking(flight: Flight, passenger: PassengerDetails): Promise<BookingResponse> {
  const payload = {
    flight_id: flight.id,
    flight_airline: flight.airline,
    flight_number: flight.flight_number,
    origin: flight.origin,
    destination: flight.destination,
    departure_time: flight.departure_time,
    price: flight.price,
    passenger: {
      full_name: passenger.full_name.trim(),
      email: passenger.email.trim(),
      phone: passenger.phone.trim(),
    },
  };

  try {
    const res = await fetch(`${API_BASE}/api/book`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      const detail = errBody.detail || 'Unable to complete booking. Please try again.';
      throw new ApiError(detail, res.status);
    }

    return await res.json();
  } catch (err) {
    if (err instanceof ApiError) throw err;
    throw new ApiError('Unable to complete booking. Please try again.');
  }
}

export async function checkBackendHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/health`);
    return res.ok;
  } catch {
    return false;
  }
}
