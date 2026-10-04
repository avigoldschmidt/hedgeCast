import { X } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { PlanCard, S, Side } from '@/api/client'
import { TopicIcon } from '@/components/domain'
import { PayoutPicker, QuoteCheckout, Section } from '@/components/quote'
import { TOPICS } from '@/lib/topics'
import { cn, pct } from '@/lib/format'

export function ProtectSheet({ card, badDay, onClose }: { card: PlanCard; badDay: number; onClose: () => void }) {
  const [ticker, setTicker] = useState(card.ticker)
  const [side, setSide] = useState<Side>(card.side)
  const [payout, setPayout] = useState(badDay)

  useEffect(() => {
    const close = (event: KeyboardEvent) => event.key === 'Escape' && onClose()
    document.addEventListener('keydown', close)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', close)
      document.body.style.overflow = ''
    }
  }, [onClose])

  const choice = card.choices.find((item) => item.ticker === ticker) ?? card.choices[0]
  const title = ticker === card.ticker ? card.title : `${card.group_title} · ${choice.label}`
  const request: S['QuoteRequest'] | null =
    payout >= 1
      ? {
          legs: [{ ticker, side }],
          payout_dollars: payout,
          plan: { topic: card.topic, title, why: card.why, catch: card.catch },
        }
      : null
  const chance = choice.chance == null ? null : side === 'yes' ? choice.chance : 1 - choice.chance

  return (
    <div className="fixed inset-0 z-40 flex justify-end" role="dialog" aria-modal aria-label={card.title}>
      <button aria-label="Close" className="absolute inset-0 bg-ink/30 backdrop-blur-[2px]" onClick={onClose} />
      <div className="relative flex h-full w-full max-w-lg flex-col overflow-y-auto bg-surface shadow-lift">
        <div className="flex items-start gap-4 border-b border-line px-6 py-5">
          <TopicIcon topic={card.topic} />
          <div className="min-w-0 flex-1">
            <div className="text-xs font-medium text-muted">{TOPICS[card.topic].name}</div>
            <h2 className="font-display text-2xl leading-tight font-semibold tracking-tight">{title}</h2>
            <p className="mt-1 text-sm text-ink-soft">{card.why}</p>
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 text-muted hover:bg-ink/5 hover:text-ink" aria-label="Close">
            <X className="size-5" />
          </button>
        </div>

        <div className="space-y-8 px-6 py-6">
          <Section number={1} title="What happens">
            {card.choices.length > 1 && (
              <div className="flex flex-wrap gap-2">
                {card.choices.map((item) => (
                  <button
                    key={item.ticker}
                    onClick={() => setTicker(item.ticker)}
                    className={cn(
                      'rounded-full border px-3.5 py-1.5 text-sm transition',
                      item.ticker === ticker ? 'border-ink bg-ink text-canvas' : 'border-line-strong bg-surface hover:border-ink/40',
                    )}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            )}
            {card.choices.length === 1 && <p className="text-sm font-medium">{choice.label}</p>}
            <div className="mt-3 grid grid-cols-2 gap-2">
              {(['yes', 'no'] as const).map((option) => (
                <button
                  key={option}
                  onClick={() => setSide(option)}
                  className={cn(
                    'rounded-xl border px-3.5 py-2.5 text-left text-sm transition',
                    side === option ? 'border-ink ring-1 ring-ink' : 'border-line hover:border-line-strong',
                  )}
                >
                  <span className="block font-medium">{option === 'yes' ? 'Pay me if it happens' : "Pay me if it doesn't"}</span>
                </button>
              ))}
            </div>
            {chance != null && (
              <p className="mt-2.5 text-xs text-muted">
                The market gives that a <span className="num font-medium text-ink">{pct(chance)}</span> chance.
              </p>
            )}
          </Section>

          <Section number={2} title="What would it cost you?">
            <PayoutPicker value={payout} onChange={setPayout} badDay={badDay} />
          </Section>

          <Section number={3} title="Price and fine print">
            <QuoteCheckout request={request} onPayout={setPayout} />
          </Section>
        </div>
      </div>
    </div>
  )
}
