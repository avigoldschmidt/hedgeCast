import { expect, type Page, test } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const OUT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../devpost-gallery/raw')
const VIEWPORT = { width: 1500, height: 1000 }

async function shot(page: Page, name: string) {
  fs.mkdirSync(OUT, { recursive: true })
  await page.screenshot({
    path: path.join(OUT, `${name}.png`),
    type: 'png',
  })
}

async function onboard(page: Page) {
  await page.goto('/welcome')
  await expect(page.getByLabel('Business name')).toBeVisible()
  await shot(page, '01-welcome')

  await page.getByLabel('Business name').fill('Peach Stand Café')
  await page.getByLabel('Industry').selectOption({ label: 'Café or coffee shop' })
  await page.getByLabel('Where are you?').selectOption({ label: 'New York, NY' })
  await shot(page, '02-welcome-filled')
  await page.getByRole('button', { name: 'Find cover' }).click()
  await expect(page.getByRole('heading', { name: 'What kind of cover do you need?' })).toBeVisible()
}

test('capture Devpost gallery screens', async ({ page }) => {
  test.skip(!process.env.CAPTURE_GALLERY, 'Set CAPTURE_GALLERY=1 to regenerate Devpost screenshots')
  await page.setViewportSize(VIEWPORT)
  await onboard(page)
  await shot(page, '03-kind-of-cover')

  await page.getByRole('button', { name: /Weather/ }).click()
  await expect(page.getByRole('heading', { name: /Weather near/ })).toBeVisible()
  await expect(page.getByRole('button', { name: /Rain/ })).toBeVisible()
  await shot(page, '04-weather-kinds')

  await page.getByRole('button', { name: /Rain/ }).click()
  await expect(page.getByText(/Settles on the official/)).toBeVisible()
  await expect(page.getByRole('button', { name: /Continue with \d+ day/ })).toBeVisible()
  await shot(page, '05-rain-days')

  await page.getByRole('button', { name: /Continue with \d+ day/ }).click()
  await expect(page.getByText(/How much would a bad day cost you/)).toBeVisible()
  await shot(page, '06-quote')

  await page.getByRole('button', { name: 'Connect checking' }).click()
  await expect(page.getByText(/Checking ••/)).toBeVisible()
  await shot(page, '07-checking-connected')

  await page.getByRole('button', { name: '$300', exact: true }).click()
  const protect = page.getByRole('button', { name: /^Protect for \$\d+/ })
  await expect(protect).toBeEnabled()
  await shot(page, '08-ready-to-protect')
  await protect.click()
  await expect(page.getByText("You're covered.")).toBeVisible()
  await shot(page, '09-policy-live')

  const policyUrl = page.url()

  await page.goto('/')
  await expect(page.getByText(/cover|policy|Peach/i).first()).toBeVisible({ timeout: 10000 }).catch(() => {})
  await shot(page, '10-home')

  await page.goto('/policies')
  await shot(page, '11-policies')

  await page.goto('/ops')
  await expect(page.getByRole('button', { name: 'Settle YES' }).first()).toBeVisible()
  await shot(page, '12-ops')
  await page.getByRole('button', { name: 'Settle YES' }).first().click()
  await expect(page.getByText('Paid out').first()).toBeVisible()
  await shot(page, '13-ops-paid')

  await page.goto(policyUrl)
  await expect(page.getByText(/\+\$300 paid into checking/)).toBeVisible()
  await shot(page, '14-policy-paid')

  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'What kind of cover do you need?' })).toBeVisible()
  await page.getByRole('button', { name: /Interest rates/ }).click()
  await expect(page.getByRole('heading', { name: 'Interest rates' })).toBeVisible()
  await expect(page.getByRole('button', { name: /Fed|rate|FOMC/i }).first()).toBeVisible({ timeout: 15000 })
  await shot(page, '15-rates-markets')
})
