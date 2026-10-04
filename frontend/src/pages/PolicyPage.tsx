import { useQuery } from '@tanstack/react-query'
import { ArrowDownLeft, ArrowLeft, ArrowUpRight, CheckCircle2, ChevronDown, PartyPopper } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link, useLocation, useParams } from 'react-router'
import { api, type PolicyStatus, type S } from '@/api/client'
import { ErrorNote, Loading, StatusBadge, TopicIcon } from '@/components/domain'
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/card'
import { cn, contractCents, dateTime, money } from '@/lib/format'
import { OPEN_STATUSES } from '@/lib/status'

const REACHED: Record<PolicyStatus, number> = {
  PENDING: 0,
  ACTIVE: 1,
  AWAITING_RESULT: 2,
  NEEDS_REVIEW: 2,
  PAID: 3,
  EXPIRED: 3,
  REFUNDED: 3,
}

const FINAL: Partial<Record<PolicyStatus, string>> = {
  PAID: 'Paid into checking',
  EXPIRED: "Didn't happen · no payout",
  REFUNDED: 'Premium refunded',
}

export function PolicyPage() {
  const { id } = useParams()
  const location = useLocation()
  const justBound = Boolean((location.state as { justBound?: boolean } | null)?.justBound)
  const policy = useQuery({
    queryKey: ['policy', Number(id)],
    queryFn: () => api.policy(Number(id)),
    refetchInterval: (query) => (query.state.data && !OPEN_STATUSES.includes(query.state.data.status) ? false : 5000),
  })
  const me = useQuery({
    queryKey: ['me'],
    queryFn: api.me,
    enabled: Boolean(policy.data && (policy.data.status === 'PAID' || (justBound && policy.data.status === 'ACTIVE'))),
    refetchOnWindowFocus: true,
  })

  if (policy.isPending) return <Loading />
  if (policy.isError) return <ErrorNote error={policy.error} />
  const p = policy.data
  const multi = p.legs.length > 1
  const checkingCents = me.data?.bank.balance_cents ?? null
  const checking = checkingCents != null ? money(checkingCents) : null

  return (
    <div className="mx-auto max-w-3xl">
      <Link to="/policies" className="mb-6 inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink">
        <ArrowLeft className="size-4" /> Policies
      </Link>

      {justBound && p.status === 'ACTIVE' && (
        <Banner icon={<CheckCircle2 className="size-5 text-good" />}>
          <strong>You're covered.</strong>{' '}
          <span className="num">−{money(p.premium_cents)}</span> left checking.
          {checking && (
            <>
              {' '}
              Balance is now <span className="num font-semibold">{checking}</span>.
            </>
          )}{' '}
          We'll watch the official result and pay you automatically — no claim form.
        </Banner>
      )}
      {p.status === 'PAID' && (
        <Banner icon={<PartyPopper className="size-5 text-good" />}>
          <strong>
            <span className="num">+{money(p.paid_cents)}</span> paid into checking.
          </strong>{' '}
          No claim needed.
          {checking && (
            <>
              {' '}
              Balance is now <span className="num font-semibold">{checking}</span>.
            </>
          )}
        </Banner>
      )}

      <div className="flex items-start gap-4">
        <TopicIcon topic={p.topic} className="size-12 rounded-2xl" />
        <div className="flex-1">
          <h1 className="font-display text-3xl leading-tight font-semibold tracking-tight">{p.title}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-muted">
            <StatusBadge status={p.status} />
            <span>
              Policy #{p.id} · bought {dateTime(p.created_at)}
            </span>
          </div>
        </div>
      </div>

      <Card className="mt-8">
        <CardBody>
          <div className="grid grid-cols-3 gap-4">
            <Figure label={multi ? 'Pays per outcome' : 'Pays'} value={money(p.payout_each_cents)} />
            <Figure label="You paid" value={money(p.premium_cents)} />
            <Figure label="Paid to you" value={<span className={p.paid_cents > 0 ? 'text-good' : ''}>{money(p.paid_cents)}</span>} />
          </div>
          {p.why && <p className="mt-5 leading-relaxed text-ink-soft">{p.why}</p>}
          {p.catch && (
            <div className="mt-4 rounded-xl bg-canvas px-4 py-3 text-sm leading-relaxed text-ink-soft">
              <div className="mb-0.5 text-xs font-semibold tracking-wide text-muted uppercase">What this covers</div>
              {p.catch}
            </div>
          )}
          <Progress policy={p} />
        </CardBody>
      </Card>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Money</CardTitle>
        </CardHeader>
        <CardBody className="pt-3">
          {p.movements.length === 0 ? (
            <p className="text-sm text-muted">No money has moved yet.</p>
          ) : (
            <ul className="divide-y divide-line">
              {p.movements.map((movement, index) => (
                <Movement key={index} movement={movement} />
              ))}
            </ul>
          )}
          {checking && (
            <p className="mt-4 text-sm text-muted">
              Checking balance after payout: <span className="num font-medium text-ink">{checking}</span>
            </p>
          )}
        </CardBody>
      </Card>

      <details className="group mt-6 rounded-2xl border border-line bg-surface shadow-card">
        <summary className="flex cursor-pointer list-none items-center gap-4 px-6 py-5 [&::-webkit-details-marker]:hidden">
          <div className="min-w-0 flex-1">
            <div className="text-[15px] font-semibold">Under the hood</div>
            <p className="mt-0.5 text-sm text-muted">Exact terms, backing contracts, and history</p>
          </div>
          <ChevronDown className="size-4 shrink-0 text-muted transition group-open:rotate-180" />
        </summary>
        <div className="space-y-6 border-t border-line px-6 py-5 text-sm">
          <p className="leading-relaxed text-ink-soft">{p.terms}</p>

          <div>
            <div className="mb-2.5 text-xs font-semibold tracking-wide text-muted uppercase">
              Backing {multi ? 'contracts' : 'contract'}
            </div>
            <ul className="space-y-3">
              {p.legs.map((leg) => (
                <li key={leg.ticker} className="rounded-xl bg-canvas px-4 py-3.5">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="font-medium text-ink">{leg.label}</div>
                      <div className="mt-0.5 font-mono text-xs text-muted">{leg.ticker}</div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      <span className="rounded-md bg-surface px-2 py-0.5 font-medium uppercase text-ink-soft">
                        {leg.side}
                      </span>
                      {leg.result && (
                        <span className="rounded-md bg-surface px-2 py-0.5 font-medium uppercase text-ink-soft">
                          {leg.result}
                        </span>
                      )}
                      {leg.simulated && leg.order_id && (
                        <span className="rounded-md bg-sky-soft px-2 py-0.5 font-medium text-sky">Paper · live book</span>
                      )}
                    </div>
                  </div>
                  <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2.5 sm:grid-cols-4">
                    <HoodField label="Contracts" value={leg.contracts.toLocaleString()} />
                    <HoodField label="Limit" value={contractCents(leg.limit_price)} />
                    <HoodField label="Fill" value={contractCents(leg.fill_price)} />
                    <HoodField label="Fee" value={leg.fee_cents ? money(leg.fee_cents) : '—'} />
                    <HoodField
                      label="Order"
                      value={<span className="font-mono text-xs">{leg.order_id ?? '—'}</span>}
                      className="col-span-2 sm:col-span-4"
                    />
                  </div>
                </li>
              ))}
            </ul>
          </div>

          {p.events.length > 0 && (
            <div>
              <div className="mb-2.5 text-xs font-semibold tracking-wide text-muted uppercase">History</div>
              <ol className="space-y-3">
                {p.events.map((event, index) => (
                  <li key={index} className="flex gap-3">
                    <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-line-strong" />
                    <div className="min-w-0">
                      <div className="text-ink-soft">{event.message}</div>
                      <div className="mt-0.5 text-xs text-muted">{dateTime(event.created_at)}</div>
                    </div>
                  </li>
                ))}
              </ol>
            </div>
          )}
        </div>
      </details>
    </div>
  )
}

