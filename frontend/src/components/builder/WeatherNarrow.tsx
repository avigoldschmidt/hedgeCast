import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, MapPin } from 'lucide-react'
import { useMemo, useState } from 'react'
import { api, type PerilId, type S } from '@/api/client'
import type { BuilderSelection } from '@/components/builder/types'
import { BasisRiskBadge, Checkbox, ErrorNote, Loading, PerilIcon } from '@/components/domain'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Select } from '@/components/ui/field'
import { Section } from '@/components/quote'
import { cn, dayLabel, pct } from '@/lib/format'

export function WeatherNarrow({
  cityName,
  hasCity,
  onContinue,
}: {
  cityName?: string
  hasCity: boolean
  onContinue: (selection: BuilderSelection) => void
}) {
  const queryClient = useQueryClient()
  const [peril, setPeril] = useState<PerilId | null>(null)
  const [picks, setPicks] = useState<Partial<Record<PerilId, Record<string, string>>>>({})
  const cities = useQuery({ queryKey: ['cities'], queryFn: api.cities })
  const perils = useQuery({ queryKey: ['perils'], queryFn: api.perils })
  const options = useQuery({
    queryKey: ['weather', peril],
    queryFn: () => api.weather(peril as PerilId),
    enabled: peril !== null && hasCity,
    staleTime: 30_000,
  })
  const setCity = useMutation({
    mutationFn: api.setCity,
    onSuccess: (data) => {
      queryClient.setQueryData(['me'], data)
      queryClient.invalidateQueries({ queryKey: ['weather'] })
    },
  })

  const selected = useMemo(() => {
    if (peril && picks[peril]) return picks[peril]
    const first = options.data?.days.find((day) => day.triggers.length > 0)
    return first ? { [first.date]: first.triggers[0].ticker } : {}
  }, [peril, picks, options.data])

  const tickers = Object.values(selected)

  function toggleDay(date: string, ticker: string) {
    if (!peril) return
    const next = { ...selected }
    if (next[date] === ticker) delete next[date]
    else next[date] = ticker
    setPicks({ ...picks, [peril]: next })
  }

  function continueWithDays() {
    if (!peril || !options.data || tickers.length === 0) return
    const labels = tickers.map((ticker) => {
      for (const day of options.data.days) {
        const trigger = day.triggers.find((item) => item.ticker === ticker)
        if (trigger) return `${dayLabel(day.date)} · ${trigger.label}`
      }
      return ticker
    })
    const title =
      tickers.length === 1
        ? `${options.data.peril.name} · ${labels[0]}`
        : `${options.data.peril.name} · ${tickers.length} days`
    onContinue({
      topic: 'weather',
      title,
      why: `Cover for ${options.data.peril.name.toLowerCase()} near you.`,
      catch: `Settles on the official ${options.data.station.name} reading.`,
      legs: tickers.map((ticker) => ({ ticker, side: 'yes' as const })),
    })
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display text-[34px] leading-tight font-semibold tracking-tight">
          {cityName ? `Weather near ${cityName}` : 'Weather cover'}
        </h1>
        <p className="mt-2 text-muted">What weather would cost you money?</p>
      </div>

      {!hasCity && (
        <Card className="flex flex-wrap items-center gap-3 p-4">
          <MapPin className="size-4 text-muted" />
          <span className="text-sm text-muted">Choose your city for local weather cover.</span>
          <Select
            aria-label="Your city"
            className="h-9 w-auto min-w-[12rem]"
            defaultValue=""
            disabled={setCity.isPending || cities.isPending}
            onChange={(event) => {
              if (event.target.value) setCity.mutate(event.target.value)
            }}
          >
            <option value="" disabled>
              {cities.isPending ? 'Loading…' : 'Choose city'}
            </option>
            {cities.data?.map((city) => (
              <option key={city.id} value={city.id}>
                {city.name}, {city.state}
              </option>
            ))}
          </Select>
          <ErrorNote error={setCity.error} />
        </Card>
      )}

      <Section number={1} title="Choose the weather">
        {perils.isPending && <Loading label="Loading…" />}
        <ErrorNote error={perils.error} />
        <div className="grid gap-3 sm:grid-cols-3">
          {perils.data?.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setPeril(item.id)}
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

      {peril && hasCity && (
        <Section number={2} title="Pick the days">
          {options.isPending && <Loading label="Finding markets near you" />}
          <ErrorNote error={options.error} />
          {options.data && (
            <>
              <StationCard station={options.data.station} city={cityName} />
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

      {peril && tickers.length > 0 && (
        <Button type="button" size="lg" onClick={continueWithDays}>
          Continue with {tickers.length} {tickers.length === 1 ? 'day' : 'days'}
        </Button>
      )}
    </div>
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
                type="button"
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
