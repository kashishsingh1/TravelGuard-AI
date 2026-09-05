import { test, expect } from '@playwright/test';

test.describe('TEST: Flight Booking Drift Detection', () => {
  test('should complete flight booking using role-based submit locator', async ({ page }) => {
    // 1. Open SkyBook
    await page.goto('/');

    // 2. Search flights
    await page.locator('[data-testid="from-input"]').fill('Delhi');
    await page.locator('[data-testid="to-input"]').fill('Dubai');
    await page.locator('[data-testid="date-input"]').fill('2026-09-15');
    await page.locator('[data-testid="search-flights"]').click();

    // 3. Select first flight
    const selectButton = page.locator('[data-testid="select-flight"]').first();
    await expect(selectButton).toBeVisible();
    await selectButton.click();

    // 4. Enter passenger details
    await page.locator('[data-testid="passenger-name"]').fill('John Doe');
    await page.locator('[data-testid="passenger-email"]').fill('john.doe@example.com');
    await page.locator('[data-testid="passenger-phone"]').fill('+91 98765 43210');

    // 5. Submit booking using getByRole locator (target for drift detection / self-healing)
    await page.getByRole('button', { name: 'Book Flight' }).click();

    // 6. Verify booking confirmation
    const confirmation = page.locator('[data-testid="booking-confirmation"]');
    await expect(confirmation).toBeVisible();
    await expect(confirmation).toContainText('Booking Confirmed');

    // 7. Verify booking ID format
    const bookingIdElem = page.locator('[data-testid="booking-id"]');
    await expect(bookingIdElem).toBeVisible();
    const bookingIdText = await bookingIdElem.textContent();
    expect(bookingIdText).toMatch(/^SKB-\d+$/);
  });
});
