import { useQuery } from '@tanstack/react-query'
import { ArrowDownLeft, ArrowLeft, ArrowUpRight, CheckCircle2, CircleDashed, PartyPopper, RotateCcw, XCircle } from 'lucide-react'
import { Link, useLocation, useParams } from 'react-router'
import { api, type S } from '@/api/client'
import { BasisRiskBadge, CategoryIcon, ErrorNote, Loading, SideBadge, Stat, StatusBadge } from '@/components/domain'
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/card'
import { cn, dateTime, money } from '@/lib/format'
import { OPEN_STATUSES } from '@/lib/status'

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

  return (
    <>
      <Link to="/policies" className="mb-6 inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink">
        <ArrowLeft className="size-4" /> Policies
      </Link>

      {justBound && p.status === 'ACTIVE' && (
        <div className="mb-6 flex items-center gap-3 rounded-2xl border border-good/25 bg-good-soft px-5 py-4 text-sm">
          <CheckCircle2 className="size-5 text-good" />
          <span>
            <strong>You're covered.</strong> Premium of {money(p.premium_cents)} was charged and the cover is active. We'll
            watch the official result and pay you automatically.
          </span>
        </div>
      )}
      {p.status === 'PAID' && (
        <div className="mb-6 flex items-center gap-3 rounded-2xl border border-good/25 bg-good-soft px-5 py-4 text-sm">
          <PartyPopper className="size-5 text-good" />
          <span>
            <strong>{money(p.paid_cents)} was paid into your checking account.</strong> No claim needed.
          </span>
        </div>
      )}

      <div className="flex flex-wrap items-start gap-5">
        <CategoryIcon category={p.category} className="size-14 rounded-2xl" />
        <div className="flex-1">
          <h1 className="font-display text-3xl font-semibold tracking-tight">{p.title}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-muted">
            <StatusBadge status={p.status} />
            <span>Policy #{p.id}</span>
            <span>·</span>
            <span>{p.category}</span>
            <span>·</span>
            <span>Bought {dateTime(p.created_at)}</span>
          </div>
        </div>
      </div>

      <Card className="mt-8 grid grid-cols-2 gap-6 p-6 md:grid-cols-4">
        <Stat label={p.legs.length > 1 ? 'Payout per outcome' : 'Payout'} value={money(p.payout_each_cents)} />
        <Stat label="Maximum payout" value={money(p.max_payout_cents)} />
        <Stat label="Premium" value={money(p.premium_cents)} />
        <Stat label="Paid to you" value={<span className={p.paid_cents > 0 ? 'text-good' : ''}>{money(p.paid_cents)}</span>} />
      </Card>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_360px]">
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>What's covered</CardTitle>
              {p.basis_risk && <BasisRiskBadge risk={p.basis_risk} />}
            </CardHeader>
            <CardBody>
              <p className="leading-relaxed text-ink-soft">{p.terms}</p>
              <ul className="mt-5 divide-y divide-line rounded-xl border border-line">
                {p.legs.map((leg) => (
                  <li key={leg.ticker} className="flex flex-wrap items-center gap-3 px-4 py-3 text-sm">
                    <LegResult leg={leg} />
                    <span className="min-w-0 flex-1 font-medium">{leg.label}</span>
                    <SideBadge side={leg.side} />
                    <span className="text-muted">{legStatus(leg)}</span>
                  </li>
                ))}
              </ul>
            </CardBody>
          </Card>

          <Card>
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

          <details className="group rounded-2xl border border-line bg-surface shadow-card">
            <summary className="flex cursor-pointer list-none items-center justify-between px-6 py-4 text-[15px] font-semibold">
              Under the hood
              <span className="text-xs font-normal text-muted">Market contracts backing this policy</span>
            </summary>
            <div className="overflow-x-auto border-t border-line px-6 py-4">
              <table className="w-full text-sm">
                <thead className="text-left text-xs text-muted uppercase">
                  <tr>
                    <th className="pb-2 font-medium">Market</th>
                    <th className="pb-2 font-medium">Contracts</th>
                    <th className="pb-2 font-medium">Fill price</th>
                    <th className="pb-2 font-medium">Cost</th>
                    <th className="pb-2 font-medium">Closes</th>
                  </tr>
                </thead>
                <tbody className="num">
                  {p.legs.map((leg) => (
                    <tr key={leg.ticker} className="border-t border-line">
                      <td className="py-2 font-mono text-xs">{leg.ticker}</td>
                      <td className="py-2">{leg.contracts.toLocaleString()}</td>
                      <td className="py-2">{leg.fill_price ? `${(Number(leg.fill_price) * 100).toFixed(1)}¢` : '—'}</td>
                      <td className="py-2">{money(leg.cost_cents)}</td>
                      <td className="py-2">{dateTime(leg.close_time)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </div>

        <Card className="self-start">
          <CardHeader>
            <CardTitle>Timeline</CardTitle>
          </CardHeader>
          <CardBody className="pt-4">
            <ol className="relative space-y-5 border-l border-line pl-5">
              {p.events.map((event, index) => (
                <li key={index} className="relative">
                  <span
                    className={cn(
                      'absolute top-1 -left-[25px] size-2.5 rounded-full ring-4 ring-surface',
                      index === p.events.length - 1 ? 'bg-brand' : 'bg-line-strong',
                    )}
                  />
                  <div className="text-sm text-ink">{event.message}</div>
                  <div className="mt-0.5 text-xs text-muted">{dateTime(event.created_at)}</div>
                </li>
              ))}
            </ol>
          </CardBody>
        </Card>
      </div>
    </>
  )
}

function LegResult({ leg }: { leg: S['PolicyLeg'] }) {
  if (leg.result === 'void') return <RotateCcw className="size-4 text-sun" />
  if (leg.result === leg.side) return <CheckCircle2 className="size-4 text-good" />
  if (leg.result) return <XCircle className="size-4 text-muted" />
  return <CircleDashed className="size-4 text-muted" />
}

function legStatus(leg: S['PolicyLeg']) {
  if (leg.result === 'void') return 'Market voided'
  if (leg.result === leg.side) return `Settled ${leg.result.toUpperCase()} · pays out`
  if (leg.result) return `Settled ${leg.result.toUpperCase()} · no payout`
  if (new Date(leg.close_time).getTime() < Date.now()) return 'Waiting for official result'
  return `Watching until ${dateTime(leg.close_time)}`
}

const MOVEMENT_LABEL: Record<S['MoneyMovement']['kind'], string> = {
  premium: 'Premium charged',
  refund: 'Premium refunded',
  payout: 'Payout sent',
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
