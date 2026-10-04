# HedgeCast

Parametric cover for small businesses. Pick a risk in plain English, pay from checking, and get paid automatically when the official result hits. No claim form.

Small businesses lose money to weather, fuel spikes, rate changes, and similar shocks. Traditional insurance is slow and claim-heavy. Kalshi already prices a lot of these risks, but the interface is built for traders.

HedgeCast is the middle layer: describe the risk in normal language, buy cover priced off live markets, pay from a bank account, and get paid when the official result comes in.

## What it does

1. Create a business profile with name, industry, and city.
2. Pick a kind of cover: weather, rates, fuel, prices, tariffs, sports, jobs, or something else.
3. Narrow it to a specific market. Example path: Weather → Rain → a day with a live probability.
4. Choose a cover amount, connect checking, pay the premium, and activate cover.
5. When the market settles, the payout lands in checking. You can see it in the balance and the money ledger.

The same flow works across topics, not only weather.

## Stack

- **Frontend:** React, TypeScript, Vite, Tailwind CSS, TanStack Query
- **Backend:** FastAPI, Python, Pydantic, SQLite
- **Markets:** Kalshi for live prices and settlement results
- **Banking:** Capital One Nessie for premiums and payouts

## Run

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cd frontend && npm install && cd ..
cp .env.example .env
```

Set `NESSIE_API_KEY` in `.env` if you want live bank movements. See [`.env.example`](.env.example) for the full list.

```bash
make live    # fresh demo: reset DB + API + Vite
make start   # resume: API + Vite, keep existing DB
```

Or separately: `make api` and `make web` in two terminals. Wipe only: `make reset-db`.

Offline Plan B (fakes, no API keys):

```bash
make fake         # fresh: reset DB + fake API + Vite
make start-fake   # resume fakes, keep DB
```

Checks:

```bash
make check   # pytest + TypeScript + lint
make e2e     # Playwright happy path
make smoke   # live Kalshi prices + Nessie
```

## Try the main path

1. Open `/welcome` and create a business (for example Peach Stand Café, Café, New York).
2. Choose Weather → Rain → pick a day → Continue.
3. Set cover to $300, connect checking, and Protect.
4. After settlement, open the policy page and check the balance and money ledger.

## Project layout

- [`frontend/`](frontend/) — React app (onboarding, plan wizard, policies)
- [`backend/hedgecast/`](backend/hedgecast/) — FastAPI engine, Kalshi and Nessie integrations
- [`Makefile`](Makefile) — `api`, `demo`, `web`, `check`, `e2e`, `smoke`
