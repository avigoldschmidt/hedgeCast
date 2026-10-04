import { useQuery } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { api, type S, type Side } from '@/api/client'
import { CategoryIcon, Checkbox, ErrorNote, Loading } from '@/components/domain'
import { PayoutPicker, QuoteCheckout, Section } from '@/components/quote'
import { Card } from '@/components/ui/card'
import { cn, pct, shortDate } from '@/lib/format'

const MAX_LEGS = 5

export function EventPage() {
  const { ticker = '' } = useParams()
  const event = useQuery({ queryKey: ['event', ticker], queryFn: () => api.event(ticker), staleTime: 30_000 })
  const [picked, setPicked] = useState<string[] | null>(null)
  const [side, setSide] = useState<Side>('yes')
  const [payout, setPayout] = useState(1000)

  if (event.isPending) return <Loading label="Loading market" />
  if (event.isError) return <ErrorNote error={event.error} />

  const { markets } = event.data
  const chosen = picked ?? (markets.length === 1 ? [markets[0].ticker] : [])
  const request: S['QuoteRequest'] | null =
    chosen.length > 0 ? { legs: chosen.map((t) => ({ ticker: t, side })), payout_dollars: payout } : null

  function toggle(marketTicker: string) {
    setPicked(chosen.includes(marketTicker) ? chosen.filter((t) => t !== marketTicker) : [...chosen, marketTicker])
  }

  return (
    <>
      <Link to="/protect" className="mb-6 inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink">
        <ArrowLeft className="size-4" /> All markets
      </Link>
      <div className="mb-8 flex items-start gap-4">
        <CategoryIcon category={event.data.category} className="size-12 rounded-2xl" />
        <div>
          <div className="text-sm text-muted">
            {event.data.category}
            {event.data.sub_title && ` · ${event.data.sub_title}`}
          </div>
          <h1 className="font-display text-3xl font-semibold tracking-tight">{event.data.title}</h1>
        </div>
      </div>

      <div className="grid gap-8 lg:grid-cols-[1fr_400px]">
        <div className="space-y-8">
          <Section number={1} title={markets.length === 1 ? 'The market' : 'Pick the outcomes to cover'}>
            {markets.length === 0 ? (
              <p className="text-sm text-muted">Nothing in this event is open for cover right now.</p>
            ) : (
              <Card className="max-h-[440px] divide-y divide-line overflow-y-auto">
                {markets.map((market) => {
                  const active = chosen.includes(market.ticker)
                  const full = !active && chosen.length >= MAX_LEGS
                  return (
                    <button
                      key={market.ticker}
                      disabled={full}
                      onClick={() => toggle(market.ticker)}
                      className={cn(
                        'flex w-full items-center gap-3 px-5 py-3.5 text-left text-sm transition disabled:opacity-40',
                        active ? 'bg-ink text-canvas' : 'hover:bg-canvas',
                      )}
                    >
                      <Checkbox checked={active} />
                      <span className="min-w-0 flex-1">
                        <span className="block font-medium">{market.outcome || market.title}</span>
                        <span className={cn('block text-xs', active ? 'text-canvas/70' : 'text-muted')}>
                          {market.outcome && market.outcome !== market.title && `${market.title} · `}closes {shortDate(market.close_time)}
                        </span>
                      </span>
                      <span className={cn('num shrink-0 text-xs', active ? 'text-canvas/80' : 'text-muted')}>
                        {market.yes_probability != null ? `${pct(market.yes_probability)} YES` : '—'}
                      </span>
                    </button>
                  )
                })}
              </Card>
            )}
            {markets.length > 1 && <p className="mt-2 text-xs text-muted">Pick up to {MAX_LEGS}. Each one pays separately.</p>}
          </Section>

          {request && (
            <Section number={2} title="Which result hurts your business?">
              <div className="grid gap-3 sm:grid-cols-2">
                {(['yes', 'no'] as const).map((option) => (
                  <button
                    key={option}
                    onClick={() => setSide(option)}
                    className={cn(
                      'rounded-2xl border bg-surface p-4 text-left transition',
                      side === option ? 'border-ink ring-1 ring-ink' : 'border-line hover:border-line-strong',
                    )}
                  >
                    <div className="font-semibold">Pay me if {option.toUpperCase()}</div>
                    <div className="mt-1 text-sm text-muted">
                      {option === 'yes' ? 'You lose money if this happens.' : "You lose money if this doesn't happen."}
                    </div>
                  </button>
                ))}
              </div>
            </Section>
          )}

          {request && (
            <Section number={3} title="How much would it cost you?">
              <PayoutPicker label={chosen.length > 1 ? 'Payout per outcome' : 'Payout'} value={payout} onChange={setPayout} />
            </Section>
          )}
        </div>

        <aside className="lg:sticky lg:top-24 lg:self-start">
          <QuoteCheckout request={request} emptyHint="Pick an outcome to see a live price." onPayout={setPayout} />
        </aside>
      </div>
    </>
  )
}
