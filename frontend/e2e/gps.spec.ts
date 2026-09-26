import { expect, test } from '@playwright/test'

// Georgia Tech (Klaus Advanced Computing Building area).
const GT = { latitude: 33.7766, longitude: -84.3963 }
const MIDTOWN_MARTA = { latitude: 33.781, longitude: -84.3863 }

test.beforeEach(async ({ context, page }) => {
  await context.grantPermissions(['geolocation'])
  await context.setGeolocation(GT)
  await page.addInitScript(() => localStorage.setItem('pathpro:first-run-seen', '1'))
})

test('two taps: "Where to?" then a place routes from "Your location" (GPS-01)', async ({ page }) => {
  await page.goto('/')

  await page.getByRole('button', { name: 'Where to?' }).click()
  const search = page.getByRole('dialog', { name: 'Where to?' })
  await search.getByRole('list', { name: 'Popular near Georgia Tech' }).getByRole('button', { name: 'Midtown MARTA' }).click()

  await expect(page.getByRole('button', { name: /From.*Your location/ })).toBeVisible()
  await expect(page).toHaveURL(/from=33\.7766\d*%2C-84\.3963\d*%2CYour\+location/)
  await expect(page.getByRole('region', { name: 'Route comparison' })).toContainText(/less traffic risk|lower-risk option/)
})

test('Start follows GPS and detects arrival; the trip becomes a recent place (GPS-02, ROUT-01)', async ({ page, context }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Where to?' }).click()
  await page.getByRole('list', { name: 'Popular near Georgia Tech' }).getByRole('button', { name: 'Midtown MARTA' }).click()
  await expect(page.getByRole('region', { name: 'Route comparison' })).toBeVisible()

  await page.getByRole('button', { name: 'Start', exact: true }).click()
  await expect(page.getByRole('region', { name: 'Trip progress' })).toBeVisible()
  await expect(page.getByText('Preview walk', { exact: true })).toHaveCount(0)

  await context.setGeolocation(MIDTOWN_MARTA)
  const arrived = page.getByRole('region', { name: "You've arrived" })
  await expect(arrived).toContainText('Midtown MARTA')
  await arrived.getByRole('button', { name: 'Done' }).click()

  // Standing at Midtown MARTA right after the trip: the learned "return" suggestion appears,
  // naming the GPS start after the nearest known place rather than "Your location".
  await expect(page.getByRole('region', { name: 'Suggested trip' })).toContainText('Heading back to Klaus Building?')
  await page.getByRole('button', { name: 'Where to?' }).click()
  await expect(page.getByRole('list', { name: 'Recent' })).toContainText('Midtown MARTA')
})

test('outside Atlanta, PathPro asks for a start instead (GPS-03)', async ({ page, context }) => {
  await context.setGeolocation({ latitude: 34.25, longitude: -84.1 })
  await page.goto('/')

  await page.getByRole('button', { name: 'Where to?' }).click()
  await page.getByRole('list', { name: 'Popular near Georgia Tech' }).getByRole('button', { name: 'Midtown MARTA' }).click()

  await expect(page.getByRole('status').filter({ hasText: "You're outside Atlanta" })).toBeVisible()
  await page.getByRole('button', { name: 'Pick a start' }).click()
  await page.getByRole('dialog', { name: 'Choose a start' }).getByRole('button', { name: 'Klaus Building' }).click()
  await expect(page.getByRole('region', { name: 'Route comparison' })).toBeVisible()
})
