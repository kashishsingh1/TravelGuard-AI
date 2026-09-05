import { test, expect } from '@playwright/test';
import path from 'path';

const ARTIFACT_DIR = '/Users/kashishsingh/.gemini/antigravity-ide/brain/fafe92e9-8ad4-40c8-a6e4-f966ced4eedb';

test('capture screenshots of all booking steps', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });

  // 1. Search page
  await page.goto('/');
  await page.waitForSelector('[data-testid="search-flights"]');
  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'step1_search.png') });

  // 2. Flight results
  await page.locator('[data-testid="from-input"]').fill('Delhi');
  await page.locator('[data-testid="to-input"]').fill('Dubai');
  await page.locator('[data-testid="date-input"]').fill('2026-09-15');
  await page.locator('[data-testid="search-flights"]').click();
  await page.waitForSelector('[data-testid="flight-results"]');
  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'step2_results.png') });

  // 3. Passenger form
  await page.locator('[data-testid="select-flight"]').first().click();
  await page.waitForSelector('[data-testid="passenger-name"]');
  await page.locator('[data-testid="passenger-name"]').fill('John Doe');
  await page.locator('[data-testid="passenger-email"]').fill('john.doe@example.com');
  await page.locator('[data-testid="passenger-phone"]').fill('+91 98765 43210');
  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'step3_passenger.png') });

  // 4. Booking confirmation
  await page.locator('[data-testid="book-flight"]').click();
  await page.waitForSelector('[data-testid="booking-confirmation"]');
  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'step4_confirmation.png') });
});
