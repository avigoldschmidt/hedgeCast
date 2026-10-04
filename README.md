# HedgeCast

Parametric cover for small businesses: pick a risk in plain English, get a live price from Kalshi prediction markets, pay the premium from checking, and get paid automatically when the official result hits — no claim form.

**Stack:** React (Vite) + FastAPI · Kalshi market data · Capital One Nessie for bank movements · paper hedges against the live book by default.

## What makes it special

| Status quo | HedgeCast |
|---|---|
| Business interruption insurance | Slow, opaque, claims adjusters |
| Trading Kalshi yourself | Needs market literacy; no SME packaging or bank payout UX |
| Generic “risk dashboards” | No real price, no money movement |

HedgeCast is the **distribution layer**: SME language → Kalshi hedge → Capital One money movement → parametric payout.

## Run

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cd frontend && npm install && cd ..
cp .env.example .env   # set NESSIE_API_KEY for live bank
```

**Primary (live Kalshi prices + Nessie, paper hedges):**

```bash
make api    # FastAPI :8000
make web    # React :5173 → http://localhost:5173
```

**Backup (offline fakes, no keys):**

```bash
make demo
make web
```

**Verify:**

```bash
make check   # pytest + tsc + lint
make e2e     # Playwright happy path (fakes)
make smoke   # real Nessie + live Kalshi prices, paper hedge
```

See [`.env.example`](.env.example) for `HEDGE_MODE`, Kalshi keys (live hedges only), and `HEDGECAST_FAKES`.

## 3-minute demo script

One path. Narrate the numbers.

| Time | Screen | Do | Say |
|------|--------|----|-----|
| 0:00–0:20 | `/welcome` | Peach Stand Café · Café · New York → **Find cover** | Patio café. Rain kills sales. Insurance won’t pay that fast — we will. |
| 0:20–1:10 | Plan | **Weather → Rain → pick a day with % → Continue** | Live Kalshi market, wrapped in English. |
| 1:10–1:50 | Price | **$300** → **Connect checking** (~$1,000) → **Protect** | Premium leaves checking. Cover is live. |
| 1:50–2:40 | `/ops` → policy | Pre-open Settlement in a second tab → **Settle YES** → back to policy | Normally Kalshi posts the result and our worker pays; we’re firing that settle now. **+$300, no claim.** |
| 2:40–3:00 | Policy / header | Linger on paid banner + checking balance + Money ledger | Same rails for rates, fuel, tariffs. |

**Skip on stage:** second topics, Under the hood, thin-book panel, Settle NO on rain cover, large payout presets.

**If weather markets are empty:** pivot to Interest rates → Fed (buy only), or restart with `make demo`.

### Judge honesty (if asked)

Prices and results come from Kalshi. Hedges are paper fills against the live order book (exchange demo account can’t be funded). Bank movements use the Capital One Nessie sandbox.

## Day-of checklist

1. `.env`: `NESSIE_API_KEY`, `HEDGE_MODE=paper`, `HEDGECAST_FAKES=0`
2. `make api` + `make web`; dry-run the rain → $300 → protect → Settle YES path once
3. Note starting checking, premium, and expected post-payout balance
4. Pre-open `/ops` in a second tab
5. Keep a terminal ready for `make demo` if live APIs flake
6. Rehearse under 2:45

## Project layout

- [`frontend/`](frontend/) — React app (`/welcome`, plan wizard, policies, `/ops`)
- [`backend/hedgecast/`](backend/hedgecast/) — FastAPI engine, Kalshi + Nessie integrations
- [`Makefile`](Makefile) — `api`, `demo`, `web`, `check`, `e2e`, `smoke`