function Progress({ policy }: { policy: S['PolicyDetail'] }) {
  const reached = REACHED[policy.status]
  const steps = [
    { label: 'Watching', sub: `Until ${dateTime(policy.closes_at)}` },
    { label: 'Official result', sub: policy.status === 'NEEDS_REVIEW' ? 'Our risk desk is checking it' : 'From Kalshi' },
    { label: FINAL[policy.status] ?? 'Paid if it goes your way', sub: 'Straight to checking' },
  ]
  return (
    <ol className="mt-6 grid grid-cols-3 gap-3 border-t border-line pt-5">
      {steps.map((step, index) => {
        const lit = index < reached
        const current = lit && index === reached - 1 && reached < 3
        return (
          <li key={step.label}>
            <div className={cn('h-1.5 rounded-full', lit ? (current ? 'bg-brand' : 'bg-good') : 'bg-ink/5')} />
            <div className={cn('mt-2.5 text-sm font-medium', lit ? 'text-ink' : 'text-muted')}>{step.label}</div>
            <div className="text-xs text-muted">{step.sub}</div>
          </li>
        )
      })}
    </ol>
  )
}

function Figure({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <div className="text-xs text-muted">{label}</div>
      <div className="num mt-0.5 text-xl font-semibold">{value}</div>
    </div>
  )
}

function HoodField({ label, value, className }: { label: string; value: ReactNode; className?: string }) {
  return (
    <div className={className}>
      <div className="text-[11px] text-muted">{label}</div>
      <div className="num mt-0.5 text-ink">{value}</div>
    </div>
  )
}

function Banner({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <div className="mb-6 flex items-center gap-3 rounded-2xl border border-good/25 bg-good-soft px-5 py-4 text-sm">
      {icon}
      <span>{children}</span>
    </div>
  )
}

const MOVEMENT_LABEL: Record<S['MoneyMovement']['kind'], string> = {
  premium: 'Cover paid',
  refund: 'Refund',
  payout: 'Payout',
}

function Movement({ movement }: { movement: S['MoneyMovement'] }) {
  const incoming = movement.kind !== 'premium'
  return (
    <li className="flex items-center gap-3 py-3 text-sm">
      <span
        className={cn(
          'inline-flex size-8 items-center justify-center rounded-lg',
          incoming ? 'bg-good-soft text-good' : 'bg-ink/5 text-ink-soft',
        )}
      >
        {incoming ? <ArrowDownLeft className="size-4" /> : <ArrowUpRight className="size-4" />}
      </span>
      <span className="flex-1">
        <span className="block font-medium">{MOVEMENT_LABEL[movement.kind]}</span>
        <span className="block text-xs text-muted">
          {dateTime(movement.created_at)}
          {movement.status !== 'done' && ` · ${movement.status}`}
        </span>
      </span>
      <span className={cn('num font-semibold', incoming && 'text-good')}>
        {incoming ? '+' : '−'}
        {money(movement.amount_cents)}
      </span>
    </li>
  )
}
