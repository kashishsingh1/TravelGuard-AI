import { test, expect } from '@playwright/test';

test.describe('TEST 3: End-to-End Booking Workflow', () => {
  test('should complete flight booking and display confirmation with booking ID', async ({ page }) => {
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

    // 5. Click Book Flight
    await page.locator('[data-testid="book-flight"]').click();

    // 6. Verify confirmation screen appears
    const confirmation = page.locator('[data-testid="booking-confirmation"]');
    await expect(confirmation).toBeVisible();
    await expect(confirmation).toContainText('Booking Confirmed');

    // 7. Verify booking ID exists and matches deterministic pattern SKB-xxxxx
    const bookingIdElem = page.locator('[data-testid="booking-id"]');
    await expect(bookingIdElem).toBeVisible();
    const bookingIdText = await bookingIdElem.textContent();
    expect(bookingIdText).toMatch(/^SKB-\d+$/);

    // 8. Verify passenger and route are displayed on confirmation
    await expect(confirmation).toContainText('John Doe');
    await expect(confirmation).toContainText('Delhi');
    await expect(confirmation).toContainText('Dubai');

    // 9. Verify "Book Another Flight" button is present and functional
    const bookAnotherBtn = page.locator('[data-testid="book-another"]');
    await expect(bookAnotherBtn).toBeVisible();
    await bookAnotherBtn.click();
    await expect(page.locator('[data-testid="search-flights"]')).toBeVisible();
  });
});
