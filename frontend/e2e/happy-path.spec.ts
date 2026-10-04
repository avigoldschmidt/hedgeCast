import { expect, type Page, test } from '@playwright/test'

async function onboard(page: Page, name: string) {
  await page.goto('/welcome')
  await page.getByLabel('Business name').fill(name)
  await page.getByLabel('What do you do?').fill('We run a small coffee shop with a sidewalk patio.')
  await page.getByLabel('Where are you?').selectOption({ label: 'New York, NY' })
  await page.getByRole('button', { name: 'Continue' }).click()

  await expect(page.getByText('Here’s what we’ll watch for you')).toBeVisible()
  await expect(page.getByRole('button', { name: /Weather/, pressed: true })).toBeVisible()
  await page.getByRole('button', { name: 'Looks right' }).click()

  await page.getByRole('button', { name: 'Connect checking' }).click()
  await expect(page.getByRole('heading', { name })).toBeVisible()
}

async function protect(page: Page, preset: string) {
  const sheet = page.getByRole('dialog')
  await sheet.getByRole('button', { name: preset, exact: true }).click()
  const button = sheet.getByRole('button', { name: /^Protect for \$\d+/ })
  await expect(button).toBeEnabled()
  await button.click()
  await expect(page.getByText("You're covered.")).toBeVisible()
}

test('forecast card: protect against rain, resolve, get paid', async ({ page }) => {
  await onboard(page, 'Playwright Patio')

  await expect(page.getByRole('button', { name: /Rain at New York City \(Central Park\)/ })).toBeVisible()
  await expect(page.getByRole('button', { name: /US gas prices at the end of October/ })).toBeVisible()

  await page.getByRole('button', { name: /Rain at New York City \(Central Park\)/ }).click()
  await expect(page.getByRole('dialog').getByText(/official reading at New York City \(Central Park\)/).first()).toBeVisible()
  await protect(page, '$300')
  const policyUrl = page.url()

  await page.goto('/ops')
  await page.getByRole('button', { name: 'Resolve YES' }).first().click()
  await expect(page.getByText('Paid out').first()).toBeVisible()

  await page.goto(policyUrl)
  await expect(page.getByText('$300 was paid into your checking account.')).toBeVisible()
})

test('ask bar: cover the Fed holding, resolve, get paid', async ({ page }) => {
  await onboard(page, 'Playwright Pastries')

  await page.getByPlaceholder(/Worried about something else/).fill('fed rate cuts')
  await page.getByRole('button', { name: 'Ask', exact: true }).click()
  await page.getByRole('button', { name: /Fed rate decision in December/ }).first().click()

  const sheet = page.getByRole('dialog')
  await sheet.getByRole('button', { name: /^Hold/ }).click()
  await sheet.getByRole('button', { name: "Pay me if it doesn't" }).click()
  await protect(page, '$600')
  const policyUrl = page.url()

  await page.goto('/ops')
  await page.getByRole('button', { name: 'Resolve NO' }).first().click()
  await expect(page.getByText('Paid out').first()).toBeVisible()

  await page.goto(policyUrl)
  await expect(page.getByText('$600 was paid into your checking account.')).toBeVisible()
})
