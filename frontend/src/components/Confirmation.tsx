import React from 'react';
import { CheckCircle2, Plane, Calendar, User, Ticket, ArrowRight, RotateCcw } from 'lucide-react';
import { BookingResponse, Flight, PassengerDetails } from '../types';

interface ConfirmationProps {
  booking: BookingResponse;
  flight: Flight;
  passenger: PassengerDetails;
  onReset: () => void;
}

export const Confirmation: React.FC<ConfirmationProps> = ({
  booking,
  flight,
  passenger,
  onReset,
}) => {
  return (
    <div className="confirmation-container" data-testid="booking-confirmation">
      {/* Success Badge */}
      <div className="success-hero">
        <div className="success-icon-wrapper">
          <CheckCircle2 size={54} className="success-icon" />
        </div>
        <h1 className="confirmation-heading">✓ Booking Confirmed</h1>
        <p className="confirmation-subhead">
          Your reservation has been processed and your e-ticket is confirmed.
        </p>

        <div className="booking-id-pill">
          <span className="booking-id-label">Booking ID:</span>
          <strong className="booking-id-value" data-testid="booking-id">
            {booking.booking_id}
          </strong>
        </div>
      </div>

      {/* Ticket Card */}
      <div className="ticket-card">
        <div className="ticket-header">
          <div className="ticket-airline">
            <Plane size={20} />
            <span>{flight.airline}</span>
            <span className="ticket-flight-no">({flight.flight_number})</span>
          </div>
          <div className="ticket-status-badge">Confirmed</div>
        </div>

        <div className="ticket-body">
          {/* Route details */}
          <div className="ticket-route-row">
            <div className="route-endpoint">
              <span className="endpoint-time">{flight.departure_time}</span>
              <span className="endpoint-city">{flight.origin}</span>
            </div>

            <div className="route-connector">
              <span className="connector-duration">{flight.duration}</span>
              <div className="connector-line">
                <ArrowRight size={18} />
              </div>
              <span className="connector-type">{flight.stops}</span>
            </div>

            <div className="route-endpoint text-right">
              <span className="endpoint-time">{flight.arrival_time}</span>
              <span className="endpoint-city">{flight.destination}</span>
            </div>
          </div>

          <div className="ticket-divider" />

          {/* Passenger & Fare grid */}
          <div className="ticket-grid">
            <div className="ticket-info-item">
              <span className="info-label">Passenger:</span>
              <strong className="info-val">{passenger.full_name}</strong>
            </div>

            <div className="ticket-info-item">
              <span className="info-label">Email:</span>
              <span className="info-val">{passenger.email}</span>
            </div>

            <div className="ticket-info-item">
              <span className="info-label">Phone:</span>
              <span className="info-val">{passenger.phone}</span>
            </div>

            <div className="ticket-info-item">
              <span className="info-label">Total Paid:</span>
              <strong className="info-val fare-highlight">₹{flight.price.toLocaleString('en-IN')}</strong>
            </div>
          </div>
        </div>

        <div className="ticket-stub-footer">
          <span className="stub-notice">System Under Test (SUT) • Deterministic Test Booking</span>
        </div>
      </div>

      {/* Action Row */}
      <div className="confirmation-action-row">
        <button
          type="button"
          data-testid="book-another"
          onClick={onReset}
          className="btn btn-primary btn-large book-another-btn"
        >
          <RotateCcw size={18} />
          <span>Book Another Flight</span>
        </button>
      </div>
    </div>
  );
};
