import { useQuery } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { useCallback, useState } from 'react'
import { api, type TopicId } from '@/api/client'
import { CoverStep } from '@/components/builder/CoverStep'
import { KindStep } from '@/components/builder/KindStep'
import { OtherNarrow } from '@/components/builder/OtherNarrow'
import { TopicNarrow } from '@/components/builder/TopicNarrow'
import type { BuilderSelection, BuilderStep } from '@/components/builder/types'
import { WeatherNarrow } from '@/components/builder/WeatherNarrow'
import { ErrorNote, Loading } from '@/components/domain'
import { cn } from '@/lib/format'
import { TOPICS } from '@/lib/topics'

export function Home() {
  const me = useQuery({ queryKey: ['me'], queryFn: api.me })
  const [step, setStep] = useState<BuilderStep>('kind')
  const [topic, setTopic] = useState<TopicId | null>(null)
  const [selection, setSelection] = useState<BuilderSelection | null>(null)

  const onNarrowContinue = useCallback((next: BuilderSelection) => {
    setSelection(next)
    setStep('cover')
  }, [])

  if (me.isPending) return <Loading />
  if (me.isError) return <ErrorNote error={me.error} />
  const business = me.data

  function pickKind(next: TopicId) {
    setTopic(next)
    setSelection(null)
    setStep('narrow')
  }

  function goBack() {
    if (step === 'cover') {
      setStep('narrow')
      return
    }
    if (step === 'narrow') {
      setTopic(null)
      setSelection(null)
      setStep('kind')
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      {step !== 'kind' && (
        <button
          type="button"
          onClick={goBack}
          className="mb-6 inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink"
        >
          <ArrowLeft className="size-4" />
          {step === 'cover' ? 'Back to questions' : 'All kinds of cover'}
        </button>
      )}

      <Progress step={step} topic={topic} />

      {step === 'kind' && <KindStep suggested={business.topics} onPick={pickKind} />}

      {step === 'narrow' && topic === 'weather' && (
        <WeatherNarrow
          cityName={business.city?.name}
          hasCity={Boolean(business.city)}
          onContinue={onNarrowContinue}
        />
      )}

      {step === 'narrow' && topic && topic !== 'weather' && topic !== 'other' && (
        <TopicNarrow
          topic={topic}
          cityName={business.city?.name}
          hasCity={Boolean(business.city)}
          onContinue={onNarrowContinue}
        />
      )}

      {step === 'narrow' && topic === 'other' && <OtherNarrow onContinue={onNarrowContinue} />}

      {step === 'cover' && selection && <CoverStep selection={selection} badDay={business.bad_day_dollars} />}
    </div>
  )
}

function Progress({ step, topic }: { step: BuilderStep; topic: TopicId | null }) {
  const labels = [
    { id: 'kind' as const, label: 'Kind' },
    { id: 'narrow' as const, label: topic ? TOPICS[topic].name : 'Details' },
    { id: 'cover' as const, label: 'Price' },
  ]
  const current = labels.findIndex((item) => item.id === step)
  return (
    <ol className="mb-8 flex flex-wrap items-center gap-2 text-xs font-medium">
      {labels.map((item, index) => (
        <li key={item.id} className="flex items-center gap-2">
          <span
            className={cn(
              'inline-flex size-6 items-center justify-center rounded-full',
              index < current && 'bg-good text-white',
              index === current && 'bg-ink text-canvas',
              index > current && 'bg-ink/5 text-muted',
            )}
          >
            {index < current ? '✓' : index + 1}
          </span>
          <span className={index === current ? 'text-ink' : 'text-muted'}>{item.label}</span>
          {index < labels.length - 1 && <span className="mx-1 h-px w-6 bg-line-strong" />}
        </li>
      ))}
    </ol>
  )
}
