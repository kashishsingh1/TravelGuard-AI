export interface Flight {
  id: string;
  airline: string;
  flight_number: string;
  origin: string;
  destination: string;
  departure_time: string;
  arrival_time: string;
  duration: string;
  price: number;
  stops: string;
}

export interface FlightSearchParams {
  origin: string;
  destination: string;
  date: string;
}

export interface PassengerDetails {
  full_name: string;
  email: string;
  phone: string;
}

export interface BookingResponse {
  success: boolean;
  booking_id: string;
  message: string;
  flight_id?: string;
  passenger_name?: string;
  route?: string;
  created_at?: string;
}

export type BookingStep = 'search' | 'results' | 'passenger' | 'confirmation';
