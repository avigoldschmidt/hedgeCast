import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, ArrowUpRight, Landmark, Plus } from 'lucide-react'
import { Link } from 'react-router'
import { api, type S } from '@/api/client'
import { CategoryIcon, ErrorNote, Loading, PageHeader, Stat, StatusBadge } from '@/components/domain'
import { Button } from '@/components/ui/button'
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/card'
import { buttonVariants } from '@/components/ui/variants'
import { money, shortDate, timeAgo } from '@/lib/format'
import { OPEN_STATUSES } from '@/lib/status'

export function Dashboard() {
  const queryClient = useQueryClient()
  const dashboard = useQuery({ queryKey: ['dashboard'], queryFn: api.dashboard, refetchInterval: 15000 })
  const link = useMutation({
    mutationFn: api.linkBank,
    onSuccess: (data) => {
      queryClient.setQueryData(['me'], data)
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })

  if (dashboard.isPending) return <Loading />
  if (dashboard.isError) return <ErrorNote error={dashboard.error} />

  const { business, policies, activity } = dashboard.data
  const open = policies.filter((policy) => OPEN_STATUSES.includes(policy.status))
  const closed = policies.filter((policy) => !OPEN_STATUSES.includes(policy.status))

  return (
    <>
      <PageHeader eyebrow={`Good ${greeting()}`} title={business.name}>
        <Link to="/protect" className={buttonVariants({ size: 'lg' })}>
          <Plus className="size-4" /> Get protection
        </Link>
      </PageHeader>

      {!business.bank.linked && (
        <Card className="mb-6 flex flex-wrap items-center gap-4 border-sun/30 bg-sun-soft/60 p-5">
          <Landmark className="size-5 text-sun" />
          <div className="flex-1 text-sm">
            <div className="font-medium">Connect checking to buy cover</div>
            <div className="text-muted">Premiums come out of it and payouts go straight back in.</div>
          </div>
          <Button onClick={() => link.mutate()} disabled={link.isPending}>
            {link.isPending ? 'Connecting…' : 'Connect checking'}
          </Button>
          {link.error && (
            <div className="w-full">
              <ErrorNote error={link.error} />
            </div>
          )}
        </Card>
      )}

      <Card className="grid grid-cols-2 gap-6 p-6 md:grid-cols-4">
        <Stat
          label="Checking"
          value={business.bank.balance_cents != null ? money(business.bank.balance_cents) : '—'}
          sub={business.bank.linked ? `••${business.bank.account_mask}` : 'Not connected'}
        />
        <Stat label="Active protection" value={money(dashboard.data.active_coverage_cents)} sub={`${open.length} open ${open.length === 1 ? 'policy' : 'policies'}`} />
        <Stat label="Premiums paid" value={money(dashboard.data.premiums_paid_cents)} sub="All time" />
        <Stat label="Payouts received" value={<span className="text-good">{money(dashboard.data.payouts_received_cents)}</span>} sub="All time" />
      </Card>

      <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_340px]">
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Open protection</CardTitle>
              <Link to="/policies" className="text-sm text-muted hover:text-ink">
                All policies
              </Link>
            </CardHeader>
            <CardBody className="pt-3">
              {open.length === 0 ? (
                <EmptyCover />
              ) : (
                <ul className="divide-y divide-line">
                  {open.map((policy) => (
                    <PolicyRow key={policy.id} policy={policy} />
                  ))}
                </ul>
              )}
            </CardBody>
          </Card>
          {closed.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Recently closed</CardTitle>
              </CardHeader>
              <CardBody className="pt-3">
                <ul className="divide-y divide-line">
                  {closed.slice(0, 5).map((policy) => (
                    <PolicyRow key={policy.id} policy={policy} />
                  ))}
                </ul>
              </CardBody>
            </Card>
          )}
        </div>

        <Card className="self-start">
          <CardHeader>
            <CardTitle>Activity</CardTitle>
          </CardHeader>
          <CardBody className="pt-3">
            {activity.length === 0 ? (
              <p className="text-sm text-muted">Premiums, results, and payouts will show up here.</p>
            ) : (
              <ol className="space-y-4">
                {activity.slice(0, 8).map((item, index) => (
                  <li key={`${item.policy_id}-${index}`} className="flex gap-3">
                    <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-brand" />
                    <Link to={`/policies/${item.policy_id}`} className="group text-sm">
                      <span className="text-ink-soft group-hover:text-ink">{item.message}</span>
                      <span className="mt-0.5 block text-xs text-muted">{timeAgo(item.created_at)}</span>
                    </Link>
                  </li>
                ))}
              </ol>
            )}
          </CardBody>
        </Card>
      </div>
    </>
  )
}

export function PolicyRow({ policy }: { policy: S['PolicySummary'] }) {
  return (
    <li>
      <Link to={`/policies/${policy.id}`} className="group -mx-2 flex items-center gap-4 rounded-xl px-2 py-3.5 transition hover:bg-canvas">
        <CategoryIcon category={policy.category} />
        <div className="min-w-0 flex-1">
          <div className="truncate font-medium text-ink">{policy.title}</div>
          <div className="text-sm text-muted">
            {policy.category} · settles by {shortDate(policy.closes_at)}
          </div>
        </div>
        <div className="hidden text-right sm:block">
          <div className="num font-semibold">{money(policy.status === 'PAID' ? policy.paid_cents : policy.max_payout_cents)}</div>
          <div className="text-xs text-muted">{policy.status === 'PAID' ? 'paid out' : 'max payout'}</div>
        </div>
        <StatusBadge status={policy.status} />
        <ArrowUpRight className="size-4 text-muted opacity-0 transition group-hover:opacity-100" />
      </Link>
    </li>
  )
}

function EmptyCover() {
  return (
    <div className="flex flex-col items-center py-10 text-center">
      <div className="flex -space-x-2">
        <CategoryIcon category="Economics" className="ring-4 ring-surface" />
        <CategoryIcon category="Climate and Weather" className="ring-4 ring-surface" />
        <CategoryIcon category="Financials" className="ring-4 ring-surface" />
      </div>
      <div className="mt-4 font-medium">No open protection</div>
      <p className="mt-1 max-w-sm text-sm text-muted">
        A rate hike, a tariff, a gas spike, a rainy Saturday. Cover the event that would cost you money in about a minute.
      </p>
      <Link to="/protect" className={buttonVariants({ variant: 'outline', className: 'mt-5' })}>
        Find a market <ArrowRight className="size-4" />
      </Link>
    </div>
  )
}

function greeting() {
  const hour = new Date().getHours()
  if (hour < 12) return 'morning'
  if (hour < 18) return 'afternoon'
  return 'evening'
}
