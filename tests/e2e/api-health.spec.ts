import { test, expect } from '@playwright/test';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

test.describe('TEST 5: Backend & Booking API Health Checks', () => {
  test('should return status ok on GET /api/health', async ({ request }) => {
    const response = await request.get(`${BACKEND_URL}/api/health`);
    expect(response.status()).toBe(200);

    const data = await response.json();
    expect(data).toEqual({ status: 'ok' });
  });

  test('should retrieve mock flight inventory on GET /api/flights', async ({ request }) => {
    const response = await request.get(`${BACKEND_URL}/api/flights?origin=Delhi&destination=Dubai`);
    expect(response.status()).toBe(200);

    const data = await response.json();
    expect(data.flights).toBeInstanceOf(Array);
    expect(data.flights.length).toBeGreaterThanOrEqual(1);

    const first = data.flights[0];
    expect(first).toHaveProperty('id');
    expect(first).toHaveProperty('airline');
    expect(first).toHaveProperty('price');
    expect(first.origin.toLowerCase()).toBe('delhi');
    expect(first.destination.toLowerCase()).toBe('dubai');
  });

  test('should successfully create booking on POST /api/book', async ({ request }) => {
    const payload = {
      flight_id: 'FL-001',
      flight_airline: 'IndiGo',
      flight_number: '6E-1405',
      origin: 'Delhi',
      destination: 'Dubai',
      departure_time: '14:30',
      price: 18450,
      passenger: {
        full_name: 'Test Passenger',
        email: 'passenger@example.com',
        phone: '+91 99999 88888',
      },
    };

    const response = await request.post(`${BACKEND_URL}/api/book`, {
      data: payload,
    });
    expect(response.status()).toBe(201);

    const data = await response.json();
    expect(data.success).toBe(true);
    expect(data.booking_id).toMatch(/^SKB-\d+$/);
    expect(data.passenger_name).toBe('Test Passenger');
  });

  test('should return structured information on GET /api/llm/health without leaking secrets', async ({ request }) => {
    const response = await request.get(`${BACKEND_URL}/api/llm/health`);
    expect(response.status()).toBe(200);

    const data = await response.json();
    expect(data).toHaveProperty('success');

    // Ensure no API keys or raw authorization tokens are present anywhere in the response
    const rawText = JSON.stringify(data);
    expect(rawText).not.toContain('Bearer');
    expect(rawText).not.toContain('DEEPSEEK_API_KEY');
    expect(rawText).not.toContain('GROQ_API_KEY');

    // If keys are not set locally, success will be false with an error message
    // If keys are set, success will be true with provider and model
    if (data.success) {
      expect(['deepseek', 'groq']).toContain(data.provider);
      expect(data).toHaveProperty('model');
    } else {
      expect(data).toHaveProperty('error');
    }
  });
});
