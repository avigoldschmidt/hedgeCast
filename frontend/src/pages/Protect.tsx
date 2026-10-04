import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Calculator, Check, Clock, Info, Lock, MapPin, RefreshCw } from 'lucide-react'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { api, type PerilId, type S } from '@/api/client'
import { BasisRiskBadge, ErrorNote, Loading, PageHeader, PerilIcon } from '@/components/domain'
import { Button } from '@/components/ui/button'
import { Card, CardBody } from '@/components/ui/card'
import { Input } from '@/components/ui/field'
import { cn, dayLabel, money, pct } from '@/lib/format'
import { useDebounced } from '@/lib/useDebounced'

const PRESETS = [500, 1000, 2500, 5000]

export function Protect() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [params, setParams] = useSearchParams()
  const peril = (params.get('peril') as PerilId | null) ?? null
  const [picks, setPicks] = useState<Partial<Record<PerilId, Record<string, string>>>>({})
  const [payout, setPayout] = useState(1000)
  const [allOrNothing, setAllOrNothing] = useState(false)

  const me = useQuery({ queryKey: ['me'], queryFn: api.me })
  const perils = useQuery({ queryKey: ['perils'], queryFn: api.perils })
  const coverage = useQuery({
    queryKey: ['coverage', peril],
    queryFn: () => api.coverage(peril as PerilId),
    enabled: peril !== null,
    staleTime: 30_000,
  })

  const selected = useMemo(() => {
    if (peril && picks[peril]) return picks[peril]
    const first = coverage.data?.days.find((day) => day.triggers.length > 0)
    return first ? { [first.date]: first.triggers[0].ticker } : {}
  }, [peril, picks, coverage.data])
  const tickers = useMemo(() => Object.values(selected), [selected])
  const quote = useLiveQuote(peril, tickers, payout)

  const bind = useMutation({
    mutationFn: api.bind,
    onSuccess: (policy) => {
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      queryClient.invalidateQueries({ queryKey: ['policies'] })
      queryClient.invalidateQueries({ queryKey: ['me'] })
      navigate(`/policies/${policy.id}`, { state: { justBound: true } })
    },
  })

  function choosePeril(id: PerilId) {
    setParams({ peril: id })
    bind.reset()
  }

  function toggleDay(date: string, ticker: string) {
    if (!peril) return
    const next = { ...selected }
    if (next[date] === ticker) delete next[date]
    else next[date] = ticker
    setPicks({ ...picks, [peril]: next })
  }

  return (
    <>
      <PageHeader eyebrow="New protection" title="What weather would cost you money?" />
      <div className="grid gap-8 lg:grid-cols-[1fr_400px]">
        <div className="space-y-8">
          <Section number={1} title="Choose the weather">
            <div className="grid gap-3 sm:grid-cols-3">
              {perils.data?.map((item) => (
                <button
                  key={item.id}
                  onClick={() => choosePeril(item.id)}
                  className={cn(
                    'relative rounded-2xl border bg-surface p-5 text-left transition',
                    peril === item.id ? 'border-ink shadow-lift ring-1 ring-ink' : 'border-line hover:border-line-strong hover:shadow-card',
                  )}
                >
                  {peril === item.id && (
                    <span className="absolute top-4 right-4 inline-flex size-5 items-center justify-center rounded-full bg-ink text-canvas">
                      <Check className="size-3" />
                    </span>
                  )}
                  <PerilIcon peril={item.id} />
                  <div className="mt-4 font-semibold">{item.name}</div>
                  <div className="mt-1 text-sm leading-snug text-muted">{item.description}</div>
                </button>
              ))}
            </div>
          </Section>

          {peril && (
            <Section number={2} title="Pick the days">
              {coverage.isPending && <Loading label="Finding markets near you" />}
              <ErrorNote error={coverage.error} />
              {coverage.data && (
                <>
                  {coverage.data.station && <StationCard station={coverage.data.station} city={me.data?.city.name} />}
                  {coverage.data.message && (
                    <p className="mt-4 rounded-xl border border-line bg-surface px-4 py-3 text-sm text-muted">{coverage.data.message}</p>
                  )}
                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    {coverage.data.days.map((day) => (
                      <DayCard key={day.date} day={day} selected={selected[day.date]} onToggle={toggleDay} />
                    ))}
                  </div>
                </>
              )}
            </Section>
          )}

          {peril && tickers.length > 0 && (
            <Section number={3} title="How much would a bad day cost you?">
              <PayoutPicker value={payout} onChange={setPayout} />
            </Section>
          )}
        </div>

        <aside className="lg:sticky lg:top-24 lg:self-start">
          <QuotePanel
            quote={quote}
            payout={payout}
            ready={peril !== null && tickers.length > 0}
            bankLinked={me.data?.bank.linked ?? false}
            accountMask={me.data?.bank.account_mask ?? null}
            allOrNothing={allOrNothing}
            onAllOrNothing={setAllOrNothing}
            onTakeAvailable={(dollars) => setPayout(dollars)}
            onBuy={(quoteId) => bind.mutate({ quote_id: quoteId, all_or_nothing: allOrNothing })}
            buying={bind.isPending}
            buyError={bind.error}
          />
        </aside>
      </div>
    </>
  )
}

