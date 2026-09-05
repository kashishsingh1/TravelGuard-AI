import React, { useState } from 'react';
import { Header } from './components/Header';
import { SearchForm } from './components/SearchForm';
import { FlightResults } from './components/FlightResults';
import { PassengerForm } from './components/PassengerForm';
import { Confirmation } from './components/Confirmation';
import { ErrorBanner } from './components/ErrorBanner';
import { searchFlights, createBooking } from './services/api';
import { BookingResponse, BookingStep, Flight, FlightSearchParams, PassengerDetails } from './types';

export const App: React.FC = () => {
  const [step, setStep] = useState<BookingStep>('search');
  const [searchParams, setSearchParams] = useState<FlightSearchParams>({
    origin: 'Delhi',
    destination: 'Dubai',
    date: new Date(Date.now() + 7 * 86400000).toISOString().split('T')[0],
  });
  const [flights, setFlights] = useState<Flight[]>([]);
  const [selectedFlight, setSelectedFlight] = useState<Flight | null>(null);
  const [passenger, setPassenger] = useState<PassengerDetails | null>(null);
  const [booking, setBooking] = useState<BookingResponse | null>(null);

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string>('');

  // 1. Handle Search Flights
  const handleSearch = async (params: FlightSearchParams) => {
    setIsLoading(true);
    setErrorMessage('');
    setSearchParams(params);

    try {
      const results = await searchFlights(params);
      setFlights(results);
      setStep('results');
    } catch (err: any) {
      setErrorMessage(err.message || 'Unable to load flights. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  // 2. Handle Flight Selection
  const handleSelectFlight = (flight: Flight) => {
    setSelectedFlight(flight);
    setErrorMessage('');
    setStep('passenger');
  };

  // 3. Handle Booking Submission
  const handleBookFlight = async (details: PassengerDetails) => {
    if (!selectedFlight) return;

    setIsLoading(true);
    setErrorMessage('');
    setPassenger(details);

    try {
      const result = await createBooking(selectedFlight, details);
      setBooking(result);
      setStep('confirmation');
    } catch (err: any) {
      setErrorMessage(err.message || 'Unable to complete booking. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  // 4. Reset to Start
  const handleReset = () => {
    setStep('search');
    setSelectedFlight(null);
    setPassenger(null);
    setBooking(null);
    setErrorMessage('');
  };

  return (
    <div className="app-layout">
      <Header currentStep={step} onReset={handleReset} />

      <main className="main-content">
        <div className="content-wrapper">
          <ErrorBanner message={errorMessage} onDismiss={() => setErrorMessage('')} />

          {step === 'search' && (
            <SearchForm
              onSearch={handleSearch}
              isLoading={isLoading}
              initialParams={searchParams}
            />
          )}

          {step === 'results' && (
            <FlightResults
              flights={flights}
              searchParams={searchParams}
              onSelectFlight={handleSelectFlight}
              onBackToSearch={() => setStep('search')}
            />
          )}

          {step === 'passenger' && selectedFlight && (
            <PassengerForm
              flight={selectedFlight}
              onSubmit={handleBookFlight}
              onBack={() => setStep('results')}
              isLoading={isLoading}
              serverError={errorMessage}
            />
          )}

          {step === 'confirmation' && booking && selectedFlight && passenger && (
            <Confirmation
              booking={booking}
              flight={selectedFlight}
              passenger={passenger}
              onReset={handleReset}
            />
          )}
        </div>
      </main>

      <footer className="site-footer">
        <div className="footer-inner">
          <p>
            SkyBook Travel System • Controlled System Under Test (SUT) for{' '}
            <strong>TravelGuard AI</strong>
          </p>
          <span className="footer-version">v0.1.0 • Increment 1</span>
        </div>
      </footer>
    </div>
  );
};

export default App;
