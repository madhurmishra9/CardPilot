// Smoke test: the built SPA renders and navigates without a backend.
// (API calls fail gracefully into error/empty states — the shell must survive.)
import { test, expect } from '@playwright/test'

test('app shell renders and tabs navigate', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('header h1')).toContainText('Card')

  const tabs = ['Swipe Advisor', 'Redemption', 'Card Compare', 'Travel', 'Chat',
                'Transactions', 'My Cards', 'Dashboard']
  for (const tab of tabs) {
    await page.getByRole('button', { name: tab, exact: true }).click()
  }

  await page.getByRole('button', { name: 'Swipe Advisor', exact: true }).click()
  await expect(page.getByText('Which card should I swipe?')).toBeVisible()

  await page.getByRole('button', { name: 'Chat', exact: true }).click()
  await expect(page.getByPlaceholder(/Ask about swipes/)).toBeVisible()
})

test('PWA manifest and service worker are served', async ({ page, request }) => {
  const manifest = await request.get('/manifest.webmanifest')
  expect(manifest.ok()).toBeTruthy()
  expect((await manifest.json()).name).toBe('CardPilot')
  const sw = await request.get('/sw.js')
  expect(sw.ok()).toBeTruthy()
})