function Section({ number, title, children }: { number: number; title: string; children: ReactNode }) {
  return (
    <section>
      <h2 className="mb-4 flex items-center gap-3 text-lg font-semibold">
        <span className="inline-flex size-7 items-center justify-center rounded-full bg-ink text-sm text-canvas">{number}</span>
        {title}
      </h2>
      {children}
    </section>
  )
}

function StationCard({ station, city }: { station: S['Station']; city?: string }) {
  return (
    <Card className="flex flex-wrap items-start gap-4 p-5">
      <span className="inline-flex size-10 items-center justify-center rounded-xl bg-ink/5 text-ink-soft">
        <MapPin className="size-5" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium">Settles on the official {station.name} reading</span>
          <BasisRiskBadge risk={station.basis_risk} />
        </div>
        <p className="mt-1 text-sm text-muted">
          {station.distance_km > 0 ? `${station.distance_km} km from ${city ?? 'you'}. ` : ''}
          {station.basis_note}
        </p>
      </div>
    </Card>
  )
}

function DayCard({
  day,
  selected,
  onToggle,
}: {
  day: S['CoverageDay']
  selected?: string
  onToggle: (date: string, ticker: string) => void
}) {
  return (
    <Card className={cn('p-4 transition', selected && 'border-ink ring-1 ring-ink')}>
      <div className="text-sm font-semibold">{dayLabel(day.date)}</div>
      {day.triggers.length === 0 ? (
        <p className="mt-2 text-sm text-muted">No market is open for this day yet.</p>
      ) : (
        <div className="mt-3 space-y-2">
          {day.triggers.map((trigger) => {
            const active = selected === trigger.ticker
            return (
              <button
                key={trigger.ticker}
                onClick={() => onToggle(day.date, trigger.ticker)}
                className={cn(
                  'flex w-full items-center gap-3 rounded-lg border px-3 py-2.5 text-left text-sm transition',
                  active ? 'border-ink bg-ink text-canvas' : 'border-line hover:border-line-strong',
                )}
              >
                <span
                  className={cn(
                    'inline-flex size-4 items-center justify-center rounded border',
                    active ? 'border-canvas bg-canvas text-ink' : 'border-line-strong',
                  )}
                >
                  {active && <Check className="size-3" />}
                </span>
                <span className="flex-1 font-medium">{trigger.label}</span>
                {trigger.implied_probability != null && (
                  <span className={cn('num text-xs', active ? 'text-canvas/70' : 'text-muted')}>
                    {pct(trigger.implied_probability)} chance
                  </span>
                )}
              </button>
            )
          })}
        </div>
      )}
    </Card>
  )
}

