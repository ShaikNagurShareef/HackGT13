import { expect, test } from '@playwright/test'

test.describe('demo mode (DEMO-01)', () => {
  test('scripted route works end to end with the network disabled after load', async ({ page, context }) => {
    await page.goto('/?demo=1')

    const card = page.getByRole('region', { name: 'Route comparison' })
    await expect(card).toContainText('less traffic risk')
    await expect(page.getByTestId('route-pp')).toContainText(/arrive \d{1,2}:\d{2} [AP]M/)
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

  test('Start previews the walk offline with the navigation banner, then ends (VOX-05)', async ({ page, context }) => {
    await page.goto('/?demo=1')
    await expect(page.getByRole('region', { name: 'Route comparison' })).toBeVisible()
    await context.setOffline(true)

    await page.getByRole('button', { name: 'Start', exact: true }).click()

    const banner = page.getByRole('status').filter({ hasText: /traffic risk|Continue on/ })
    await expect(banner).toBeVisible()
    await expect(page.getByText('Preview walk', { exact: true })).toBeVisible()
    await expect(page.getByRole('region', { name: 'Trip progress' })).toContainText(/\d+ min/)
    await expect(banner).toContainText('High traffic risk', { timeout: 20_000 })

    await page.getByRole('button', { name: 'End', exact: true }).click()
    await expect(page.getByRole('region', { name: 'Route comparison' })).toBeVisible()
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
    await page.keyboard.press('t')
    await page.getByRole('button', { name: 'Map options', exact: true }).click()

    const options = page.getByRole('dialog', { name: 'Map options' })
    await expect(options.getByRole('button', { name: 'Dry' })).toHaveAttribute('aria-pressed', 'true')
    await expect(options.getByRole('slider', { name: 'Hour of day' })).toHaveAttribute('aria-valuetext', /^10 PM/)
  })

  test('desktop home: persistent sidebar with inline search, options, and Risk Tides on the map (UX-03)', async ({ page }) => {
    await page.goto('/?demo=1')
    await page.getByRole('button', { name: 'Back to map' }).click()

    const sidebar = page.getByRole('complementary', { name: 'PathPro' })
    await expect(sidebar).toContainText('See the risks on your way, before you go.')
    await expect(sidebar.getByRole('combobox', { name: 'Search places' })).toBeVisible()
    await expect(sidebar.getByRole('heading', { name: 'Popular near Georgia Tech' })).toBeVisible()
    await expect(sidebar.getByRole('button', { name: /Wet/ })).toHaveAttribute('aria-pressed', 'true')
    await expect(page.getByRole('region', { name: 'Risk Tides timeline' })).toBeVisible()
    await expect(page.getByRole('slider', { name: 'Hour of day' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Where to?' })).toHaveCount(0)
  })
})
