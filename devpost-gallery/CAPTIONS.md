# Devpost gallery

Upload from `final/` in this order. All are JPG, 3:2, under 5 MB.

| File | Caption |
|---|---|
| `01-cover.jpg` | HedgeCast cover |
| `02-welcome.jpg` | Onboard a business |
| `03-pick-cover.jpg` | Pick a kind of cover |
| `04-weather-options.jpg` | Weather options in plain English |
| `05-pick-rain-day.jpg` | Pick days with live market chances |
| `06-price-and-protect.jpg` | Live price, connect checking, protect |
| `07-cover-live.jpg` | Cover is live after premium leaves checking |
| `08-policies.jpg` | Active and past plans |
| `09-payout.jpg` | Automatic payout into checking |
| `10-rates-markets.jpg` | Same flow for interest rates |
| `11-settlement.jpg` | Settlement view after result |

Suggested first image on Devpost: `01-cover.jpg` or `09-payout.jpg`.

To regenerate screenshots:

```bash
cd frontend && CAPTURE_GALLERY=1 npx playwright test e2e/capture-gallery.spec.ts
```
