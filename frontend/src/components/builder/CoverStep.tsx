import { useState } from 'react'
import type { S } from '@/api/client'
import type { BuilderSelection } from '@/components/builder/types'
import { TopicIcon } from '@/components/domain'
import { PayoutPicker, QuoteCheckout, Section } from '@/components/quote'
import { TOPICS } from '@/lib/topics'

export function CoverStep({ selection, badDay }: { selection: BuilderSelection; badDay: number }) {
  const [payout, setPayout] = useState(badDay)
  const request: S['QuoteRequest'] | null =
    payout >= 1 && selection.legs.length > 0
      ? {
          legs: selection.legs,
          payout_dollars: payout,
          plan: {
            topic: selection.topic,
            title: selection.title,
            why: selection.why,
            catch: selection.catch,
          },
        }
      : null

  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_400px]">
      <div className="space-y-8">
        <div className="flex items-start gap-4">
          <TopicIcon topic={selection.topic} />
          <div className="min-w-0">
            <div className="text-xs font-medium text-muted">{TOPICS[selection.topic].name}</div>
            <h1 className="font-display text-[28px] leading-tight font-semibold tracking-tight">{selection.title}</h1>
            <p className="mt-1 text-sm text-ink-soft">{selection.why}</p>
            {selection.catch && <p className="mt-2 text-xs text-muted">{selection.catch}</p>}
          </div>
        </div>

        <Section number={1} title="How much would a bad day cost you?">
          <PayoutPicker value={payout} onChange={setPayout} badDay={badDay} />
          {selection.legs.length > 1 && (
            <p className="mt-2 text-xs text-muted">
              Pays up to that amount for each covered day that goes your way ({selection.legs.length} days selected).
            </p>
          )}
        </Section>
      </div>

      <aside className="lg:sticky lg:top-24 lg:self-start">
        <div className="rounded-2xl border border-line bg-surface p-5 shadow-card">
          <h2 className="mb-4 text-sm font-semibold tracking-wide text-muted uppercase">Price</h2>
          <QuoteCheckout request={request} onPayout={setPayout} />
        </div>
      </aside>
    </div>
  )
}
