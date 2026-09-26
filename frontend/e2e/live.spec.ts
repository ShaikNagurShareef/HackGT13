import { expect, test } from '@playwright/test'
import { openOptions, pickPopular } from './helpers'

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('pathpro:first-run-seen', '1'))
})

test('first run explains traffic risk in a toast and remembers dismissal', async ({ page }) => {
  await page.addInitScript(() => localStorage.removeItem('pathpro:first-run-seen'))
  await page.goto('/')

  const toast = page.getByRole('region', { name: 'Welcome to PathPro' })
  await expect(toast).toContainText('Traffic risk only — not crime or personal safety')
  await toast.getByRole('button', { name: 'Got it' }).click()
  await expect(toast).toBeHidden()
  expect(await page.evaluate(() => localStorage.getItem('pathpro:first-run-seen'))).toBe('1')
})

test('Risk Tides slider is keyboard operable with a spoken value (TIDE-04)', async ({ page }) => {
  await page.goto('/?h=21&day=friday&cond=dry')
  const options = await openOptions(page)
  const slider = options.getByRole('slider', { name: 'Hour of day' })
  await expect(slider).toHaveAttribute('aria-valuetext', /^9 PM, dry, citywide median risk \d+$/)

  await slider.focus()
  await page.keyboard.press('ArrowRight')
  await expect(slider).toHaveAttribute('aria-valuetext', /^10 PM/)
})

test('without GPS, picking a destination then a start routes between covered places', async ({ page }) => {
  await page.goto('/?t=2026-09-25T22:30&cond=wet')
  await pickPopular(page, 'Midtown MARTA')

  await page.getByRole('button', { name: /From.*Choose a start/ }).click()
  await page.getByRole('dialog', { name: 'Choose a start' }).getByRole('button', { name: 'Klaus Building' }).click()

  await expect(page.getByRole('region', { name: 'Route comparison' })).toContainText(/min/)
  await expect(page).toHaveURL(/from=.*Klaus/)
})

test('destination outside coverage gets an honest message (EC-01)', async ({ page }) => {
  await page.goto('/?from=33.77710,-84.39620,Klaus&to=33.77480,-84.29630,Decatur')

  await expect(page.getByRole('alert')).toContainText('PathPro covers the City of Atlanta')
})

test('origin equal to destination is handled (EC-02)', async ({ page }) => {
  await page.goto('/?from=33.77710,-84.39620,Klaus&to=33.77712,-84.39621,Klaus')

  await expect(page.getByRole('alert')).toContainText("You're already there")
})

test('About shows the model card and emergency numbers (TRUST-01/03)', async ({ page }) => {
  await page.goto('/')
  const options = await openOptions(page)
  await options.getByRole('button', { name: 'About PathPro' }).click()

  const about = page.getByRole('dialog', { name: 'How PathPro works' })
  await expect(about).toContainText('held-out')
  await expect(about.getByRole('link', { name: 'Call 911' })).toHaveAttribute('href', 'tel:911')
  await expect(about).toContainText('No demographic, income, or crime data')
})

test('City Pulse: toggle to citywide hexes and open an area card (CITY-01/02)', async ({ page }) => {
  await page.goto('/?h=22&day=friday&cond=wet')
  const options = await openOptions(page)
  await options.getByRole('button', { name: 'City Pulse' }).click()
  await expect(options.getByRole('button', { name: 'City Pulse' })).toHaveAttribute('aria-pressed', 'true')
  await options.getByRole('button', { name: 'Close options' }).click()
  await page.waitForTimeout(2500) // fly-to animation settles
  await page.mouse.click(700, 450)

  const card = page.getByRole('region', { name: 'Area traffic risk' })
  await expect(card).toBeVisible()
  const points = await card.locator('.factor:not(.factor-total) .factor-points').allTextContents()
  const total = points.reduce((sum, p) => sum + Number(p.replace('−', '-').replace('+', '')), 0)
  expect(total).toBe(Number(await card.locator('.dial-score').textContent()))
})

test('citywide coverage: West End gets street-level routes', async ({ page }) => {
  await page.goto('/?from=33.74960,-84.41360,AUC&to=33.73590,-84.41320,West%20End%20MARTA&t=2026-09-25T22:30&cond=wet')

  const card = page.getByRole('region', { name: 'Route comparison' })
  await expect(card).toContainText(/min/)
  await expect(page.getByRole('alert')).toHaveCount(0)
})