function PayoutPicker({ value, onChange }: { value: number; onChange: (value: number) => void }) {
  const [estimating, setEstimating] = useState(false)
  const [revenue, setRevenue] = useState(3000)
  const [share, setShare] = useState(60)
  const estimate = Math.max(1, Math.round((revenue * share) / 100))

  return (
    <Card>
      <CardBody>
        <div className="flex flex-wrap items-end gap-4">
          <label className="block flex-1">
            <span className="mb-1.5 block text-sm font-medium">Payout per covered day</span>
            <div className="relative">
              <span className="absolute top-1/2 left-4 -translate-y-1/2 text-xl text-muted">$</span>
              <Input
                type="number"
                inputMode="numeric"
                min={1}
                step={1}
                value={value}
                onChange={(event) => onChange(Math.max(0, Math.floor(Number(event.target.value) || 0)))}
                className="num h-14 pl-9 text-2xl font-semibold"
              />
            </div>
          </label>
          <div className="flex flex-wrap gap-2">
            {PRESETS.map((preset) => (
              <button
                key={preset}
                onClick={() => onChange(preset)}
                className={cn(
                  'num h-10 rounded-lg border px-3.5 text-sm font-medium transition',
                  value === preset ? 'border-ink bg-ink text-canvas' : 'border-line-strong bg-surface hover:bg-canvas',
                )}
              >
                {money(preset * 100)}
              </button>
            ))}
          </div>
        </div>
        <p className="mt-3 text-xs text-muted">Whole dollars. Each dollar of payout is backed one-for-one by a market contract.</p>

        <div className="mt-5 border-t border-line pt-4">
          <button onClick={() => setEstimating(!estimating)} className="inline-flex items-center gap-2 text-sm font-medium text-brand">
            <Calculator className="size-4" /> {estimating ? 'Hide estimator' : 'Help me estimate'}
          </button>
          {estimating && (
            <div className="mt-4 grid items-end gap-4 sm:grid-cols-[1fr_1fr_auto]">
              <label className="block text-sm">
                <span className="mb-1.5 block font-medium">Sales on a normal day</span>
                <Input type="number" min={0} value={revenue} onChange={(event) => setRevenue(Number(event.target.value) || 0)} />
              </label>
              <label className="block text-sm">
                <span className="mb-1.5 block font-medium">Share you'd lose ({share}%)</span>
                <input
                  type="range"
                  min={5}
                  max={100}
                  step={5}
                  value={share}
                  onChange={(event) => setShare(Number(event.target.value))}
                  className="h-11 w-full accent-ink"
                />
              </label>
              <Button variant="outline" onClick={() => onChange(estimate)}>
                Use {money(estimate * 100)}
              </Button>
            </div>
          )}
        </div>
      </CardBody>
    </Card>
  )
}

type LiveQuote = {
  data: S['Quote'] | null
  error: unknown
  loading: boolean
  refresh: () => void
}

function useLiveQuote(peril: PerilId | null, tickers: string[], payout: number): LiveQuote {
  const key = JSON.stringify({ peril, tickers, payout })
  const debouncedKey = useDebounced(key, 450)
  const request = useMemo(
    () => JSON.parse(debouncedKey) as { peril: PerilId | null; tickers: string[]; payout: number },
    [debouncedKey],
  )
  const query = useQuery({
    queryKey: ['quote', debouncedKey],
    queryFn: () => api.quote({ peril: request.peril as PerilId, tickers: request.tickers, payout_dollars: request.payout }),
    enabled: request.peril !== null && request.tickers.length > 0 && request.payout >= 1,
    staleTime: Infinity,
    gcTime: 0,
  })
  const settled = debouncedKey === key
  return {
    data: settled ? (query.data ?? null) : null,
    error: settled ? query.error : null,
    loading: !settled || query.isFetching,
    refresh: () => void query.refetch(),
  }
}

function useSecondsLeft(expiresAt: string | undefined) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 500)
    return () => clearInterval(timer)
  }, [])
  if (!expiresAt) return 0
  return Math.max(0, Math.ceil((new Date(expiresAt).getTime() - now) / 1000))
}

