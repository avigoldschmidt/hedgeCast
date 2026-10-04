import { useQuery } from '@tanstack/react-query'
import { ArrowUpRight } from 'lucide-react'
import { Link } from 'react-router'
import { api, type S } from '@/api/client'
import { ErrorNote, Loading, PageHeader, StatusBadge, TopicIcon } from '@/components/domain'
import { Card, CardBody } from '@/components/ui/card'
import { money, shortDate } from '@/lib/format'

export function Policies() {
  const policies = useQuery({ queryKey: ['policies'], queryFn: api.policies, refetchInterval: 15000 })

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader eyebrow="Your cover" title="Active and past plans" />
      {policies.isPending && <Loading />}
      <ErrorNote error={policies.error} />
      {policies.data && (
        <Card>
          <CardBody className="py-3">
            {policies.data.length === 0 ? (
              <div className="py-10 text-center text-sm text-muted">
                Nothing yet.{' '}
                <Link to="/" className="font-medium text-ink underline-offset-4 hover:underline">
                  Build a cover plan
                </Link>
                .
              </div>
            ) : (
              <ul className="divide-y divide-line">
                {policies.data.map((policy) => (
                  <PolicyRow key={policy.id} policy={policy} />
                ))}
              </ul>
            )}
          </CardBody>
        </Card>
      )}
    </div>
  )
}

function PolicyRow({ policy }: { policy: S['PolicySummary'] }) {
  return (
    <li>
      <Link to={`/policies/${policy.id}`} className="group -mx-2 flex items-center gap-4 rounded-xl px-2 py-3.5 transition hover:bg-canvas">
        <TopicIcon topic={policy.topic} />
        <div className="min-w-0 flex-1">
          <div className="truncate font-medium text-ink">{policy.title}</div>
          <div className="text-sm text-muted">Result by {shortDate(policy.closes_at)}</div>
        </div>
        <div className="hidden text-right sm:block">
          <div className="num font-semibold">{money(policy.status === 'PAID' ? policy.paid_cents : policy.max_payout_cents)}</div>
          <div className="text-xs text-muted">{policy.status === 'PAID' ? 'paid out' : 'pays up to'}</div>
        </div>
        <StatusBadge status={policy.status} />
        <ArrowUpRight className="size-4 text-muted opacity-0 transition group-hover:opacity-100" />
      </Link>
    </li>
  )
}
