import { useQuery } from '@tanstack/react-query'
import { Search } from 'lucide-react'
import { useState } from 'react'
import { api, type PlanCard, type Side } from '@/api/client'
import type { BuilderSelection } from '@/components/builder/types'
import { ErrorNote, Loading } from '@/components/domain'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/field'
import { Section } from '@/components/quote'
import { cn, pct, shortDate } from '@/lib/format'
import { useDebounced } from '@/lib/useDebounced'

export function OtherNarrow({ onContinue }: { onContinue: (selection: BuilderSelection) => void }) {
  const [query, setQuery] = useState('')
  const debounced = useDebounced(query.trim(), 300)
  const searching = debounced.length >= 2
  const [cardId, setCardId] = useState<string | null>(null)
  const [ticker, setTicker] = useState<string | null>(null)
  const [side, setSide] = useState<Side>('yes')

  const search = useQuery({
    queryKey: ['search', debounced],
    queryFn: () => api.search(debounced),
    enabled: searching,
  })

  const cards = search.data?.cards ?? []
  const card: PlanCard | undefined = cards.find((item) => item.id === cardId) ?? cards[0]
  const choice = card?.choices.find((item) => item.ticker === ticker) ?? card?.choices[0]

  function continueWithPick() {
    if (!card || !choice) return
    const title = ticker === card.ticker || !ticker ? card.title : `${card.group_title} · ${choice.label}`
    onContinue({
      topic: card.topic,
      title,
      why: card.why,
      catch: card.catch,
      legs: [{ ticker: choice.ticker, side }],
    })
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display text-[34px] leading-tight font-semibold tracking-tight">Something else</h1>
        <p className="mt-2 text-muted">Search any open Kalshi event you want cover for.</p>
      </div>

      <div className="relative">
        <Search className="pointer-events-none absolute top-1/2 left-4 size-5 -translate-y-1/2 text-muted" />
        <Input
          value={query}
          onChange={(event) => {
            setQuery(event.target.value)
            setCardId(null)
            setTicker(null)
          }}
          maxLength={120}
          placeholder="Election, crypto, awards…"
          className="h-13 rounded-xl pl-12 text-[15px]"
          autoFocus
        />
      </div>

      {searching && search.isFetching && <Loading label="Finding cover…" />}
      <ErrorNote error={search.error} />
      {searching && search.data?.message && !search.isFetching && (
        <p className="text-sm text-muted">{search.data.message}</p>
      )}

      {searching && cards.length > 0 && (
        <>
          <Section number={1} title="Which event">
            <div className="space-y-2">
              {cards.map((item) => {
                const active = (cardId ?? cards[0]?.id) === item.id
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => {
                      setCardId(item.id)
                      setTicker(item.ticker)
                    }}
                    className={cn(
                      'flex w-full items-start gap-3 rounded-xl border px-4 py-3 text-left transition',
                      active ? 'border-ink ring-1 ring-ink' : 'border-line hover:border-line-strong',
                    )}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="font-medium">{item.title}</div>
                      <div className="mt-0.5 text-xs text-muted">by {shortDate(item.closes_at)}</div>
                    </div>
                    <div className="num text-sm font-semibold">{item.chance != null ? pct(item.chance) : '—'}</div>
                  </button>
                )
              })}
            </div>
          </Section>

          {card && (
            <Section number={2} title="Which outcome">
              <div className="flex flex-wrap gap-2">
                {card.choices.map((item) => {
                  const active = (ticker ?? card.ticker) === item.ticker
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
                    </button>
                  )
                })}
              </div>
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
          </Section>

          <Button type="button" size="lg" disabled={!choice} onClick={continueWithPick}>
            Continue
          </Button>
        </>
      )}

      {searching && !search.isFetching && cards.length === 0 && search.data && (
        <p className="text-sm text-muted">No open cover matched that. Try a shorter word.</p>
      )}
    </div>
  )
}
