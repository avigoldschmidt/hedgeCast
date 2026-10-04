import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { MapPin, Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import { api, type BrowseGroup, type Side, type TopicId } from '@/api/client'
import type { BuilderSelection } from '@/components/builder/types'
import { ErrorNote, Loading } from '@/components/domain'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input, Select } from '@/components/ui/field'
import { Section } from '@/components/quote'
import { cn, pct, shortDate } from '@/lib/format'
import { TOPICS } from '@/lib/topics'

const TITLES: Partial<Record<TopicId, { heading: string; sub: string; event: string; outcome: string }>> = {
  fuel: {
    heading: 'Fuel and gas',
    sub: 'Which pump or oil price would hurt your costs?',
    event: 'Which market',
    outcome: 'Which level',
  },
  rates: {
    heading: 'Interest rates',
    sub: 'Which Fed or rate decision do you want cover for?',
    event: 'Which decision',
    outcome: 'Which outcome',
  },
  prices: {
    heading: 'Prices and inflation',
    sub: 'Which price series would squeeze your margins?',
    event: 'Which series',
    outcome: 'Which outcome',
  },
  tariffs: {
    heading: 'Trade and tariffs',
    sub: 'Which trade event could raise your import costs?',
    event: 'Which event',
    outcome: 'Which outcome',
  },
  sports: {
    heading: 'Sports and big events',
    sub: 'Which game day could fill or empty your place?',
    event: 'Which game',
    outcome: 'Which outcome',
  },
  jobs: {
    heading: 'Jobs and wages',
    sub: 'Which jobs or wage report matters for your business?',
    event: 'Which report',
    outcome: 'Which outcome',
  },
}

export function TopicNarrow({
  topic,
  cityName,
  hasCity,
  onContinue,
}: {
  topic: TopicId
  cityName?: string
  hasCity: boolean
  onContinue: (selection: BuilderSelection) => void
}) {
  const queryClient = useQueryClient()
  const copy = TITLES[topic] ?? {
    heading: TOPICS[topic].name,
    sub: 'Narrow down the cover that fits.',
    event: 'Which event',
    outcome: 'Which outcome',
  }
  const [filter, setFilter] = useState('')
  const [groupId, setGroupId] = useState<string | null>(null)
  const [ticker, setTicker] = useState<string | null>(null)
  const [side, setSide] = useState<Side>('yes')

  const browse = useQuery({
    queryKey: ['browse', topic],
    queryFn: () => api.browse(topic),
    staleTime: 30_000,
  })
  const cities = useQuery({ queryKey: ['cities'], queryFn: api.cities, enabled: topic === 'sports' && !hasCity })
  const setCity = useMutation({
    mutationFn: api.setCity,
    onSuccess: (data) => {
      queryClient.setQueryData(['me'], data)
      queryClient.invalidateQueries({ queryKey: ['browse', topic] })
    },
  })

  const groups = useMemo(() => {
    const all = browse.data?.groups ?? []
    const q = filter.trim().toLowerCase()
    if (!q) return all
    return all.filter((group) => group.title.toLowerCase().includes(q) || group.options.some((o) => o.label.toLowerCase().includes(q)))
  }, [browse.data, filter])

  const group: BrowseGroup | undefined = groups.find((item) => item.id === groupId) ?? groups[0]
  const option = group?.options.find((item) => item.ticker === ticker) ?? group?.options[0]

  function continueWithPick() {
    if (!group || !option) return
    const title = `${group.title} · ${option.label}`
    onContinue({
      topic,
      title,
      why: copy.sub,
      catch: group.settles_on,
      legs: [{ ticker: option.ticker, side }],
    })
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display text-[34px] leading-tight font-semibold tracking-tight">{copy.heading}</h1>
        <p className="mt-2 text-muted">{copy.sub}</p>
      </div>

      {topic === 'sports' && !hasCity && (
        <Card className="flex flex-wrap items-center gap-3 p-4">
          <MapPin className="size-4 text-muted" />
          <span className="text-sm text-muted">Add your city to surface local games first.</span>
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

      {topic === 'sports' && (
        <div className="relative">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted" />
          <Input
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            placeholder="Filter by team or event…"
            className="pl-10"
          />
        </div>
      )}

      {browse.isPending && <Loading label="Finding open cover…" />}
      <ErrorNote error={browse.error} />
      {browse.data?.message && <p className="rounded-xl border border-line bg-surface px-4 py-3 text-sm text-muted">{browse.data.message}</p>}

      {groups.length > 0 && (
        <>
          <Section number={1} title={copy.event}>
            <div className="space-y-2">
              {groups.map((item) => {
                const active = (groupId ?? groups[0]?.id) === item.id
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => {
                      setGroupId(item.id)
                      setTicker(item.options[0]?.ticker ?? null)
                    }}
                    className={cn(
                      'flex w-full items-start gap-3 rounded-xl border px-4 py-3 text-left transition',
                      active ? 'border-ink ring-1 ring-ink' : 'border-line hover:border-line-strong',
                    )}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="font-medium">{item.title}</div>
                      <div className="mt-0.5 text-xs text-muted">
                        {item.options.length} outcome{item.options.length === 1 ? '' : 's'}
                        {item.options[0] && ` · by ${shortDate(item.options[0].closes_at)}`}
                      </div>
                      {item.warning && <div className="mt-1 text-xs text-sun">{item.warning}</div>}
                    </div>
                  </button>
                )
              })}
            </div>
          </Section>

          {group && (
            <Section number={2} title={copy.outcome}>
              <div className="flex flex-wrap gap-2">
                {group.options.map((item) => {
                  const active = (ticker ?? group.options[0]?.ticker) === item.ticker
                  return (
                    <button
                      key={item.ticker}
                      type="button"
                      onClick={() => setTicker(item.ticker)}
                      className={cn(
                        'rounded-full border px-3.5 py-1.5 text-sm transition',
                        active ? 'border-ink bg-ink text-canvas' : 'border-line-strong bg-surface hover:border-ink/40',
                      )}
                    >
                      {item.label}
                      {item.chance != null && <span className="num ml-1.5 opacity-70">{pct(item.chance)}</span>}
                    </button>
                  )
                })}
              </div>
              <p className="mt-2 text-xs text-muted">{group.settles_on}</p>
            </Section>
          )}

          <Section number={3} title="When should it pay?">
            <div className="grid grid-cols-2 gap-2">
              {(['yes', 'no'] as const).map((optionSide) => (
                <button
                  key={optionSide}
                  type="button"
                  onClick={() => setSide(optionSide)}
                  className={cn(
                    'rounded-xl border px-3.5 py-2.5 text-left text-sm transition',
                    side === optionSide ? 'border-ink ring-1 ring-ink' : 'border-line hover:border-line-strong',
                  )}
                >
                  <span className="block font-medium">
                    {optionSide === 'yes' ? 'Pay me if it happens' : "Pay me if it doesn't"}
                  </span>
                </button>
              ))}
            </div>
            {cityName && topic === 'sports' && (
              <p className="mt-2 text-xs text-muted">Local games near {cityName} are listed first.</p>
            )}
          </Section>

          <Button type="button" size="lg" disabled={!option} onClick={continueWithPick}>
            Continue
          </Button>
        </>
      )}
    </div>
  )
}
