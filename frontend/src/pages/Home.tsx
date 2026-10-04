import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, ArrowRight, Landmark, Search, ShieldCheck, X } from 'lucide-react'
import { useCallback, useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { api, type PlanCard, type TopicId } from '@/api/client'
import { ErrorNote, Loading, TopicIcon } from '@/components/domain'
import { ProtectSheet } from '@/components/ProtectSheet'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/field'
import { cn, money, pct, shortDate } from '@/lib/format'
import { OPEN_STATUSES } from '@/lib/status'
import { TOPICS } from '@/lib/topics'

const WEEK_MS = 7 * 24 * 60 * 60 * 1000

export function Home() {
  const queryClient = useQueryClient()
  const me = useQuery({ queryKey: ['me'], queryFn: api.me })
  const forecast = useQuery({ queryKey: ['forecast'], queryFn: api.forecast, staleTime: 60_000, refetchInterval: 60_000 })
  const policies = useQuery({ queryKey: ['policies'], queryFn: api.policies })
  const topics = useQuery({ queryKey: ['topics'], queryFn: api.topics })
  const [selected, setSelected] = useState<PlanCard | null>(null)
  const [question, setQuestion] = useState('')
  const [now] = useState(() => Date.now())
  const close = useCallback(() => setSelected(null), [])

  const watch = useMutation({
    mutationFn: api.setTopics,
    onSuccess: (data) => {
      queryClient.setQueryData(['me'], data)
      queryClient.invalidateQueries({ queryKey: ['forecast'] })
    },
  })
  const link = useMutation({
    mutationFn: api.linkBank,
    onSuccess: (data) => queryClient.setQueryData(['me'], data),
  })
  const ask = useMutation({ mutationFn: api.ask })

  if (me.isPending) return <Loading />
  if (me.isError) return <ErrorNote error={me.error} />
  const business = me.data

  function toggle(id: TopicId) {
    const next = business.topics.includes(id) ? business.topics.filter((t) => t !== id) : [...business.topics, id]
    if (next.length > 0) watch.mutate(next)
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    if (question.trim().length >= 3) ask.mutate(question.trim())
  }

  const cards = forecast.data?.cards ?? []
  const soon = cards.filter((card) => new Date(card.closes_at).getTime() - now < WEEK_MS)
  const later = cards.filter((card) => !soon.includes(card))
  const open = (policies.data ?? []).filter((policy) => OPEN_STATUSES.includes(policy.status))
  const paid = (policies.data ?? []).reduce((sum, policy) => sum + policy.paid_cents, 0)

  return (
    <div className="mx-auto max-w-3xl">
      <div className="text-sm font-medium text-brand">Good {greeting()}</div>
      <h1 className="font-display mt-1 text-[34px] leading-tight font-semibold tracking-tight">{business.name}</h1>
      <p className="mt-1 text-muted">
        Your forecast{business.city ? ` for ${business.city.name}` : ''}: the things coming up that could cost you money.
      </p>

      <div className="mt-5 flex flex-wrap items-center gap-2">
        <span className="mr-1 text-xs font-medium tracking-wide text-muted uppercase">Watching</span>
        {topics.data?.map((topic) => {
          const on = business.topics.includes(topic.id)
          const Icon = TOPICS[topic.id].icon
          return (
            <button
              key={topic.id}
              aria-pressed={on}
              title={topic.blurb}
              disabled={watch.isPending}
              onClick={() => toggle(topic.id)}
              className={cn(
                'inline-flex h-8 items-center gap-1.5 rounded-full border px-3 text-xs font-medium transition',
                on ? 'border-ink bg-ink text-canvas' : 'border-line-strong bg-surface text-muted hover:text-ink',
              )}
            >
              <Icon className="size-3.5" /> {topic.name}
            </button>
          )
        })}
      </div>

      {!business.bank.linked && (
        <div className="mt-6 flex flex-wrap items-center gap-3 rounded-2xl border border-sun/30 bg-sun-soft/60 px-5 py-3.5 text-sm">
          <Landmark className="size-4 text-sun" />
          <span className="flex-1">Connect checking so cover can be paid for and payouts can land.</span>
          <Button size="sm" onClick={() => link.mutate()} disabled={link.isPending}>
            {link.isPending ? 'Connecting…' : 'Connect checking'}
          </Button>
        </div>
      )}

      {(open.length > 0 || paid > 0) && (
        <Link
          to="/policies"
          className="group mt-6 flex items-center gap-3 rounded-2xl border border-good/25 bg-good-soft/70 px-5 py-3.5 text-sm transition hover:border-good/40"
        >
          <ShieldCheck className="size-4 text-good" />
          <span className="flex-1">
            {open.length > 0 ? (
              <>
                <strong>You’re covered.</strong> {open.length} {open.length === 1 ? 'plan' : 'plans'} watching, up to{' '}
                <span className="num">{money(open.reduce((sum, p) => sum + p.max_payout_cents, 0))}</span>.
              </>
            ) : (
              <strong>No open cover.</strong>
            )}
            {paid > 0 && <span className="text-ink-soft"> {money(paid)} paid out so far.</span>}
          </span>
          <ArrowRight className="size-4 text-good transition group-hover:translate-x-0.5" />
        </Link>
      )}

      <form onSubmit={submit} className="relative mt-6">
        <Search className="pointer-events-none absolute top-1/2 left-4 size-5 -translate-y-1/2 text-muted" />
        <Input
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          maxLength={300}
          placeholder="Worried about something else? Describe it in your own words."
          className="h-13 rounded-xl pr-24 pl-12 text-[15px]"
        />
        <Button type="submit" size="sm" className="absolute top-1/2 right-2.5 -translate-y-1/2" disabled={ask.isPending}>
          {ask.isPending ? 'Looking…' : 'Ask'}
        </Button>
      </form>

      {(ask.data || ask.error) && (
        <section className="mt-5 rounded-2xl border border-line bg-surface p-5">
          <div className="flex items-start gap-3">
            <p className="flex-1 text-sm text-ink-soft">{ask.data?.message}</p>
            <button
              onClick={() => {
                ask.reset()
                setQuestion('')
              }}
              className="rounded-lg p-1 text-muted hover:bg-ink/5 hover:text-ink"
              aria-label="Clear"
            >
              <X className="size-4" />
            </button>
          </div>
          <ErrorNote error={ask.error} />
          {ask.data && ask.data.cards.length > 0 && (
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {ask.data.cards.map((card) => (
                <ForecastCard key={card.id} card={card} onOpen={setSelected} />
              ))}
            </div>
          )}
        </section>
      )}

      <div className="mt-10">
        {forecast.isPending && <Loading label="Reading your forecast…" />}
        <ErrorNote error={forecast.error} />
        {forecast.data?.note && <p className="mb-6 rounded-xl border border-line bg-surface px-4 py-3 text-sm text-muted">{forecast.data.note}</p>}
        <Group title="This week" cards={soon} onOpen={setSelected} />
        <Group title="Coming up" cards={later} onOpen={setSelected} />
        {forecast.data && cards.length > 0 && (
          <p className="mt-8 text-center text-xs text-muted">
            {forecast.data.tailored ? `Picked and written for ${business.name} with Gemini. ` : ''}
            Chances and prices come straight from Kalshi.
          </p>
        )}
      </div>

      {selected && <ProtectSheet card={selected} badDay={business.bad_day_dollars} onClose={close} />}
    </div>
  )
}

function Group({ title, cards, onOpen }: { title: string; cards: PlanCard[]; onOpen: (card: PlanCard) => void }) {
  if (cards.length === 0) return null
  return (
    <section className="mb-10">
      <h2 className="mb-3 text-xs font-medium tracking-wide text-muted uppercase">{title}</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        {cards.map((card) => (
          <ForecastCard key={card.id} card={card} onOpen={onOpen} />
        ))}
      </div>
    </section>
  )
}

function ForecastCard({ card, onOpen }: { card: PlanCard; onOpen: (card: PlanCard) => void }) {
  return (
    <button onClick={() => onOpen(card)} className="group block h-full text-left">
      <Card className="flex h-full flex-col p-5 transition group-hover:border-line-strong group-hover:shadow-lift">
        <div className="flex items-center gap-2.5 text-xs text-muted">
          <TopicIcon topic={card.topic} className="size-8 rounded-lg" />
          <span className="flex-1">{TOPICS[card.topic].name}</span>
          <span>by {shortDate(card.closes_at)}</span>
        </div>
        <div className="font-display mt-3 text-xl leading-snug font-semibold tracking-tight">{card.title}</div>
        <p className="mt-1 text-sm leading-snug text-ink-soft">{card.why}</p>
        {card.warnings.length > 0 && (
          <p className="mt-2 flex items-start gap-1.5 text-xs text-sun">
            <AlertTriangle className="mt-px size-3.5 shrink-0" />
            <span className="line-clamp-2">{card.warnings[0]}</span>
          </p>
        )}
        <div className="mt-auto flex items-end justify-between pt-4">
          <div>
            <div className="num text-2xl font-semibold">{card.chance != null ? pct(card.chance) : '—'}</div>
            <div className="text-xs text-muted">chance this pays out</div>
          </div>
          <span className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-ink px-3.5 text-sm font-medium text-canvas transition group-hover:bg-ink-soft">
            Protect <ArrowRight className="size-3.5" />
          </span>
        </div>
      </Card>
    </button>
  )
}

function greeting() {
  const hour = new Date().getHours()
  if (hour < 12) return 'morning'
  if (hour < 18) return 'afternoon'
  return 'evening'
}
