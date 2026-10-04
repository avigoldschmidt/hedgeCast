import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ArrowRight, CloudSun, Search } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { api, type S } from '@/api/client'
import { CategoryIcon, ErrorNote, Loading, PageHeader } from '@/components/domain'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/field'
import { cn, pct, shortDate } from '@/lib/format'
import { useDebounced } from '@/lib/useDebounced'

export function Browse() {
  const [text, setText] = useState('')
  const [category, setCategory] = useState<string | null>(null)
  const query = useDebounced(text.trim(), 300)
  const me = useQuery({ queryKey: ['me'], queryFn: api.me })
  const markets = useQuery({
    queryKey: ['markets', query, category],
    queryFn: () => api.markets(query, category),
    placeholderData: keepPreviousData,
    staleTime: 60_000,
  })
  const city = me.data?.city

  return (
    <>
      <PageHeader eyebrow="New protection" title="What would cost your business money?" />

      <div className="relative">
        <Search className="pointer-events-none absolute top-1/2 left-4 size-5 -translate-y-1/2 text-muted" />
        <Input
          autoFocus
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder="Search Kalshi: Fed rates, gas prices, tariffs, an election…"
          className="h-14 pl-12 text-base"
        />
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <Tab active={category === null} onClick={() => setCategory(null)}>
          All
        </Tab>
        {markets.data?.categories.map((name) => (
          <Tab key={name} active={category === name} onClick={() => setCategory(category === name ? null : name)}>
            {name}
          </Tab>
        ))}
      </div>

      {city && !query && (category === null || category === 'Climate and Weather') && (
        <Link to="/weather" className="group mt-6 block">
          <Card className="flex items-center gap-4 border-sky/30 bg-sky-soft/50 p-5 transition group-hover:shadow-lift">
            <span className="inline-flex size-10 items-center justify-center rounded-xl bg-sky-soft text-sky">
              <CloudSun className="size-5" />
            </span>
            <div className="flex-1">
              <div className="font-medium">Weather near {city.name}</div>
              <div className="text-sm text-muted">Cover rain, heat, or a cold snap on the days that matter, settled at your local station.</div>
            </div>
            <ArrowRight className="size-4 text-muted transition group-hover:translate-x-0.5 group-hover:text-ink" />
          </Card>
        </Link>
      )}

      <div className="mt-6">
        {markets.isPending && <Loading label="Loading Kalshi markets" />}
        <ErrorNote error={markets.error} />
        {markets.data && markets.data.events.length === 0 && (
          <p className="py-12 text-center text-sm text-muted">No open markets match that. Try a broader word.</p>
        )}
        <div className={cn('grid gap-4 md:grid-cols-2', markets.isPlaceholderData && 'opacity-60')}>
          {markets.data?.events.map((event) => (
            <EventCard key={event.event_ticker} event={event} />
          ))}
        </div>
      </div>
    </>
  )
}

function Tab({ active, onClick, children }: { active: boolean; onClick: () => void; children: string }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'h-9 rounded-full border px-4 text-sm font-medium transition',
        active ? 'border-ink bg-ink text-canvas' : 'border-line-strong bg-surface text-ink-soft hover:text-ink',
      )}
    >
      {children}
    </button>
  )
}

function EventCard({ event }: { event: S['EventCard'] }) {
  return (
    <Link to={`/events/${event.event_ticker}`} className="group block">
      <Card className="h-full p-5 transition group-hover:border-line-strong group-hover:shadow-lift">
        <div className="flex items-start gap-3">
          <CategoryIcon category={event.category} />
          <div className="min-w-0 flex-1">
            <div className="font-semibold leading-snug">{event.title}</div>
            <div className="mt-0.5 text-xs text-muted">
              {event.category}
              {event.sub_title && ` · ${event.sub_title}`} · closes {shortDate(event.closes_at)}
            </div>
          </div>
        </div>
        <ul className="mt-4 space-y-1.5 text-sm">
          {event.markets.map((market) => (
            <li key={market.ticker} className="flex justify-between gap-3">
              <span className="truncate text-ink-soft">{market.outcome || market.title}</span>
              <span className="num shrink-0 text-muted">{market.yes_probability != null ? pct(market.yes_probability) : '—'}</span>
            </li>
          ))}
        </ul>
        {event.market_count > event.markets.length && (
          <div className="mt-2 text-xs text-muted">+{event.market_count - event.markets.length} more outcomes</div>
        )}
      </Card>
    </Link>
  )
}
