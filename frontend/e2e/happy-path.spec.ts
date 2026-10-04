import { expect, test } from '@playwright/test'

test('onboard, buy rain cover, resolve, get paid', async ({ page }) => {
  await page.goto('/welcome')
  await page.getByLabel('Business name').fill('Playwright Pastries')
  await page.getByLabel('What kind of business').selectOption('Café or coffee shop')
  await page.getByLabel('City').selectOption({ label: 'New York, NY' })
  await page.getByRole('button', { name: 'Continue' }).click()

  await page.getByRole('button', { name: 'Connect checking' }).click()
  await expect(page.getByText("You're set up")).toBeVisible()
  await page.getByRole('button', { name: 'Go to my dashboard' }).click()

  await page.getByRole('link', { name: 'Get protection' }).first().click()
  await page.getByRole('button', { name: /^Rain/ }).click()
  await expect(page.getByText('Settles on the official New York City (Central Park) reading')).toBeVisible()
  await page.getByRole('button', { name: '$500', exact: true }).click()

  const buy = page.getByRole('button', { name: /Buy protection · \$\d+/ })
  await expect(buy).toBeEnabled()
  await buy.click()

  await expect(page.getByText("You're covered.")).toBeVisible()
  await expect(page.getByText('Active', { exact: true }).first()).toBeVisible()
  const policyUrl = page.url()

  await page.goto('/ops')
  await page.getByRole('button', { name: 'Resolve YES' }).first().click()
  await expect(page.getByText('Paid out').first()).toBeVisible()

  await page.goto(policyUrl)
  await expect(page.getByText('$500 was paid into your checking account.')).toBeVisible()

  await page.goto('/')
  await expect(page.getByText('Paid $500 into checking. No claim needed.').first()).toBeVisible()
})
