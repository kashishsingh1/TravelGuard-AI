import React from 'react';
import { ArrowRight, Clock, Plane, ArrowLeft } from 'lucide-react';
import { Flight, FlightSearchParams } from '../types';

interface FlightResultsProps {
  flights: Flight[];
  searchParams: FlightSearchParams;
  onSelectFlight: (flight: Flight) => void;
  onBackToSearch: () => void;
}

export const FlightResults: React.FC<FlightResultsProps> = ({
  flights,
  searchParams,
  onSelectFlight,
  onBackToSearch,
}) => {
  return (
    <div className="results-container" data-testid="flight-results">
      <div className="results-header">
        <button type="button" onClick={onBackToSearch} className="btn-back">
          <ArrowLeft size={18} />
          <span>Modify Search</span>
        </button>

        <div className="route-banner">
          <h2 className="route-title">
            <span>{searchParams.origin}</span>
            <ArrowRight size={20} className="route-arrow" />
            <span>{searchParams.destination}</span>
          </h2>
          <span className="route-meta">
            {new Date(searchParams.date).toLocaleDateString('en-US', {
              weekday: 'short',
              month: 'short',
              day: 'numeric',
              year: 'numeric',
            })}{' '}
            • {flights.length} {flights.length === 1 ? 'flight' : 'flights'} available
          </span>
        </div>
      </div>

      {flights.length === 0 ? (
        <div className="empty-results-card">
          <Plane size={48} className="empty-icon" />
          <h3>No flights found for this route</h3>
          <p>Please try searching for another origin or destination city.</p>
          <button type="button" onClick={onBackToSearch} className="btn btn-secondary">
            Back to Search
          </button>
        </div>
      ) : (
        <div className="flights-list">
          {flights.map((flight) => (
            <div key={flight.id} className="flight-card" data-testid="flight-card">
              <div className="flight-card-main">
                {/* Airline info */}
                <div className="airline-col">
                  <div className="airline-avatar">
                    <Plane size={22} />
                  </div>
                  <div>
                    <h3 className="airline-name">{flight.airline}</h3>
                    <span className="flight-no">{flight.flight_number}</span>
                  </div>
                </div>

                {/* Timing & Route */}
                <div className="timing-col">
                  <div className="time-block">
                    <span className="time-val">{flight.departure_time}</span>
                    <span className="city-label">{flight.origin}</span>
                  </div>

                  <div className="duration-block">
                    <span className="duration-text">{flight.duration}</span>
                    <div className="flight-visual-line">
                      <div className="dot" />
                      <div className="line" />
                      <Plane size={14} className="plane-mini" />
                      <div className="line" />
                      <div className="dot" />
                    </div>
                    <span className="stops-label">{flight.stops}</span>
                  </div>

                  <div className="time-block">
                    <span className="time-val">{flight.arrival_time}</span>
                    <span className="city-label">{flight.destination}</span>
                  </div>
                </div>

                {/* Price & Action */}
                <div className="price-action-col">
                  <div className="price-box">
                    <span className="price-currency">₹</span>
                    <span className="price-amount">{flight.price.toLocaleString('en-IN')}</span>
                    <span className="price-sub">per passenger</span>
                  </div>

                  <button
                    type="button"
                    data-testid="select-flight"
                    onClick={() => onSelectFlight(flight)}
                    className="btn btn-primary select-flight-btn"
                  >
                    Select Flight
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
