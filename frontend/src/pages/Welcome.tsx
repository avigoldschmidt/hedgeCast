import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, Building2, CheckCircle2, CloudRain, Landmark, ShieldCheck, Zap } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { api, type S } from '@/api/client'
import { ErrorNote } from '@/components/domain'
import { Logo } from '@/components/Logo'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Field, Input, Select } from '@/components/ui/field'
import { cn, money } from '@/lib/format'

const INDUSTRIES = [
  'Café or coffee shop',
  'Restaurant or bar',
  'Food truck',
  'Farm or market stand',
  'Outdoor events',
  'Retail shop',
  'Recreation or rentals',
  'Landscaping or construction',
  'Other',
]

const PITCH = [
  { icon: CloudRain, title: 'Pick the weather that hurts', body: 'Rain, heat, or a cold snap on the days that matter.' },
  { icon: Zap, title: 'Priced live by the market', body: 'A real-time price, locked for 30 seconds, one click to buy.' },
  { icon: ShieldCheck, title: 'Paid automatically', body: 'When the official reading confirms it, money lands in checking.' },
]

export function Welcome() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [business, setBusiness] = useState<S['Business'] | null>(null)
  const cities = useQuery({ queryKey: ['cities'], queryFn: api.cities })
  const existing = useQuery({ queryKey: ['businesses'], queryFn: api.businesses })

  const create = useMutation({
    mutationFn: api.createBusiness,
    onSuccess: (data) => setBusiness(data),
  })
  const link = useMutation({
    mutationFn: api.linkBank,
    onSuccess: (data) => {
      setBusiness(data)
      queryClient.setQueryData(['me'], data)
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
      city_id: String(form.get('city_id') ?? ''),
    })
  }

  function finish() {
    queryClient.setQueryData(['me'], business)
    navigate('/')
  }

  const step = !business ? 1 : business.bank.linked ? 3 : 2

  return (
    <div className="grid min-h-screen lg:grid-cols-[1.05fr_1fr]">
      <section className="relative hidden overflow-hidden bg-ink px-14 py-12 text-canvas lg:flex lg:flex-col">
        <div className="absolute -top-40 -right-40 size-[520px] rounded-full bg-brand/40 blur-3xl" />
        <div className="absolute bottom-0 left-0 size-[380px] rounded-full bg-sun/10 blur-3xl" />
        <div className="relative">
          <span className="inline-flex items-center gap-2.5 rounded-xl bg-canvas px-3 py-1.5">
            <Logo />
          </span>
        </div>
        <div className="relative mt-auto max-w-lg">
          <h1 className="font-display text-5xl leading-[1.05] font-semibold tracking-tight">
            Weather protection that pays out on its own.
          </h1>
          <p className="mt-5 text-lg text-canvas/70">
            Parametric cover for small businesses. Choose the weather that costs you money, see a live price, and get paid
            automatically when it happens.
          </p>
          <ul className="mt-10 space-y-5">
            {PITCH.map(({ icon: Icon, title, body }) => (
              <li key={title} className="flex gap-4">
                <span className="mt-0.5 inline-flex size-9 shrink-0 items-center justify-center rounded-lg bg-canvas/10">
                  <Icon className="size-4.5" />
                </span>
                <div>
                  <div className="font-medium">{title}</div>
                  <div className="text-sm text-canvas/60">{body}</div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          <div className="mb-8 lg:hidden">
            <Logo />
          </div>
          <Steps step={step} />

          {step === 1 && (
            <>
              <h2 className="font-display mt-8 text-3xl font-semibold tracking-tight">Tell us about your business</h2>
              <p className="mt-2 text-muted">We use your location to find the official weather station that settles your cover.</p>
              <form onSubmit={submit} className="mt-8 space-y-5">
                <Field label="Business name">
                  <Input name="name" required maxLength={80} placeholder="Peach Stand Café" autoComplete="organization" />
                </Field>
                <Field label="What kind of business">
                  <Select name="industry" required defaultValue="">
                    <option value="" disabled>
                      Choose one
                    </option>
                    {INDUSTRIES.map((industry) => (
                      <option key={industry}>{industry}</option>
                    ))}
                  </Select>
                </Field>
                <Field label="City">
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
                <ErrorNote error={create.error} />
                <Button type="submit" size="lg" className="w-full" disabled={create.isPending}>
                  {create.isPending ? 'Creating…' : 'Continue'} <ArrowRight className="size-4" />
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
                            {item.industry} · {item.city.name}, {item.city.state}
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

          {step === 2 && business && (
            <>
              <h2 className="font-display mt-8 text-3xl font-semibold tracking-tight">Connect your checking account</h2>
              <p className="mt-2 text-muted">
                Premiums are paid from this account and payouts land back in it. No cards, no claims forms.
              </p>
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
              <button onClick={finish} className="mt-4 w-full text-center text-sm text-muted hover:text-ink">
                Skip for now
              </button>
            </>
          )}

          {step === 3 && business && (
            <>
              <h2 className="font-display mt-8 text-3xl font-semibold tracking-tight">You're set up</h2>
              <Card className="mt-8 p-5">
                <div className="flex items-center gap-3">
                  <CheckCircle2 className="size-5 text-good" />
                  <div className="flex-1 text-sm">
                    Checking ••{business.bank.account_mask} connected
                  </div>
                  {business.bank.balance_cents != null && (
                    <div className="num text-sm font-semibold">{money(business.bank.balance_cents)}</div>
                  )}
                </div>
              </Card>
              <Button size="lg" className="mt-6 w-full" onClick={finish}>
                Go to my dashboard <ArrowRight className="size-4" />
              </Button>
            </>
          )}
        </div>
      </section>
    </div>
  )
}

function Steps({ step }: { step: number }) {
  const labels = ['Business', 'Bank', 'Done']
  return (
    <ol className="flex items-center gap-2 text-xs font-medium">
      {labels.map((label, index) => {
        const number = index + 1
        return (
          <li key={label} className="flex items-center gap-2">
            <span
              className={cn(
                'inline-flex size-6 items-center justify-center rounded-full',
                number < step && 'bg-good text-white',
                number === step && 'bg-ink text-canvas',
                number > step && 'bg-ink/5 text-muted',
              )}
            >
              {number < step ? '✓' : number}
            </span>
            <span className={number === step ? 'text-ink' : 'text-muted'}>{label}</span>
            {number < labels.length && <span className="mx-1 h-px w-6 bg-line-strong" />}
          </li>
        )
      })}
    </ol>
  )
}
