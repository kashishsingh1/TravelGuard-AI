import React, { useState } from 'react';
import { User, Mail, Phone, ArrowLeft, Plane, Shield } from 'lucide-react';
import { Flight, PassengerDetails } from '../types';

interface PassengerFormProps {
  flight: Flight;
  onSubmit: (details: PassengerDetails) => void;
  onBack: () => void;
  isLoading: boolean;
  serverError?: string;
}

export const PassengerForm: React.FC<PassengerFormProps> = ({
  flight,
  onSubmit,
  onBack,
  isLoading,
  serverError,
}) => {
  const [fullName, setFullName] = useState<string>('');
  const [email, setEmail] = useState<string>('');
  const [phone, setPhone] = useState<string>('');
  const [validationError, setValidationError] = useState<string>('');

  const validate = (): boolean => {
    const trimmedName = fullName.trim();
    const trimmedEmail = email.trim();
    const trimmedPhone = phone.trim();

    if (!trimmedName) {
      setValidationError('Full Name is required.');
      return false;
    }
    if (trimmedName.length < 2) {
      setValidationError('Full Name must be at least 2 characters long.');
      return false;
    }

    if (!trimmedEmail) {
      setValidationError('Email is required.');
      return false;
    }
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(trimmedEmail)) {
      setValidationError('Please enter a valid email address (e.g., passenger@example.com).');
      return false;
    }

    if (!trimmedPhone) {
      setValidationError('Phone number is required.');
      return false;
    }
    if (trimmedPhone.length < 7) {
      setValidationError('Please enter a valid phone number (at least 7 digits).');
      return false;
    }

    setValidationError('');
    return true;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) {
      return;
    }
    onSubmit({
      full_name: fullName.trim(),
      email: email.trim(),
      phone: phone.trim(),
    });
  };

  const displayError = validationError || serverError;

  return (
    <div className="passenger-container">
      <div className="passenger-header">
        <button type="button" onClick={onBack} className="btn-back">
          <ArrowLeft size={18} />
          <span>Back to Flights</span>
        </button>
      </div>

      <div className="passenger-layout">
        {/* Main form card */}
        <div className="passenger-card">
          <h2 className="passenger-title">Passenger Information</h2>
          <p className="passenger-subtitle">
            Enter passenger details as they appear on government-issued identification.
          </p>

          {displayError && (
            <div
              className="form-error-banner"
              data-testid="error-message"
              role="alert"
              aria-live="polite"
            >
              {displayError}
            </div>
          )}

          <form onSubmit={handleSubmit} className="passenger-form" noValidate>
            {/* Full Name */}
            <div className="form-group">
              <label htmlFor="passenger-name" className="form-label">
                <User size={16} className="label-icon" />
                <span>Full Name</span>
              </label>
              <input
                id="passenger-name"
                name="passenger-name"
                type="text"
                data-testid="passenger-name"
                className="form-input"
                placeholder="e.g. John Doe"
                value={fullName}
                onChange={(e) => {
                  setFullName(e.target.value);
                  if (validationError) setValidationError('');
                }}
                required
              />
            </div>

            {/* Email Address */}
            <div className="form-group">
              <label htmlFor="passenger-email" className="form-label">
                <Mail size={16} className="label-icon" />
                <span>Email Address</span>
              </label>
              <input
                id="passenger-email"
                name="passenger-email"
                type="email"
                data-testid="passenger-email"
                className="form-input"
                placeholder="e.g. john.doe@example.com"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  if (validationError) setValidationError('');
                }}
                required
              />
            </div>

            {/* Phone Number */}
            <div className="form-group">
              <label htmlFor="passenger-phone" className="form-label">
                <Phone size={16} className="label-icon" />
                <span>Phone Number</span>
              </label>
              <input
                id="passenger-phone"
                name="passenger-phone"
                type="tel"
                data-testid="passenger-phone"
                className="form-input"
                placeholder="e.g. +91 98765 43210"
                value={phone}
                onChange={(e) => {
                  setPhone(e.target.value);
                  if (validationError) setValidationError('');
                }}
                required
              />
            </div>

            <div className="passenger-submit-row">
              <button
                type="submit"
                data-testid="book-flight"
                className="btn btn-primary btn-large book-flight-btn"
                disabled={isLoading}
              >
                {isLoading ? 'Processing Booking...' : 'Book Flight'}
              </button>
            </div>
          </form>
        </div>

        {/* Selected flight summary side-card */}
        <aside className="flight-summary-sidebar" aria-label="Selected flight overview">
          <div className="summary-card">
            <h3 className="summary-title">Selected Flight</h3>
            <div className="summary-airline">
              <Plane size={20} className="summary-icon" />
              <div>
                <strong>{flight.airline}</strong>
                <span className="summary-sub">{flight.flight_number}</span>
              </div>
            </div>

            <div className="summary-route">
              <div className="summary-point">
                <span className="point-time">{flight.departure_time}</span>
                <span className="point-city">{flight.origin}</span>
              </div>
              <div className="summary-duration">{flight.duration}</div>
              <div className="summary-point">
                <span className="point-time">{flight.arrival_time}</span>
                <span className="point-city">{flight.destination}</span>
              </div>
            </div>

            <div className="summary-divider" />

            <div className="summary-fare">
              <span>Total Payable</span>
              <span className="fare-total">₹{flight.price.toLocaleString('en-IN')}</span>
            </div>

            <div className="security-notice">
              <Shield size={16} />
              <span>Test booking environment • Instant confirmation</span>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
};
