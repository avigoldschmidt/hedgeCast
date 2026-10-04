import { useQuery } from '@tanstack/react-query'
import { api, type TopicId } from '@/api/client'
import { ErrorNote, Loading, TopicIcon } from '@/components/domain'
import { cn } from '@/lib/format'
import { TOPICS } from '@/lib/topics'

export function KindStep({
  suggested,
  onPick,
}: {
  suggested: TopicId[]
  onPick: (topic: TopicId) => void
}) {
  const topics = useQuery({ queryKey: ['topics'], queryFn: api.topics })

  if (topics.isPending) return <Loading label="Loading kinds of cover…" />
  if (topics.isError) return <ErrorNote error={topics.error} />

  return (
    <div>
      <h1 className="font-display text-[34px] leading-tight font-semibold tracking-tight">What kind of cover do you need?</h1>
      <p className="mt-2 text-muted">Pick a risk type. We’ll ask a few questions to narrow it down.</p>
      <div className="mt-8 grid gap-3 sm:grid-cols-2">
        {topics.data?.map((topic) => {
          const meta = TOPICS[topic.id]
          const isSuggested = suggested.includes(topic.id)
          return (
            <button
              key={topic.id}
              type="button"
              onClick={() => onPick(topic.id)}
              className={cn(
                'rounded-2xl border border-line bg-surface p-5 text-left transition hover:border-line-strong hover:shadow-card',
                isSuggested && 'ring-1 ring-brand/30',
              )}
            >
              <div className="flex items-start gap-3.5">
                <TopicIcon topic={topic.id} />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold">{meta.name}</span>
                    {isSuggested && (
                      <span className="rounded-full bg-brand-soft px-2 py-0.5 text-[11px] font-medium text-brand">Suggested</span>
                    )}
                  </div>
                  <p className="mt-1 text-sm leading-snug text-muted">{topic.blurb}</p>
                </div>
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
