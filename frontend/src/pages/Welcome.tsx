import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, Building2 } from 'lucide-react'
import { type FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { api } from '@/api/client'
import { ErrorNote } from '@/components/domain'
import { Logo } from '@/components/Logo'
import { Button } from '@/components/ui/button'
import { Field, Input, Select } from '@/components/ui/field'

const PITCH = [
  { title: 'Pick a kind of cover', body: 'Weather, rates, fuel, sports — start with the risk that matters.' },
  { title: 'Answer a few questions', body: 'We narrow open markets to the days, levels, or outcomes that fit.' },
  {
    title: 'Get paid automatically',
    body: 'When the official result confirms it, money lands in checking — no claim form.',
  },
]

export function Welcome() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const cities = useQuery({ queryKey: ['cities'], queryFn: api.cities })
  const industries = useQuery({ queryKey: ['industries'], queryFn: api.industries })
  const existing = useQuery({ queryKey: ['businesses'], queryFn: api.businesses })

  const create = useMutation({
    mutationFn: api.createBusiness,
    onSuccess: (data) => {
      queryClient.setQueryData(['me'], data)
      navigate('/')
    },
  })
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
      industry: String(form.get('industry') ?? ''),
      city_id: String(form.get('city_id') ?? '') || null,
    })
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-[1fr_1fr]">
      <section className="relative hidden overflow-hidden bg-ink px-14 py-12 text-canvas lg:flex lg:flex-col">
        <div className="absolute -top-40 -right-40 size-[520px] rounded-full bg-brand/40 blur-3xl" />
        <Logo className="font-display relative text-xl font-semibold tracking-tight text-canvas" />
        <div className="relative mt-auto max-w-lg">
          <h1 className="font-display text-5xl leading-[1.05] font-semibold tracking-tight">
            Find cover for what could cost your business money.
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

          <h2 className="font-display text-3xl font-semibold tracking-tight">Tell us about your business</h2>
          <p className="mt-2 text-muted">A few details so we can show cover that fits — then walk through a short plan.</p>
          <form onSubmit={submit} className="mt-8 space-y-5">
            <Field label="Business name">
              <Input name="name" required maxLength={80} placeholder="Peach Stand Café" autoComplete="organization" />
            </Field>
            <Field label="Industry">
              <Select name="industry" required defaultValue="">
                <option value="" disabled>
                  {industries.isPending ? 'Loading industries…' : 'Choose one'}
                </option>
                {industries.data?.map((item) => (
                  <option key={item.name} value={item.name}>
                    {item.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Where are you?" hint="Helps with local weather and events.">
              <Select name="city_id" required defaultValue="">
                <option value="" disabled>
                  {cities.isPending ? 'Loading cities…' : 'Choose your city'}
                </option>
                {cities.data?.map((city) => (
                  <option key={city.id} value={city.id}>
                    {city.name}, {city.state}
                  </option>
                ))}
              </Select>
            </Field>
            <ErrorNote error={create.error ?? cities.error ?? industries.error} />
            <Button
              type="submit"
              size="lg"
              className="w-full"
              disabled={create.isPending || cities.isPending || industries.isPending || !cities.data?.length || !industries.data?.length}
            >
              {create.isPending ? 'Setting up…' : 'Find cover'} <ArrowRight className="size-4" />
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
        </div>
      </section>
    </div>
  )
}
