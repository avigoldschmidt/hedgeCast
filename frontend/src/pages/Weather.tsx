import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Check, MapPin } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { api, type PerilId, type S } from '@/api/client'
import { BasisRiskBadge, Checkbox, ErrorNote, Loading, PageHeader, PerilIcon } from '@/components/domain'
import { PayoutPicker, QuoteCheckout, Section } from '@/components/quote'
import { Card } from '@/components/ui/card'
import { cn, dayLabel, pct } from '@/lib/format'

export function Weather() {
  const [params, setParams] = useSearchParams()
  const peril = (params.get('peril') as PerilId | null) ?? null
  const [picks, setPicks] = useState<Partial<Record<PerilId, Record<string, string>>>>({})
  const [payout, setPayout] = useState(1000)

  const me = useQuery({ queryKey: ['me'], queryFn: api.me })
  const perils = useQuery({ queryKey: ['perils'], queryFn: api.perils })
  const options = useQuery({
    queryKey: ['weather', peril],
    queryFn: () => api.weather(peril as PerilId),
    enabled: peril !== null,
    staleTime: 30_000,
  })

  const selected = useMemo(() => {
    if (peril && picks[peril]) return picks[peril]
    const first = options.data?.days.find((day) => day.triggers.length > 0)
    return first ? { [first.date]: first.triggers[0].ticker } : {}
  }, [peril, picks, options.data])
  const tickers = Object.values(selected)
  const request: S['QuoteRequest'] | null =
    peril && tickers.length > 0
      ? { peril, legs: tickers.map((ticker) => ({ ticker, side: 'yes' as const })), payout_dollars: payout }
      : null

  function toggleDay(date: string, ticker: string) {
    if (!peril) return
    const next = { ...selected }
    if (next[date] === ticker) delete next[date]
    else next[date] = ticker
    setPicks({ ...picks, [peril]: next })
  }

  return (
    <>
      <Link to="/protect" className="mb-6 inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink">
        <ArrowLeft className="size-4" /> All markets
      </Link>
      <PageHeader eyebrow={me.data?.city ? `Weather near ${me.data.city.name}` : 'Weather'} title="What weather would cost you money?" />
      <div className="grid gap-8 lg:grid-cols-[1fr_400px]">
        <div className="space-y-8">
          <Section number={1} title="Choose the weather">
            <div className="grid gap-3 sm:grid-cols-3">
              {perils.data?.map((item) => (
                <button
                  key={item.id}
                  onClick={() => setParams({ peril: item.id })}
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
              {options.isPending && <Loading label="Finding markets near you" />}
              <ErrorNote error={options.error} />
              {options.data && (
                <>
                  <StationCard station={options.data.station} city={me.data?.city?.name} />
                  {options.data.message && (
                    <p className="mt-4 rounded-xl border border-line bg-surface px-4 py-3 text-sm text-muted">{options.data.message}</p>
                  )}
                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    {options.data.days.map((day) => (
                      <DayCard key={day.date} day={day} selected={selected[day.date]} onToggle={toggleDay} />
                    ))}
                  </div>
                </>
              )}
            </Section>
          )}

          {request && (
            <Section number={3} title="How much would a bad day cost you?">
              <PayoutPicker label="Payout per covered day" value={payout} onChange={setPayout} />
            </Section>
          )}
        </div>

        <aside className="lg:sticky lg:top-24 lg:self-start">
          <QuoteCheckout request={request} emptyHint="Pick the weather and a day to see a live price." onPayout={setPayout} />
        </aside>
      </div>
    </>
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
                <Checkbox checked={active} />
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