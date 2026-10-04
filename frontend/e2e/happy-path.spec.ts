import { expect, type Page, test } from '@playwright/test'

async function onboard(page: Page, name: string, city?: string) {
  await page.goto('/welcome')
  await page.getByLabel('Business name').fill(name)
  await page.getByLabel('What kind of business').selectOption('Café or coffee shop')
  if (city) await page.getByLabel(/^City/).selectOption({ label: city })
  await page.getByRole('button', { name: 'Continue' }).click()

  await page.getByRole('button', { name: 'Connect checking' }).click()
  await expect(page.getByText("You're set up")).toBeVisible()
  await page.getByRole('button', { name: 'Go to my dashboard' }).click()
  await page.getByRole('link', { name: 'Get protection' }).first().click()
}

async function buy(page: Page) {
  const button = page.getByRole('button', { name: /Buy protection · \$\d+/ })
  await expect(button).toBeEnabled()
  await button.click()
  await expect(page.getByText("You're covered.")).toBeVisible()
}

test('search any market, cover the NO side, resolve, get paid', async ({ page }) => {
  await onboard(page, 'Playwright Pastries')
  await expect(page.getByText(/Weather near/)).toHaveCount(0)

  await page.getByPlaceholder(/Search Kalshi/).fill('fed')
  await page.getByRole('link', { name: /Fed rate decision in December/ }).click()
  await page.getByRole('button', { name: /^Hold/ }).click()
  await page.getByRole('button', { name: /Pay me if NO/ }).click()
  await page.getByRole('button', { name: '$500', exact: true }).click()
  await expect(page.getByText('Pays if NO').first()).toBeVisible()
  await buy(page)
  const policyUrl = page.url()

  await page.goto('/ops')
  await page.getByRole('button', { name: 'Resolve NO' }).first().click()
  await expect(page.getByText('Paid out').first()).toBeVisible()

  await page.goto(policyUrl)
  await expect(page.getByText('$500 was paid into your checking account.')).toBeVisible()

  await page.goto('/')
  await expect(page.getByText('Paid $500 into checking. No claim needed.').first()).toBeVisible()
})

test('weather shortcut shows up when the business has a city', async ({ page }) => {
  await onboard(page, 'Playwright Patio', 'New York, NY')
  await page.getByRole('link', { name: /Weather near New York/ }).click()
  await page.getByRole('button', { name: /^Rain/ }).click()
  await expect(page.getByText('Settles on the official New York City (Central Park) reading')).toBeVisible()
  await page.getByRole('button', { name: '$500', exact: true }).click()
  await buy(page)
})
