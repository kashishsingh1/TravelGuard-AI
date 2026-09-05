import React, { useState } from 'react';
import { MapPin, Calendar, ArrowRightLeft, Search } from 'lucide-react';
import { FlightSearchParams } from '../types';

interface SearchFormProps {
  onSearch: (params: FlightSearchParams) => void;
  isLoading: boolean;
  initialParams?: FlightSearchParams;
}

export const SearchForm: React.FC<SearchFormProps> = ({ onSearch, isLoading, initialParams }) => {
  // Default to prompt specs: From Delhi, To Dubai, 7 days from now
  const defaultDate = () => {
    const d = new Date();
    d.setDate(d.getDate() + 7);
    return d.toISOString().split('T')[0];
  };

  const [origin, setOrigin] = useState<string>(initialParams?.origin || 'Delhi');
  const [destination, setDestination] = useState<string>(initialParams?.destination || 'Dubai');
  const [date, setDate] = useState<string>(initialParams?.date || defaultDate());
  const [error, setError] = useState<string>('');

  const handleSwap = () => {
    const temp = origin;
    setOrigin(destination);
    setDestination(temp);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!origin.trim()) {
      setError('Please enter an origin city');
      return;
    }
    if (!destination.trim()) {
      setError('Please enter a destination city');
      return;
    }
    if (!date) {
      setError('Please select a travel date');
      return;
    }
    setError('');
    onSearch({ origin: origin.trim(), destination: destination.trim(), date });
  };

  return (
    <div className="search-card">
      <div className="search-card-header">
        <h1 className="search-title">Flight Booking</h1>
        <p className="search-subtitle">Search domestic and international flights across major carriers</p>
      </div>

      {error && (
        <div className="form-error-banner" data-testid="error-message" role="alert">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="flight-search-form" noValidate>
        <div className="search-grid">
          {/* Origin field */}
          <div className="form-group">
            <label htmlFor="from-input" className="form-label">
              <MapPin size={16} className="label-icon" />
              <span>From</span>
            </label>
            <input
              id="from-input"
              name="origin"
              type="text"
              data-testid="from-input"
              className="form-input"
              placeholder="e.g. Delhi"
              value={origin}
              onChange={(e) => setOrigin(e.target.value)}
              required
            />
          </div>

          {/* Swap icon */}
          <button
            type="button"
            className="swap-button"
            onClick={handleSwap}
            aria-label="Swap origin and destination"
            title="Swap locations"
          >
            <ArrowRightLeft size={18} />
          </button>

          {/* Destination field */}
          <div className="form-group">
            <label htmlFor="to-input" className="form-label">
              <MapPin size={16} className="label-icon" />
              <span>To</span>
            </label>
            <input
              id="to-input"
              name="destination"
              type="text"
              data-testid="to-input"
              className="form-input"
              placeholder="e.g. Dubai"
              value={destination}
              onChange={(e) => setDestination(e.target.value)}
              required
            />
          </div>

          {/* Date field */}
          <div className="form-group">
            <label htmlFor="date-input" className="form-label">
              <Calendar size={16} className="label-icon" />
              <span>Date</span>
            </label>
            <input
              id="date-input"
              name="date"
              type="date"
              data-testid="date-input"
              className="form-input"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              required
            />
          </div>
        </div>

        <div className="search-action-row">
          <button
            type="submit"
            data-testid="search-flights"
            className="btn btn-primary btn-large search-submit-btn"
            disabled={isLoading}
          >
            <Search size={20} />
            <span>{isLoading ? 'Searching Flights...' : 'Search Flights'}</span>
          </button>
        </div>
      </form>
    </div>
  );
};
