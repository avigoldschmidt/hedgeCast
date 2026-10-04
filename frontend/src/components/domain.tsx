import { CloudRain, Snowflake, Sun, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import type { PerilId, PolicyStatus, S } from '@/api/client'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/format'

const STATUS: Record<PolicyStatus, { label: string; tone: 'neutral' | 'brand' | 'sky' | 'good' | 'sun' | 'bad' }> = {
  PENDING: { label: 'Setting up', tone: 'neutral' },
  ACTIVE: { label: 'Active', tone: 'sky' },
  AWAITING_RESULT: { label: 'Awaiting result', tone: 'brand' },
  PAID: { label: 'Paid out', tone: 'good' },
  EXPIRED: { label: 'Expired · no event', tone: 'neutral' },
  REFUNDED: { label: 'Refunded', tone: 'neutral' },
  NEEDS_REVIEW: { label: 'Under review', tone: 'sun' },
}

export function StatusBadge({ status }: { status: PolicyStatus }) {
  const { label, tone } = STATUS[status]
  return (
    <Badge tone={tone} dot>
      {label}
    </Badge>
  )
}

const BASIS: Record<S['Station']['basis_risk'], { label: string; tone: 'good' | 'sun' | 'bad' }> = {
  low: { label: 'Low basis risk', tone: 'good' },
  medium: { label: 'Medium basis risk', tone: 'sun' },
  high: { label: 'High basis risk', tone: 'bad' },
}

export function BasisRiskBadge({ risk }: { risk: S['Station']['basis_risk'] }) {
  const { label, tone } = BASIS[risk]
  return <Badge tone={tone}>{label}</Badge>
}

const PERIL_ICON: Record<PerilId, LucideIcon> = { rain: CloudRain, heat: Sun, cold: Snowflake }

const PERIL_TINT: Record<PerilId, string> = {
  rain: 'bg-sky-soft text-sky',
  heat: 'bg-sun-soft text-sun',
  cold: 'bg-brand-soft text-brand',
}

export function PerilIcon({ peril, className }: { peril: PerilId; className?: string }) {
  const Icon = PERIL_ICON[peril]
  return (
    <span className={cn('inline-flex size-10 shrink-0 items-center justify-center rounded-xl', PERIL_TINT[peril], className)}>
      <Icon className="size-5" strokeWidth={1.8} />
    </span>
  )
}

export function Stat({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <div>
      <div className="text-xs font-medium tracking-wide text-muted uppercase">{label}</div>
      <div className="num mt-1.5 text-2xl font-semibold text-ink">{value}</div>
      {sub && <div className="mt-1 text-xs text-muted">{sub}</div>}
    </div>
  )
}

export function ErrorNote({ error }: { error: unknown }) {
  if (!error) return null
  const message = error instanceof Error ? error.message : String(error)
  return <div className="rounded-lg border border-bad/20 bg-bad-soft px-4 py-3 text-sm text-bad">{message}</div>
}

export function Loading({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 py-16 text-sm text-muted">
      <span className="size-4 animate-spin rounded-full border-2 border-line-strong border-t-brand" />
      {label}
    </div>
  )
}

export function PageHeader({ eyebrow, title, children }: { eyebrow?: string; title: string; children?: ReactNode }) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div>
        {eyebrow && <div className="mb-1.5 text-sm font-medium text-brand">{eyebrow}</div>}
        <h1 className="font-display text-[34px] leading-tight font-semibold tracking-tight text-ink">{title}</h1>
      </div>
      {children}
    </div>
  )
}
