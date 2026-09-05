import React from 'react';
import { Plane, ShieldCheck } from 'lucide-react';
import { BookingStep } from '../types';

interface HeaderProps {
  currentStep: BookingStep;
  onReset: () => void;
  onOpenConsole?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ currentStep, onReset, onOpenConsole }) => {
  const steps: { key: BookingStep; label: string; number: number }[] = [
    { key: 'search', label: 'Search', number: 1 },
    { key: 'results', label: 'Flights', number: 2 },
    { key: 'passenger', label: 'Passenger', number: 3 },
    { key: 'confirmation', label: 'Confirmation', number: 4 },
  ];

  const getStepStatus = (stepKey: BookingStep) => {
    const order: BookingStep[] = ['search', 'results', 'passenger', 'confirmation'];
    const currentIndex = order.indexOf(currentStep);
    const stepIndex = order.indexOf(stepKey);

    if (stepIndex < currentIndex) return 'completed';
    if (stepIndex === currentIndex) return 'active';
    return 'pending';
  };

  return (
    <header className="site-header">
      <div className="header-container">
        <div className="brand-section" onClick={onReset} style={{ cursor: 'pointer' }}>
          <div className="logo-icon-wrapper">
            <Plane className="logo-icon" size={26} />
          </div>
          <div className="brand-text">
            <span className="brand-name">SkyBook</span>
            <span className="brand-tagline">Flight Booking</span>
          </div>
        </div>

        <div
          className="sut-badge"
          title="Open TravelGuard AI Developer Console"
          onClick={onOpenConsole}
          style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.45rem' }}
        >
          <ShieldCheck size={16} className="sut-icon" />
          <span>TravelGuard Dev Console</span>
          <span style={{ fontSize: '0.7rem', background: '#38bdf8', color: '#090d16', padding: '0.1rem 0.45rem', borderRadius: '4px', fontWeight: 700 }}>
            OPEN
          </span>
        </div>
      </div>

      <nav className="stepper-bar" aria-label="Booking progress">
        <div className="stepper-container">
          {steps.map((step, idx) => {
            const status = getStepStatus(step.key);
            return (
              <React.Fragment key={step.key}>
                <div className={`step-item ${status}`}>
                  <span className="step-circle">{step.number}</span>
                  <span className="step-label">{step.label}</span>
                </div>
                {idx < steps.length - 1 && <div className={`step-divider ${status === 'completed' ? 'filled' : ''}`} />}
              </React.Fragment>
            );
          })}
        </div>
      </nav>
    </header>
  );
};
