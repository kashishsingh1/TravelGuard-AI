import { test, expect } from '@playwright/test';

test.describe('TEST 1: Flight Search Workflow', () => {
  test('should search for flights from Delhi to Dubai and display results', async ({ page }) => {
    // 1. Open SkyBook
    await page.goto('/');

    // Verify title and search inputs exist
    await expect(page.locator('h1')).toContainText('Flight Booking');
    const fromInput = page.locator('[data-testid="from-input"]');
    const toInput = page.locator('[data-testid="to-input"]');
    const dateInput = page.locator('[data-testid="date-input"]');
    const searchButton = page.locator('[data-testid="search-flights"]');

    // 2. Enter origin
    await fromInput.fill('Delhi');

    // 3. Enter destination
    await toInput.fill('Dubai');

    // 4. Select date (e.g. 2026-09-15)
    await dateInput.fill('2026-09-15');

    // 5. Click Search Flights
    await searchButton.click();

    // 6. Verify flight results appear
    const resultsContainer = page.locator('[data-testid="flight-results"]');
    await expect(resultsContainer).toBeVisible();

    const flightCards = page.locator('[data-testid="flight-card"]');
    await expect(flightCards.first()).toBeVisible();
    const count = await flightCards.count();
    expect(count).toBeGreaterThanOrEqual(2);

    // Verify mock flight details are rendered
    await expect(resultsContainer).toContainText('Delhi');
    await expect(resultsContainer).toContainText('Dubai');
    await expect(page.locator('[data-testid="select-flight"]').first()).toBeVisible();
  });
});
