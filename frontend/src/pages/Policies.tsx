import { useQuery } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { Link } from 'react-router'
import { api } from '@/api/client'
import { ErrorNote, Loading, PageHeader } from '@/components/domain'
import { buttonVariants } from '@/components/ui/variants'
import { Card, CardBody } from '@/components/ui/card'
import { PolicyRow } from '@/pages/Dashboard'

export function Policies() {
  const policies = useQuery({ queryKey: ['policies'], queryFn: api.policies, refetchInterval: 15000 })

  return (
    <>
      <PageHeader eyebrow="Your cover" title="Policies">
        <Link to="/protect" className={buttonVariants()}>
          <Plus className="size-4" /> Get protection
        </Link>
      </PageHeader>
      {policies.isPending && <Loading />}
      <ErrorNote error={policies.error} />
      {policies.data && (
        <Card>
          <CardBody className="py-3">
            {policies.data.length === 0 ? (
              <p className="py-10 text-center text-sm text-muted">No policies yet.</p>
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
    </>
  )
}
