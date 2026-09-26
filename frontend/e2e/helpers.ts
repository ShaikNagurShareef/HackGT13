import type { Page } from '@playwright/test'

/** Pick a "Popular near Georgia Tech" destination: inline sidebar on desktop, search sheet on phones. */
export async function pickPopular(page: Page, name: string): Promise<void> {
  const pill = page.getByRole('button', { name: 'Where to?' })
  if (await pill.isVisible()) await pill.click()
  await page.getByRole('list', { name: 'Popular near Georgia Tech' }).getByRole('button', { name }).click()
}

export async function openOptions(page: Page) {
  await page.getByRole('button', { name: 'Map options', exact: true }).click()
  return page.getByRole('dialog', { name: 'Map options' })
}
