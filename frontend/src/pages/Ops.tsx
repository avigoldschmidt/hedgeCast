import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Play } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { api, type S } from '@/api/client'
import { ErrorNote, Loading, Stat, StatusBadge, TopicIcon } from '@/components/domain'
import { Logo } from '@/components/Logo'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/card'
import { dateTime, money, shortDate, timeAgo } from '@/lib/format'

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

  return (
    <div className="min-h-screen bg-[#eeede8]">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-4 px-6">
          <Logo />
          <Badge tone="sun">Risk desk · internal</Badge>
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
            <Card className="grid grid-cols-2 gap-6 p-6 md:grid-cols-4">
              <Stat
                label="Hedge mode"
                value={<span className="capitalize">{ops.data.hedge_mode}</span>}
                sub={ops.data.hedge_mode === 'paper' ? 'Fills simulated against live books' : 'Orders sent to Kalshi'}
              />
              <Stat label="Market data" value={<span className="text-base">{ops.data.data_source}</span>} />
              <Stat
                label="Claim reserve"
                value={ops.data.reserve_balance_cents != null ? money(ops.data.reserve_balance_cents) : '—'}
                sub={ops.data.reserve_error ?? 'Funds payouts to customers (not their checking).'}
              />
              <Stat
                label="Settlement worker"
                value={<span className="text-base">{ops.data.worker.enabled ? 'Running' : 'Off'}</span>}
                sub={
                  ops.data.worker.last_run_at
                    ? `Last run ${timeAgo(ops.data.worker.last_run_at)} · ${ops.data.worker.last_result ?? ''}`
                    : 'Not run yet'
                }
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
                  Demo resolve sets the market result. Customer is paid only if that matches the side they bought.
                  Weather rain cover is YES — click “It happened” to pay.
                </span>
              </CardHeader>
              <CardBody className="overflow-x-auto pt-3">
                {ops.data.policies.length === 0 ? (
                  <p className="py-8 text-center text-sm text-muted">No policies on the book.</p>
                ) : (
                  <table className="w-full text-sm">
                    <thead className="text-left text-xs text-muted uppercase">
                      <tr>
                        <th className="pb-3 font-medium">Policy</th>
                        <th className="pb-3 font-medium">Business</th>
                        <th className="pb-3 font-medium">Pays if</th>
                        <th className="pb-3 font-medium">Settles by</th>
                        <th className="pb-3 text-right font-medium">Premium</th>
                        <th className="pb-3 text-right font-medium">Max payout</th>
                        <th className="pb-3 font-medium">Status</th>
                        <th className="pb-3 font-medium" />
                      </tr>
                    </thead>
                    <tbody>
                      {ops.data.policies.map((policy) => {
                        const open = policy.status === 'ACTIVE' || policy.status === 'AWAITING_RESULT'
                        return (
                          <tr key={policy.id} className="border-t border-line align-middle">
                            <td className="py-3">
                              <div className="flex items-center gap-3">
                                <TopicIcon topic={policy.topic} className="size-8 rounded-lg" />
                                <div>
                                  <div className="font-medium">#{policy.id} · {policy.title}</div>
                                  <div className="text-xs text-muted">
                                    {dateTime(policy.created_at)}
                                    {policy.simulated && ' · simulated fill'}
                                  </div>
                                </div>
                              </div>
                            </td>
                            <td className="py-3">{policy.business_name}</td>
                            <td className="py-3 text-muted">{paysIfLabel(policy.covered_side)}</td>
                            <td className="py-3 text-muted">{shortDate(policy.closes_at)}</td>
                            <td className="num py-3 text-right">{money(policy.premium_cents)}</td>
                            <td className="num py-3 text-right">{money(policy.max_payout_cents)}</td>
                            <td className="py-3">
                              <StatusBadge status={policy.status} />
                            </td>
                            <td className="py-3 text-right whitespace-nowrap">
                              {open && (
                                <span className="inline-flex flex-col items-end gap-1">
                                  <span className="inline-flex gap-1.5">
                                    <Button
                                      size="sm"
                                      variant="good"
                                      disabled={resolve.isPending}
                                      title={resolveHint(policy, 'yes')}
                                      onClick={() => resolve.mutate({ id: policy.id, result: 'yes' })}
                                    >
                                      It happened (YES)
                                    </Button>
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      disabled={resolve.isPending}
                                      title={resolveHint(policy, 'no')}
                                      onClick={() => resolve.mutate({ id: policy.id, result: 'no' })}
                                    >
                                      It didn’t (NO)
                                    </Button>
                                  </span>
                                  <span className="text-[11px] text-muted">
                                    YES → {resolveHint(policy, 'yes')} · NO → {resolveHint(policy, 'no')}
                                  </span>
                                </span>
                              )}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                )}
              </CardBody>
            </Card>
          </>
        )}
      </main>
    </div>
  )
}
