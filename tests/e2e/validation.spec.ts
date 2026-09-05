import { test, expect } from '@playwright/test';

test.describe('TEST 4: Passenger Form Validation', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to passenger page for testing validation
    await page.goto('/');
    await page.locator('[data-testid="from-input"]').fill('Delhi');
    await page.locator('[data-testid="to-input"]').fill('Dubai');
    await page.locator('[data-testid="date-input"]').fill('2026-09-15');
    await page.locator('[data-testid="search-flights"]').click();
    await page.locator('[data-testid="select-flight"]').first().click();
    await expect(page.locator('[data-testid="passenger-name"]')).toBeVisible();
  });

  test('should reject empty passenger form submission', async ({ page }) => {
    // Clear any inputs if present
    await page.locator('[data-testid="passenger-name"]').fill('');
    await page.locator('[data-testid="passenger-email"]').fill('');
    await page.locator('[data-testid="passenger-phone"]').fill('');

    // Attempt to submit
    await page.locator('[data-testid="book-flight"]').click();

    // Verify error is displayed
    const errorMessage = page.locator('[data-testid="error-message"]');
    await expect(errorMessage).toBeVisible();
    await expect(errorMessage).toContainText('Full Name is required');

    // Verify user is NOT navigated to confirmation
    await expect(page.locator('[data-testid="booking-confirmation"]')).not.toBeVisible();
  });

  test('should reject invalid email format', async ({ page }) => {
    await page.locator('[data-testid="passenger-name"]').fill('Jane Doe');
    await page.locator('[data-testid="passenger-email"]').fill('invalid-email-no-at');
    await page.locator('[data-testid="passenger-phone"]').fill('9876543210');

    await page.locator('[data-testid="book-flight"]').click();

    const errorMessage = page.locator('[data-testid="error-message"]');
    await expect(errorMessage).toBeVisible();
    await expect(errorMessage).toContainText('valid email address');
    await expect(page.locator('[data-testid="booking-confirmation"]')).not.toBeVisible();
  });

  test('should reject invalid phone number with fewer than 7 digits', async ({ page }) => {
    await page.locator('[data-testid="passenger-name"]').fill('Jane Doe');
    await page.locator('[data-testid="passenger-email"]').fill('jane.doe@example.com');
    await page.locator('[data-testid="passenger-phone"]').fill('123');

    await page.locator('[data-testid="book-flight"]').click();

    const errorMessage = page.locator('[data-testid="error-message"]');
    await expect(errorMessage).toBeVisible();
    await expect(errorMessage).toContainText('at least 7 digits');
    await expect(page.locator('[data-testid="booking-confirmation"]')).not.toBeVisible();
  });
});
