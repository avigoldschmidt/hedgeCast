import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Clock, Landmark, Lock, RefreshCw } from 'lucide-react'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router'
import { api, type S } from '@/api/client'
import { ErrorNote } from '@/components/domain'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/field'
import { cn, money, pct } from '@/lib/format'
import { useDebounced } from '@/lib/useDebounced'

export function Section({ number, title, children }: { number: number; title: string; children: ReactNode }) {
  return (
    <section>
      <h3 className="mb-3 flex items-center gap-2.5 text-[15px] font-semibold">
        <span className="inline-flex size-6 items-center justify-center rounded-full bg-ink text-xs text-canvas">{number}</span>
        {title}
      </h3>
      {children}
    </section>
  )
}

/** Cap presets so sandbox checking (~$1,000) can still fund a typical premium. */
const PRESET_CAP_DOLLARS = 800

function presetsFor(badDay: number) {
  const round = (value: number) => Math.max(10, Math.round(value / 50) * 50)
  const raw = [round(badDay / 2), round(badDay), round(badDay * 2)].map((value) => Math.min(value, PRESET_CAP_DOLLARS))
  return [...new Set(raw)]
}

export function PayoutPicker({ value, onChange, badDay }: { value: number; onChange: (value: number) => void; badDay: number }) {
  const presets = presetsFor(badDay)
  return (
    <div>
      <div className="relative">
        <span className="absolute top-1/2 left-4 -translate-y-1/2 text-xl text-muted">$</span>
        <Input
          aria-label="Payout"
          type="number"
          inputMode="numeric"
          min={1}
          step={1}
          value={value}
          onChange={(event) => onChange(Math.max(0, Math.floor(Number(event.target.value) || 0)))}
          className="num h-14 pl-9 text-2xl font-semibold"
        />
      </div>
      <div className="mt-2.5 flex flex-wrap gap-2">
        {presets.map((preset) => (
          <button
            key={preset}
            type="button"
            onClick={() => onChange(preset)}
            className={cn(
              'num h-9 rounded-lg border px-3 text-sm font-medium transition',
              value === preset ? 'border-ink bg-ink text-canvas' : 'border-line-strong bg-surface hover:bg-canvas',
            )}
          >
            {money(preset * 100)}
          </button>
        ))}
      </div>
    </div>
  )
}

