import { expect, type Page, test } from '@playwright/test'

async function onboard(page: Page, name: string) {
  await page.goto('/welcome')
  await page.getByLabel('Business name').fill(name)
  await page.getByLabel('Industry').selectOption({ label: 'Café or coffee shop' })
  await page.getByLabel('Where are you?').selectOption({ label: 'New York, NY' })
  await page.getByRole('button', { name: 'Find cover' }).click()
  await expect(page.getByRole('heading', { name: 'What kind of cover do you need?' })).toBeVisible()
}

async function protect(page: Page, preset: string) {
  await page.getByRole('button', { name: 'Connect checking' }).click()
  await expect(page.getByText(/Checking ••/)).toBeVisible()
  await page.getByRole('button', { name: preset, exact: true }).click()
  const button = page.getByRole('button', { name: /^Protect for \$\d+/ })
  await expect(button).toBeEnabled()
  await button.click()
  await expect(page.getByText("You're covered.")).toBeVisible()
}

test('weather wizard: protect against rain, resolve, get paid', async ({ page }) => {
  await onboard(page, 'Playwright Patio')

  await page.getByRole('button', { name: /Weather/ }).click()
  await expect(page.getByRole('heading', { name: /Weather near/ })).toBeVisible()
  await page.getByRole('button', { name: /Rain/ }).click()
  await expect(page.getByText(/Settles on the official/)).toBeVisible()
  await page.getByRole('button', { name: /Continue with \d+ day/ }).click()

  await expect(page.getByText(/How much would a bad day cost you/)).toBeVisible()
  await protect(page, '$300')
  const policyUrl = page.url()

  await page.goto('/ops')
  await page.getByRole('button', { name: 'Settle YES' }).first().click()
  await expect(page.getByText('Paid out').first()).toBeVisible()

  await page.goto(policyUrl)
  await expect(page.getByText(/\+\$300 paid into checking/)).toBeVisible()
})

test('rates wizard: find Fed cover and protect', async ({ page }) => {
  await onboard(page, 'Playwright Rates')

  await page.getByRole('button', { name: /Interest rates/ }).click()
  await expect(page.getByRole('heading', { name: 'Interest rates' })).toBeVisible()
  await expect(page.getByRole('button', { name: /Fed|rate|FOMC/i }).first()).toBeVisible({ timeout: 15000 })
  await page.getByRole('button', { name: /Fed|rate|FOMC/i }).first().click()

  const hold = page.getByRole('button', { name: /^Hold/ })
  if (await hold.count()) await hold.first().click()
  await page.getByRole('button', { name: "Pay me if it doesn't" }).click()
  await page.getByRole('button', { name: 'Continue', exact: true }).click()

  await protect(page, '$600')
  await expect(page.getByText("You're covered.")).toBeVisible()
})