function QuotePanel({
  quote,
  payout,
  ready,
  bankLinked,
  accountMask,
  allOrNothing,
  onAllOrNothing,
  onTakeAvailable,
  onBuy,
  buying,
  buyError,
}: {
  quote: LiveQuote
  payout: number
  ready: boolean
  bankLinked: boolean
  accountMask: string | null
  allOrNothing: boolean
  onAllOrNothing: (value: boolean) => void
  onTakeAvailable: (dollars: number) => void
  onBuy: (quoteId: string) => void
  buying: boolean
  buyError: unknown
}) {
  const q = quote.data
  const secondsLeft = useSecondsLeft(q?.expires_at)
  const expired = q !== null && secondsLeft === 0
  const short = q?.thin_book.short ?? false
  const canBuy = q !== null && !expired && bankLinked && !buying && (!short || allOrNothing)

  return (
    <Card className="overflow-hidden">
      <div className="flex items-center justify-between border-b border-line bg-canvas/60 px-6 py-3.5">
        <span className="text-sm font-semibold">Your quote</span>
        {q && !expired && (
          <span className="num inline-flex items-center gap-1.5 text-xs font-medium text-brand">
            <Lock className="size-3" /> Price locked · {secondsLeft}s
          </span>
        )}
        {expired && (
          <button onClick={quote.refresh} className="inline-flex items-center gap-1.5 text-xs font-medium text-sun hover:underline">
            <Clock className="size-3" /> Expired · refresh
          </button>
        )}
        {quote.loading && <span className="text-xs text-muted">Pricing…</span>}
      </div>

      <CardBody>
        {!ready && <p className="py-8 text-center text-sm text-muted">Pick the weather and a day to see a live price.</p>}
        {ready && !q && !quote.error && (
          <div className="space-y-3 py-4">
            <div className="h-10 w-32 animate-pulse rounded-lg bg-ink/5" />
            <div className="h-4 w-48 animate-pulse rounded bg-ink/5" />
            <div className="h-24 animate-pulse rounded-lg bg-ink/5" />
          </div>
        )}
        {ready && quote.error != null && (
          <div className="space-y-3">
            <ErrorNote error={quote.error} />
            <Button variant="outline" size="sm" onClick={quote.refresh}>
              <RefreshCw className="size-3.5" /> Try again
            </Button>
          </div>
        )}

        {q && (
          <div className={cn('transition-opacity', (expired || quote.loading) && 'opacity-50')}>
            <div className="flex items-baseline gap-2">
              <span className="num font-display text-5xl font-semibold tracking-tight">{money(q.premium_cents)}</span>
              <span className="text-sm text-muted">one-time</span>
            </div>
            <p className="mt-1 text-sm text-ink-soft">
              Pays <strong className="num">{money(q.payout_per_day_cents)}</strong> per covered day
              {q.legs.length > 1 && (
                <>
                  , up to <strong className="num">{money(q.max_payout_cents)}</strong>
                </>
              )}
              .
            </p>

            <div className="mt-5 space-y-2.5">
              {q.legs.map((leg) => (
                <div key={leg.ticker}>
                  <div className="flex justify-between text-xs">
                    <span className="text-ink-soft">
                      {dayLabel(leg.date)} · {leg.label}
                    </span>
                    <span className="num font-medium">{pct(leg.implied_probability)} chance</span>
                  </div>
                  <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-ink/5">
                    <div className="h-full rounded-full bg-brand" style={{ width: `${Math.max(2, leg.implied_probability * 100)}%` }} />
                  </div>
                </div>
              ))}
            </div>

            <details className="group mt-5 rounded-xl border border-line text-sm">
              <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3 font-medium">
                How this price is built
                <span className="text-xs text-muted group-open:hidden">Show</span>
              </summary>
              <dl className="space-y-1.5 border-t border-line px-4 py-3">
                <Line label="Market cost of cover" cents={q.breakdown.hedge_cost_cents} />
                <Line label="Exchange fees" cents={q.breakdown.exchange_fee_cents} />
                <Line label="Execution buffer" cents={q.breakdown.buffer_cents} />
                <Line label="HedgeCast fee" cents={q.breakdown.platform_fee_cents} />
                <Line label="Rounded to whole dollars" cents={q.breakdown.rounding_cents} />
                <div className="flex justify-between border-t border-line pt-1.5 font-semibold">
                  <dt>Premium</dt>
                  <dd className="num">{money(q.premium_cents)}</dd>
                </div>
              </dl>
            </details>

            <div className="mt-4 rounded-xl bg-canvas px-4 py-3 text-sm leading-relaxed text-ink-soft">
              <div className="mb-1 flex items-center gap-1.5 text-xs font-semibold tracking-wide text-muted uppercase">
                <Info className="size-3" /> The terms
              </div>
              {q.terms}
            </div>

            {q.warnings.map((warning) => (
              <div key={warning} className="mt-3 flex gap-2 rounded-xl border border-sun/30 bg-sun-soft px-4 py-3 text-sm text-ink-soft">
                <AlertTriangle className="mt-0.5 size-4 shrink-0 text-sun" />
                {warning}
              </div>
            ))}

            {short && (
              <ThinBookPanel
                quote={q}
                payout={payout}
                allOrNothing={allOrNothing}
                onAllOrNothing={onAllOrNothing}
                onTakeAvailable={onTakeAvailable}
              />
            )}

            <div className="mt-5">
              <ErrorNote error={buyError} />
              <Button size="lg" className="mt-3 w-full" disabled={!canBuy} onClick={() => onBuy(q.id)}>
                {buying ? 'Setting up your cover…' : `Buy protection · ${money(q.premium_cents)}`}
              </Button>
              <p className="mt-2.5 text-center text-xs text-muted">
                {bankLinked
                  ? `Charged to checking ••${accountMask}. Payouts go to the same account automatically.`
                  : 'Connect checking on your dashboard before buying.'}
              </p>
            </div>
          </div>
        )}
      </CardBody>
    </Card>
  )
}