/** Live quote for `request` (null until the user has picked something), plus the buy button. */
export function QuoteCheckout({ request, onPayout }: { request: S['QuoteRequest'] | null; onPayout: (dollars: number) => void }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [allOrNothing, setAllOrNothing] = useState(false)
  const me = useQuery({ queryKey: ['me'], queryFn: api.me })
  const quote = useLiveQuote(request)
  const bind = useMutation({
    mutationFn: api.bind,
    onSuccess: (policy) => {
      queryClient.invalidateQueries({ queryKey: ['policies'] })
      queryClient.invalidateQueries({ queryKey: ['me'] })
      navigate(`/policies/${policy.id}`, { state: { justBound: true } })
    },
  })

  const link = useMutation({
    mutationFn: api.linkBank,
    onSuccess: (data) => queryClient.setQueryData(['me'], data),
  })

  const q = quote.data
  const bankLinked = me.data?.bank.linked ?? false
  const secondsLeft = useSecondsLeft(q?.expires_at)
  const expired = q !== null && secondsLeft === 0
  const short = q?.thin_book.short ?? false
  const canBuy = q !== null && !expired && bankLinked && !bind.isPending && (!short || allOrNothing)

  if (!request) return <p className="text-sm text-muted">Pick an outcome and payout to see a price.</p>
  if (quote.error != null) {
    return (
      <div className="space-y-3">
        <ErrorNote error={quote.error} />
        <Button variant="outline" size="sm" onClick={quote.refresh}>
          <RefreshCw className="size-3.5" /> Try again
        </Button>
      </div>
    )
  }
  if (!q) {
    return (
      <div className="space-y-3">
        <div className="h-10 w-32 animate-pulse rounded-lg bg-ink/5" />
        <div className="h-16 animate-pulse rounded-lg bg-ink/5" />
      </div>
    )
  }

  const leg = q.legs[0]
  const feeTotal =
    q.breakdown.exchange_fee_cents + q.breakdown.buffer_cents + q.breakdown.platform_fee_cents + q.breakdown.rounding_cents

  return (
    <div className={cn('transition-opacity', (expired || quote.loading) && 'opacity-50')}>
      <div className="flex items-baseline justify-between gap-3">
        <div className="flex items-baseline gap-2">
          <span className="num font-display text-4xl font-semibold tracking-tight">{money(q.premium_cents)}</span>
          <span className="text-sm text-muted">one time</span>
        </div>
        {expired ? (
          <button onClick={quote.refresh} className="inline-flex items-center gap-1.5 text-xs font-medium text-sun hover:underline">
            <Clock className="size-3" /> Price expired · refresh
          </button>
        ) : (
          <span className="num inline-flex items-center gap-1.5 text-xs font-medium text-brand">
            <Lock className="size-3" /> Price holds · {secondsLeft}s
          </span>
        )}
      </div>
      <p className="mt-1 text-sm text-ink-soft">
        Pays <strong className="num">{money(q.payout_each_cents)}</strong> into checking if {leg.side === 'yes' ? 'it happens' : "it doesn't happen"}.
        Market chance <strong className="num">{pct(leg.implied_probability)}</strong>
        {feeTotal > 0 && (
          <>
            {' '}
            · includes <span className="num">{money(feeTotal)}</span> in fees
          </>
        )}
        .
      </p>

      {q.catch && <p className="mt-3 text-sm leading-relaxed text-ink-soft">{q.catch}</p>}

      {q.warnings.map((warning) => (
        <Warning key={warning}>{warning}</Warning>
      ))}

      {short && (
        <ThinBookPanel
          quote={q}
          payout={request.payout_dollars}
          allOrNothing={allOrNothing}
          onAllOrNothing={setAllOrNothing}
          onTakeAvailable={onPayout}
        />
      )}

      {!bankLinked && (
        <div className="mt-4 rounded-xl border border-line bg-canvas px-4 py-4">
          <div className="flex items-start gap-3">
            <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-lg bg-brand-soft text-brand">
              <Landmark className="size-4" />
            </span>
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium">Link checking to protect</div>
              <p className="mt-0.5 text-xs text-muted">Cover is paid from this account and payouts land back in it.</p>
              <ErrorNote error={link.error} />
              <Button size="sm" className="mt-3" onClick={() => link.mutate()} disabled={link.isPending}>
                {link.isPending ? 'Connecting…' : 'Connect checking'}
              </Button>
            </div>
          </div>
        </div>
      )}

      <ErrorNote error={bind.error} />
      <Button
        size="lg"
        className="mt-4 w-full"
        disabled={!canBuy}
        onClick={() => bind.mutate({ quote_id: q.id, all_or_nothing: allOrNothing })}
      >
        {bind.isPending ? 'Setting up your cover…' : `Protect for ${money(q.premium_cents)}`}
      </Button>
      <p className="mt-2 text-center text-xs text-muted">
        {bankLinked
          ? me.data?.bank.balance_cents != null
            ? `Checking ••${me.data.bank.account_mask} · ${money(me.data.bank.balance_cents)}. Premium comes out of this balance; payouts land back here.`
            : `Charged to checking ••${me.data?.bank.account_mask}. Payouts go back automatically.`
          : 'Connect checking above to protect.'}
      </p>
    </div>
  )
}

export function Warning({ children }: { children: ReactNode }) {
  return (
    <div className="mt-3 flex gap-2 rounded-xl border border-sun/30 bg-sun-soft px-4 py-3 text-sm text-ink-soft">
      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-sun" />
      {children}
    </div>
  )
}

function useLiveQuote(request: S['QuoteRequest'] | null) {
  const key = JSON.stringify(request)
  const debouncedKey = useDebounced(key, 450)
  const debounced = useMemo(() => JSON.parse(debouncedKey) as S['QuoteRequest'] | null, [debouncedKey])
  const query = useQuery({
    queryKey: ['quote', debouncedKey],
    queryFn: () => api.quote(debounced as S['QuoteRequest']),
    enabled: debounced !== null && debounced.payout_dollars >= 1,
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
    <div className="mt-3 rounded-xl border border-sun/40 bg-sun-soft/70 p-4 text-sm">
      <div className="flex items-center gap-2 font-semibold">
        <AlertTriangle className="size-4 text-sun" /> The market is thin right now
      </div>
      <p className="mt-1 text-ink-soft">
        {available > 0
          ? `There's only enough on offer to cover ${money(available * 100)}, not ${money(payout * 100)}.`
          : 'Nobody is offering this cover at a sensible price right now.'}
      </p>
      <div className="mt-3 space-y-2">
        {available > 0 && (
          <button
            onClick={() => onTakeAvailable(available)}
            className="w-full rounded-lg border border-line-strong bg-surface px-3 py-2 text-left font-medium hover:bg-canvas"
          >
            Cover {money(available * 100)} instead
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
