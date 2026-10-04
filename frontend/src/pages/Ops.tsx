import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, ChevronDown, Play } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Link } from 'react-router'
import { api, type S } from '@/api/client'
import { ErrorNote, Loading, Stat, StatusBadge, TopicIcon } from '@/components/domain'
import { Logo } from '@/components/Logo'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/card'
import { cn, contractCents, dateTime, money, shortDate, timeAgo } from '@/lib/format'

type ResolveNote = { id: number; message: string; good: boolean }

function paysIfLabel(side: S['OpsPolicy']['covered_side']) {
  if (side === 'yes') return 'Pays if YES'
  if (side === 'no') return 'Pays if NO'
  return 'Mixed sides'
}

function resolveHint(policy: S['OpsPolicy'], result: 'yes' | 'no') {
  if (policy.covered_side === 'mixed') return 'May pay some legs'
  if (policy.covered_side === result) return `Pays ${money(policy.max_payout_cents)}`
  return 'Expires'
}

export function Ops() {
  const queryClient = useQueryClient()
  const ops = useQuery({ queryKey: ['ops'], queryFn: api.ops, refetchInterval: 10000 })
  const [note, setNote] = useState<ResolveNote | null>(null)
  const [openTickets, setOpenTickets] = useState<Record<number, boolean>>({})
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['ops'] })
    queryClient.invalidateQueries({ queryKey: ['policies'] })
    queryClient.invalidateQueries({ queryKey: ['policy'] })
    queryClient.invalidateQueries({ queryKey: ['me'] })
  }
  const settle = useMutation({ mutationFn: api.settle, onSuccess: refresh })
  const resolve = useMutation({
    mutationFn: ({ id, result }: { id: number; result: 'yes' | 'no' }) => api.resolve(id, { result }),
    onSuccess: (policy) => {
      if (policy.status === 'PAID') {
        setNote({ id: policy.id, message: `Paid ${money(policy.paid_cents)} to checking`, good: true })
      } else if (policy.status === 'EXPIRED') {
        setNote({ id: policy.id, message: 'Expired — no payout', good: false })
      } else {
        setNote({ id: policy.id, message: `Now ${policy.status.replace('_', ' ').toLowerCase()}`, good: false })
      }
      refresh()
    },
  })

  const paper = ops.data?.hedge_mode === 'paper'

  return (
    <div className="min-h-screen bg-[#eeede8]">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-4 px-6">
          <Logo />
          <Badge tone="sun">Settlement · internal</Badge>
          <Link to="/" className="ml-auto inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink">
            <ArrowLeft className="size-4" /> Customer app
          </Link>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-10">
        {ops.isPending && <Loading />}
        <ErrorNote error={ops.error} />
        {ops.data && (
          <>
            <Card className="grid grid-cols-2 gap-6 p-6 lg:grid-cols-5">
              <Stat
                label="Market books"
                value={<span className="text-base">Live Kalshi</span>}
                sub={ops.data.data_source}
              />
              <Stat
                label="Hedge mode"
                value={<span className="text-base capitalize">{ops.data.hedge_mode}</span>}
                sub={paper ? 'Walks the live production book' : 'Posts real Kalshi orders'}
              />
              <Stat
                label="Company float"
                value={ops.data.reserve_balance_cents != null ? money(ops.data.reserve_balance_cents) : '—'}
                sub={ops.data.reserve_error ?? 'Premiums in · payouts out'}
              />
              <Stat
                label="Settlement worker"
                value={<span className="text-base">{ops.data.worker.enabled ? 'Running' : 'Off'}</span>}
                sub={
                  ops.data.worker.last_run_at
                    ? `${timeAgo(ops.data.worker.last_run_at)} · ${ops.data.worker.last_result ?? ''}`
                    : 'Not run yet'
                }
              />
              <Stat
                label="Open on book"
                value={
                  <span className="num text-base">
                    {(ops.data.counts.ACTIVE ?? 0) + (ops.data.counts.AWAITING_RESULT ?? 0)}
                  </span>
                }
                sub="Waiting on a market result"
              />
            </Card>

            <div className="mt-4 flex flex-wrap items-center gap-2">
              {Object.entries(ops.data.counts).map(([status, count]) => (
                <Badge key={status}>
                  {status.replace('_', ' ').toLowerCase()} · {count}
                </Badge>
              ))}
              <Button variant="outline" size="sm" className="ml-auto" onClick={() => settle.mutate()} disabled={settle.isPending}>
                <Play className="size-3.5" /> {settle.isPending ? 'Running…' : 'Run settlement now'}
              </Button>
            </div>
            <div className="mt-3">
              <ErrorNote error={settle.error ?? resolve.error} />
              {note && (
                <p className={`mt-2 text-sm ${note.good ? 'text-good' : 'text-muted'}`}>
                  Policy #{note.id}: {note.message}
                </p>
              )}
            </div>

            <Card className="mt-4">
              <CardHeader>
                <CardTitle>Book</CardTitle>
                <span className="text-xs text-muted">
                  Settle YES/NO the way the worker does when Kalshi posts the result. Expand a row for the hedge ticket.
                </span>
              </CardHeader>
              <CardBody className="space-y-3 pt-3">
                {ops.data.policies.length === 0 ? (
                  <p className="py-8 text-center text-sm text-muted">No policies on the book.</p>
                ) : (
                  ops.data.policies.map((policy) => {
                    const open = policy.status === 'ACTIVE' || policy.status === 'AWAITING_RESULT'
                    const ticketsOpen = openTickets[policy.id] ?? false
                    const filled = policy.legs.some((leg) => leg.order_id)
                    return (
                      <div key={policy.id} className="rounded-xl border border-line">
                        <div className="flex flex-col gap-4 p-4 lg:flex-row lg:items-center lg:gap-6">
                          <button
                            type="button"
                            className="flex min-w-0 flex-1 items-start gap-3 text-left disabled:cursor-default"
                            onClick={() =>
                              filled && setOpenTickets((prev) => ({ ...prev, [policy.id]: !prev[policy.id] }))
                            }
                            disabled={!filled}
                          >
                            <TopicIcon topic={policy.topic} className="mt-0.5 size-9 shrink-0 rounded-lg" />
                            <div className="min-w-0">
                              <div className="flex flex-wrap items-center gap-2">
                                <span className="font-medium">
                                  #{policy.id} · {policy.title}
                                </span>
                                <StatusBadge status={policy.status} />
                                <Badge tone={policy.simulated ? 'sky' : 'good'}>
                                  {policy.simulated ? 'Paper' : 'Live'}
                                </Badge>
                                {filled && (
                                  <ChevronDown
                                    className={cn('size-3.5 text-muted transition', ticketsOpen && 'rotate-180')}
                                  />
                                )}
                              </div>
                              <p className="mt-1 text-xs text-muted">
                                {policy.business_name} · {paysIfLabel(policy.covered_side)} · settles{' '}
                                {shortDate(policy.closes_at)} · {dateTime(policy.created_at)}
                              </p>
                            </div>
                          </button>

                          <div className="flex shrink-0 items-center gap-6 lg:ml-auto">
                            <div className="text-right">
                              <div className="text-[11px] text-muted uppercase">Premium</div>
                              <div className="num text-sm font-medium">{money(policy.premium_cents)}</div>
                            </div>
                            <div className="text-right">
                              <div className="text-[11px] text-muted uppercase">Max payout</div>
                              <div className="num text-sm font-medium">{money(policy.max_payout_cents)}</div>
                            </div>
                            {open && (
                              <div className="flex gap-1.5">
                                <Button
                                  size="sm"
                                  variant="good"
                                  disabled={resolve.isPending}
                                  title={resolveHint(policy, 'yes')}
                                  onClick={() => resolve.mutate({ id: policy.id, result: 'yes' })}
                                >
                                  Settle YES
                                </Button>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  disabled={resolve.isPending}
                                  title={resolveHint(policy, 'no')}
                                  onClick={() => resolve.mutate({ id: policy.id, result: 'no' })}
                                >
                                  Settle NO
                                </Button>
                              </div>
                            )}
                          </div>
                        </div>

                        {ticketsOpen && filled && (
                          <div className="border-t border-line bg-[#f7f6f2] px-4 py-3">
                            <div className="mb-2 text-[11px] font-medium tracking-wide text-muted uppercase">
                              Hedge fill
                            </div>
                            <FillTickets legs={policy.legs} />
                          </div>
                        )}
                      </div>
                    )
                  })
                )}
              </CardBody>
            </Card>
          </>
        )}
      </main>
    </div>
  )
}

