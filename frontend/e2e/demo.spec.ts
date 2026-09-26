import { expect, test } from '@playwright/test'

test.describe('demo mode (DEMO-01)', () => {
  test('scripted route works end to end with the network disabled after load', async ({ page, context }) => {
    await page.goto('/?demo=1')

    const card = page.getByRole('region', { name: 'Route comparison' })
    await expect(card).toContainText('less traffic-risk exposure')
    await expect(page.getByTestId('route-pp')).toBeVisible()
    await expect(page.getByTestId('route-fast')).toBeVisible()
    await expect(page.getByTestId('route-explanation')).not.toBeEmpty()

    await context.setOffline(true)

    await card.locator('.hot-list .chip').first().click()
    const sheet = page.getByRole('region', { name: /Traffic risk for/ })
    await expect(sheet).toBeVisible()
    await expect(sheet.locator('.dial-score')).toHaveText(/^\d{1,3}$/)
    await expect(page.getByTestId('segment-explanation')).not.toHaveText('Loading explanation…')

    // Factor bars must add up to the displayed score (EXP-01).
    const points = await sheet.locator('.factor:not(.factor-total) .factor-points').allTextContents()
    const total = points.reduce((sum, p) => sum + Number(p.replace('−', '-').replace('+', '')), 0)
    expect(total).toBe(Number(await sheet.locator('.dial-score').textContent()))

    await sheet.getByRole('button', { name: 'Close details' }).click()
    await expect(card).toBeVisible()
  })

  test('copy never promises safety (EC-60/61)', async ({ page }) => {
    await page.goto('/?demo=1')
    await expect(page.getByRole('region', { name: 'Route comparison' })).toBeVisible()

    const text = (await page.locator('main').innerText()).toLowerCase()
    expect(text).not.toMatch(/\b(safe|safest|guaranteed|crime|dangerous area)\b/)
    await expect(page.getByRole('note')).toHaveText(/Traffic risk estimate from historical crashes/)
  })

  test('shortcuts: T jumps to 10 PM, R toggles rain (DEMO-02)', async ({ page }) => {
    await page.goto('/?demo=1')
    await expect(page.getByRole('region', { name: 'Route comparison' })).toBeVisible()

    await page.keyboard.press('r')
    await expect(page.getByRole('button', { name: 'Dry' })).toHaveAttribute('aria-pressed', 'true')
    await page.keyboard.press('t')
    await expect(page.getByRole('slider', { name: 'Hour of day' })).toHaveAttribute('aria-valuetext', /^10 PM/)
  })
})
