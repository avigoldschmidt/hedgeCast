import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, Building2, Check, Landmark } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { api, type S, type TopicId } from '@/api/client'
import { ErrorNote } from '@/components/domain'
import { Logo } from '@/components/Logo'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Field, Input, Select, Textarea } from '@/components/ui/field'
import { cn, money } from '@/lib/format'
import { TOPICS } from '@/lib/topics'

const PITCH = [
  { title: 'Tell us what you do', body: 'One sentence is enough. We work out what could cost you money.' },
  { title: 'See your forecast', body: 'Real upcoming events for your business, with the market’s odds.' },
  { title: 'Get paid automatically', body: 'When the official result confirms it, money lands in checking.' },
]

type Stage = 'about' | 'watch' | 'bank'

export function Welcome() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [business, setBusiness] = useState<S['Business'] | null>(null)
  const [stage, setStage] = useState<Stage>('about')
  const [watching, setWatching] = useState<TopicId[]>([])
  const cities = useQuery({ queryKey: ['cities'], queryFn: api.cities })
  const topics = useQuery({ queryKey: ['topics'], queryFn: api.topics })
  const existing = useQuery({ queryKey: ['businesses'], queryFn: api.businesses })

  const create = useMutation({
    mutationFn: api.createBusiness,
    onSuccess: (data) => {
      setBusiness(data)
      setWatching(data.topics)
      setStage('watch')
    },
  })
  const save = useMutation({
    mutationFn: api.setTopics,
    onSuccess: (data) => {
      setBusiness(data)
      setStage('bank')
    },
  })
  const link = useMutation({ mutationFn: api.linkBank, onSuccess: (data) => finish(data) })
  const resume = useMutation({
    mutationFn: api.startSession,
    onSuccess: (data) => {
      queryClient.setQueryData(['me'], data)
      navigate('/')
    },
  })

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    create.mutate({
      name: String(form.get('name') ?? ''),
      description: String(form.get('description') ?? ''),
      city_id: String(form.get('city_id') ?? '') || null,
    })
  }

  function toggle(id: TopicId) {
    setWatching(watching.includes(id) ? watching.filter((t) => t !== id) : [...watching, id])
  }

  function finish(data: S['Business'] | null) {
    queryClient.setQueryData(['me'], data)
    queryClient.removeQueries({ queryKey: ['forecast'] })
    navigate('/')
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-[1fr_1fr]">
      <section className="relative hidden overflow-hidden bg-ink px-14 py-12 text-canvas lg:flex lg:flex-col">
        <div className="absolute -top-40 -right-40 size-[520px] rounded-full bg-brand/40 blur-3xl" />
        <Logo className="font-display relative text-xl font-semibold tracking-tight text-canvas" />
        <div className="relative mt-auto max-w-lg">
          <h1 className="font-display text-5xl leading-[1.05] font-semibold tracking-tight">
            Protection for what could cost your business money.
          </h1>
          <ol className="mt-10 space-y-6">
            {PITCH.map(({ title, body }, index) => (
              <li key={title} className="flex gap-4">
                <span className="num mt-0.5 inline-flex size-8 shrink-0 items-center justify-center rounded-full bg-canvas/10 text-sm">
                  {index + 1}
                </span>
                <div>
                  <div className="font-medium">{title}</div>
                  <div className="text-sm text-canvas/60">{body}</div>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          <div className="mb-8 lg:hidden">
            <Logo />
          </div>
          <Steps stage={stage} />

          {stage === 'about' && (
            <>
              <h2 className="font-display mt-8 text-3xl font-semibold tracking-tight">Tell us about your business</h2>
              <p className="mt-2 text-muted">In your own words. We’ll tailor everything to it.</p>
              <form onSubmit={submit} className="mt-8 space-y-5">
                <Field label="Business name">
                  <Input name="name" required maxLength={80} placeholder="Peach Stand Café" autoComplete="organization" />
                </Field>
                <Field label="What do you do?">
                  <Textarea
                    name="description"
                    required
                    minLength={3}
                    maxLength={300}
                    rows={3}
                    placeholder="We run a small coffee shop with a sidewalk patio."
                  />
                </Field>
                <Field label="Where are you?">
                  <Select name="city_id" defaultValue="">
                    <option value="">{cities.isPending ? 'Loading cities…' : 'Skip for now'}</option>
                    {cities.data?.map((city) => (
                      <option key={city.id} value={city.id}>
                        {city.name}, {city.state}
                      </option>
                    ))}
                  </Select>
                </Field>
                <ErrorNote error={create.error} />
                <Button type="submit" size="lg" className="w-full" disabled={create.isPending}>
                  {create.isPending ? 'Getting to know your business…' : 'Continue'} <ArrowRight className="size-4" />
                </Button>
              </form>
              {existing.data && existing.data.length > 0 && (
                <div className="mt-10">
                  <div className="mb-3 text-xs font-medium tracking-wide text-muted uppercase">Or continue as</div>
                  <div className="space-y-2">
                    {existing.data.slice(0, 4).map((item) => (
                      <button
                        key={item.id}
                        onClick={() => resume.mutate({ business_id: item.id })}
                        className="flex w-full items-center gap-3 rounded-xl border border-line bg-surface px-4 py-3 text-left transition hover:border-line-strong hover:shadow-card"
                      >
                        <Building2 className="size-4 text-muted" />
                        <span className="flex-1">
                          <span className="block text-sm font-medium">{item.name}</span>
                          <span className="block text-xs text-muted">
                            {item.industry}
                            {item.city && ` · ${item.city.name}, ${item.city.state}`}
                          </span>
                        </span>
                        <ArrowRight className="size-4 text-muted" />
                      </button>
                    ))}
                  </div>
                  <ErrorNote error={resume.error} />
                </div>
              )}
            </>
          )}

          {stage === 'watch' && business && (
            <>
              <h2 className="font-display mt-8 text-3xl font-semibold tracking-tight">Here’s what we’ll watch for you</h2>
              <p className="mt-2 text-muted">
                Picked for a {business.industry.toLowerCase()}. Tap to change. A bad day could cost you about{' '}
                <strong className="num text-ink">{money(business.bad_day_dollars * 100)}</strong>, so that’s where your cover
                starts.
              </p>
              <div className="mt-8 grid gap-2.5">
                {topics.data?.map((topic) => {
                  const on = watching.includes(topic.id)
                  const { icon: Icon, tint } = TOPICS[topic.id]
                  return (
                    <button
                      key={topic.id}
                      type="button"
                      aria-pressed={on}
                      onClick={() => toggle(topic.id)}
                      className={cn(
                        'flex items-center gap-3.5 rounded-xl border px-4 py-3 text-left transition',
                        on ? 'border-ink bg-surface ring-1 ring-ink' : 'border-line bg-surface/60 opacity-70 hover:opacity-100',
                      )}
                    >
                      <span className={cn('inline-flex size-9 items-center justify-center rounded-lg', tint)}>
                        <Icon className="size-4.5" strokeWidth={1.8} />
                      </span>
                      <span className="flex-1">
                        <span className="block text-sm font-medium">{topic.name}</span>
                        <span className="block text-xs text-muted">{topic.blurb}</span>
                      </span>
                      <span
                        className={cn(
                          'inline-flex size-5 items-center justify-center rounded-full border',
                          on ? 'border-ink bg-ink text-canvas' : 'border-line-strong',
                        )}
                      >
                        {on && <Check className="size-3" />}
                      </span>
                    </button>
                  )
                })}
              </div>
              <ErrorNote error={save.error} />
              <Button size="lg" className="mt-6 w-full" disabled={watching.length === 0 || save.isPending} onClick={() => save.mutate(watching)}>
                {save.isPending ? 'Saving…' : 'Looks right'} <ArrowRight className="size-4" />
              </Button>
            </>
          )}

          {stage === 'bank' && business && (
            <>
              <h2 className="font-display mt-8 text-3xl font-semibold tracking-tight">Connect your checking account</h2>
              <p className="mt-2 text-muted">Cover is paid from this account and payouts land back in it. No claim forms.</p>
              <Card className="mt-8 flex items-center gap-4 p-5">
                <span className="inline-flex size-11 items-center justify-center rounded-xl bg-brand-soft text-brand">
                  <Landmark className="size-5" />
                </span>
                <div className="flex-1">
                  <div className="font-medium">Capital One business checking</div>
                  <div className="text-sm text-muted">Sandbox account for {business.name}</div>
                </div>
              </Card>
              <ErrorNote error={link.error} />
              <Button size="lg" className="mt-6 w-full" onClick={() => link.mutate()} disabled={link.isPending}>
                {link.isPending ? 'Connecting…' : 'Connect checking'}
              </Button>
              <button onClick={() => finish(business)} className="mt-4 w-full text-center text-sm text-muted hover:text-ink">
                Skip for now
              </button>
            </>
          )}
        </div>
      </section>
    </div>
  )
}

function Steps({ stage }: { stage: Stage }) {
  const stages: [Stage, string][] = [
    ['about', 'Your business'],
    ['watch', 'What we watch'],
    ['bank', 'Checking'],
  ]
  const current = stages.findIndex(([id]) => id === stage)
  return (
    <ol className="flex items-center gap-2 text-xs font-medium">
      {stages.map(([id, label], index) => (
        <li key={id} className="flex items-center gap-2">
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
          <span className={index === current ? 'text-ink' : 'text-muted'}>{label}</span>
          {index < stages.length - 1 && <span className="mx-1 h-px w-6 bg-line-strong" />}
        </li>
      ))}
    </ol>
  )
}
