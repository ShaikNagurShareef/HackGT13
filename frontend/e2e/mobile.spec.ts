import { expect, test } from '@playwright/test'

// Phone project (Pixel 7): the map-first layout, bottom sheet, and preview walk, offline demo.
test.describe('phone layout (UX-02)', () => {
  test('route sheet peeks, expands for "Why?", and Start previews the walk', async ({ page, context }) => {
    await page.goto('/?demo=1')
    const sheet = page.getByRole('region', { name: 'Route comparison' })
    await expect(sheet).toHaveAttribute('data-state', 'peek')
    await expect(page.getByTestId('route-pp')).toBeVisible()
    await expect(page.getByTestId('route-explanation')).toBeHidden()
    await context.setOffline(true)

    await page.getByRole('button', { name: 'Why?' }).click()
    await expect(sheet).toHaveAttribute('data-state', 'expanded')
    await expect(page.getByTestId('route-explanation')).toBeVisible()
    await page.getByRole('button', { name: 'Collapse Route comparison' }).click()
    await expect(sheet).toHaveAttribute('data-state', 'peek')

    await page.getByRole('button', { name: 'Start', exact: true }).click()
    await expect(page.getByRole('region', { name: 'Trip progress' })).toBeVisible()
    await page.getByRole('button', { name: 'End', exact: true }).click()
    await expect(sheet).toBeVisible()
  })

  test('home covers little of the map and every control is a 44 px target', async ({ page }) => {
    await page.goto('/?demo=1')
    await page.getByRole('button', { name: 'Back to map' }).click()
    await expect(page.getByRole('button', { name: 'Where to?' })).toBeVisible()

    const viewport = page.viewportSize()
    const boxes = await page.locator('main button:visible').evaluateAll((els) =>
      els.map((el) => {
        const r = el.getBoundingClientRect()
        return { name: el.getAttribute('aria-label') ?? el.textContent, w: r.width, h: r.height, area: r.width * r.height }
      }),
    )
    for (const b of boxes) {
      expect(Math.min(b.w, b.h), `${b.name} touch target`).toBeGreaterThanOrEqual(44)
    }
    const covered = boxes.reduce((sum, b) => sum + b.area, 0)
    expect(covered / ((viewport?.width ?? 1) * (viewport?.height ?? 1))).toBeLessThan(0.2)
  })
})