function Line({ label, cents }: { label: string; cents: number }) {
  return (
    <div className="flex justify-between text-ink-soft">
      <dt>{label}</dt>
      <dd className="num">{money(cents)}</dd>
    </div>
  )
}

function ThinBookPanel({
  quote,
  payout,
  allOrNothing,
  onAllOrNothing,
  onTakeAvailable,
}: {
  quote: S['Quote']
  payout: number
  allOrNothing: boolean
  onAllOrNothing: (value: boolean) => void
  onTakeAvailable: (dollars: number) => void
}) {
  const available = quote.thin_book.max_payout_dollars
  return (
    <div className="mt-4 rounded-xl border border-sun/40 bg-sun-soft/70 p-4 text-sm">
      <div className="flex items-center gap-2 font-semibold">
        <AlertTriangle className="size-4 text-sun" /> The market is thin right now
      </div>
      <p className="mt-1 text-ink-soft">
        {available > 0
          ? `There's only enough on offer to cover ${money(available * 100)} per day, not ${money(payout * 100)}.`
          : 'Nobody is offering this cover at a sensible price right now.'}
      </p>
      <div className="mt-3 space-y-2">
        {available > 0 && (
          <button
            onClick={() => onTakeAvailable(available)}
            className="w-full rounded-lg border border-line-strong bg-surface px-3 py-2 text-left font-medium hover:bg-canvas"
          >
            Cover {money(available * 100)} per day instead
          </button>
        )}
        <label className="flex cursor-pointer items-start gap-2.5 rounded-lg border border-line-strong bg-surface px-3 py-2">
          <input type="checkbox" checked={allOrNothing} onChange={(event) => onAllOrNothing(event.target.checked)} className="mt-0.5 accent-ink" />
          <span>
            <span className="font-medium">Try for the full amount</span>
            <span className="block text-xs text-muted">If it can't be fully covered, your premium is refunded right away.</span>
          </span>
        </label>
      </div>
    </div>
  )
}
