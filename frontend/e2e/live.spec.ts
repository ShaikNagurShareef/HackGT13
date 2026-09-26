import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('pathpro:first-run-seen', '1'))
})

test('first run explains traffic risk and remembers dismissal', async ({ page }) => {
  await page.addInitScript(() => localStorage.removeItem('pathpro:first-run-seen'))
  await page.goto('/')

  const dialog = page.getByRole('dialog', { name: 'PathPro' })
  await expect(dialog).toContainText('Traffic risk only — not crime or personal safety')
  await dialog.getByRole('button', { name: 'Got it' }).click()
  await expect(dialog).toBeHidden()
})

test('Risk Tides slider is keyboard operable with a spoken value (TIDE-04)', async ({ page }) => {
  await page.goto('/?h=21&day=friday&cond=dry')
  const slider = page.getByRole('slider', { name: 'Hour of day' })
  await expect(slider).toHaveAttribute('aria-valuetext', /^9 PM, dry, citywide median risk \d+$/)

  await slider.focus()
  await page.keyboard.press('ArrowRight')
  await expect(slider).toHaveAttribute('aria-valuetext', /^10 PM/)
})

test('quick picks route between two covered places', async ({ page }) => {
  await page.goto('/?t=2026-09-25T22:30&cond=wet')
  const picks = page.getByRole('group', { name: /Quick picks/ })
  await picks.getByRole('button', { name: 'Klaus Building' }).click()
  await picks.getByRole('button', { name: 'Midtown MARTA' }).click()

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
  await page.getByRole('button', { name: 'About PathPro' }).click()

  const about = page.getByRole('dialog', { name: 'How PathPro works' })
  await expect(about).toContainText('held-out')
  await expect(about.getByRole('link', { name: 'Call 911' })).toHaveAttribute('href', 'tel:911')
  await expect(about).toContainText('No demographic, income, or crime data')
})

test('City Pulse: toggle to citywide hexes and open an area card (CITY-01/02)', async ({ page }) => {
  await page.goto('/?h=22&day=friday&cond=wet')
  await page.getByRole('button', { name: 'City Pulse' }).click()
  await expect(page.getByRole('button', { name: 'City Pulse' })).toHaveAttribute('aria-pressed', 'true')
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
