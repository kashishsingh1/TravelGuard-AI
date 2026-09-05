import { test, expect } from '@playwright/test';

test.describe('TEST 2: Flight Selection', () => {
  test('should allow user to select a flight and navigate to passenger details', async ({ page }) => {
    // 1. Open SkyBook
    await page.goto('/');

    // 2. Perform search
    await page.locator('[data-testid="from-input"]').fill('Delhi');
    await page.locator('[data-testid="to-input"]').fill('Dubai');
    await page.locator('[data-testid="date-input"]').fill('2026-09-15');
    await page.locator('[data-testid="search-flights"]').click();

    // 3. Wait for results and select flight
    const selectButtons = page.locator('[data-testid="select-flight"]');
    await expect(selectButtons.first()).toBeVisible();
    await selectButtons.first().click();

    // 4. Verify passenger page appears
    await expect(page.locator('h2')).toContainText('Passenger Information');
    await expect(page.locator('[data-testid="passenger-name"]')).toBeVisible();
    await expect(page.locator('[data-testid="passenger-email"]')).toBeVisible();
    await expect(page.locator('[data-testid="passenger-phone"]')).toBeVisible();
    await expect(page.locator('[data-testid="book-flight"]')).toBeVisible();
  });
});
