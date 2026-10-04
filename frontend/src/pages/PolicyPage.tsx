import { useQuery } from '@tanstack/react-query'
import { ArrowDownLeft, ArrowLeft, ArrowUpRight, CheckCircle2, PartyPopper } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link, useLocation, useParams } from 'react-router'
import { api, type PolicyStatus, type S } from '@/api/client'
import { ErrorNote, Loading, StatusBadge, TopicIcon } from '@/components/domain'
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/card'
import { cn, dateTime, money } from '@/lib/format'
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

  if (policy.isPending) return <Loading />
  if (policy.isError) return <ErrorNote error={policy.error} />
  const p = policy.data
  const multi = p.legs.length > 1

  return (
    <div className="mx-auto max-w-3xl">
      <Link to="/policies" className="mb-6 inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink">
        <ArrowLeft className="size-4" /> Policies
      </Link>

      {justBound && p.status === 'ACTIVE' && (
        <Banner icon={<CheckCircle2 className="size-5 text-good" />}>
          <strong>You're covered.</strong> {money(p.premium_cents)} was charged. We'll watch the official result and pay you
          automatically.
        </Banner>
      )}
      {p.status === 'PAID' && (
        <Banner icon={<PartyPopper className="size-5 text-good" />}>
          <strong>{money(p.paid_cents)} was paid into your checking account.</strong> No claim needed.
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
              <div className="mb-0.5 text-xs font-semibold tracking-wide text-muted uppercase">The catch</div>
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
        </CardBody>
      </Card>

      <details className="mt-6 rounded-2xl border border-line bg-surface shadow-card">
        <summary className="flex cursor-pointer list-none items-center justify-between px-6 py-4 text-[15px] font-semibold">
          Under the hood
          <span className="text-xs font-normal text-muted">Exact terms, backing contracts, and history</span>
        </summary>
        <div className="space-y-5 border-t border-line px-6 py-5 text-sm">
          <p className="leading-relaxed text-ink-soft">{p.terms}</p>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="text-left text-xs text-muted uppercase">
                <tr>
                  <th className="pb-2 font-medium">Market</th>
                  <th className="pb-2 font-medium">Pays if</th>
                  <th className="pb-2 font-medium">Contracts</th>
                  <th className="pb-2 font-medium">Fill</th>
                  <th className="pb-2 font-medium">Result</th>
                </tr>
              </thead>
              <tbody className="num">
                {p.legs.map((leg) => (
                  <tr key={leg.ticker} className="border-t border-line">
                    <td className="py-2 pr-3">
                      <div className="font-sans">{leg.label}</div>
                      <div className="font-mono text-xs text-muted">{leg.ticker}</div>
                    </td>
                    <td className="py-2 uppercase">{leg.side}</td>
                    <td className="py-2">{leg.contracts.toLocaleString()}</td>
                    <td className="py-2">{leg.fill_price ? `${(Number(leg.fill_price) * 100).toFixed(1)}¢` : '—'}</td>
                    <td className="py-2 uppercase">{leg.result ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ol className="space-y-2 border-t border-line pt-4">
            {p.events.map((event, index) => (
              <li key={index} className="flex gap-3">
                <span className="w-32 shrink-0 text-xs text-muted">{dateTime(event.created_at)}</span>
                <span className="text-ink-soft">{event.message}</span>
              </li>
            ))}
          </ol>
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