function FillTickets({ legs }: { legs: S['PolicyLeg'][] }) {
  return (
    <div className="space-y-3">
      {legs.map((leg) => (
        <div key={leg.ticker} className="flex flex-wrap gap-x-6 gap-y-2 text-xs">
          <TicketField label="Ticker" value={<span className="font-mono">{leg.ticker}</span>} />
          <TicketField label="Side" value={<span className="uppercase">{leg.side}</span>} />
          <TicketField label="Qty" value={<span className="num">{leg.contracts.toLocaleString()}</span>} />
          <TicketField label="Limit" value={<span className="num">{contractCents(leg.limit_price)}</span>} />
          <TicketField label="Avg fill" value={<span className="num">{contractCents(leg.fill_price)}</span>} />
          <TicketField label="Fee" value={<span className="num">{leg.fee_cents ? money(leg.fee_cents) : '—'}</span>} />
          <TicketField
            label="Order"
            value={
              <span className="font-mono">
                {leg.order_id ?? '—'}
                {leg.simulated && leg.order_id ? (
                  <span className="ml-1.5 font-sans text-muted">paper · live book</span>
                ) : null}
              </span>
            }
          />
        </div>
      ))}
    </div>
  )
}

function TicketField({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="min-w-[5.5rem]">
      <div className="text-muted">{label}</div>
      <div className="mt-0.5 text-ink">{value}</div>
    </div>
  )
}
