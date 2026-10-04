import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router'
import { api, type S } from '@/api/client'
import { Logo } from '@/components/Logo'
import { cn, money } from '@/lib/format'

const NAV = [
  { to: '/', label: 'Plan', end: true },
  { to: '/policies', label: 'Cover', end: false },
]

export function AppShell({ business }: { business: S['Business'] }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const me = useQuery({
    queryKey: ['me'],
    queryFn: api.me,
    initialData: business,
    refetchOnWindowFocus: true,
    refetchInterval: (query) => (query.state.data?.bank.linked ? 10000 : false),
  })
  const current = me.data ?? business
  const balanceCents = current.bank.linked ? (current.bank.balance_cents ?? null) : null
  const [flash, setFlash] = useState<{ delta: number; key: number } | null>(null)
  const prevBalance = useRef<number | null>(null)

  useEffect(() => {
    if (balanceCents == null) {
      prevBalance.current = null
      return
    }
    if (prevBalance.current != null && balanceCents !== prevBalance.current) {
      setFlash({ delta: balanceCents - prevBalance.current, key: Date.now() })
    }
    prevBalance.current = balanceCents
  }, [balanceCents])

  useEffect(() => {
    if (!flash) return
    const timer = window.setTimeout(() => setFlash(null), 4500)
    return () => window.clearTimeout(timer)
  }, [flash])

  async function switchBusiness() {
    await api.endSession()
    queryClient.clear()
    navigate('/welcome')
  }

  const checking = balanceCents != null ? money(balanceCents) : null

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-line bg-canvas/85 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-5xl items-center gap-8 px-6">
          <Link to="/">
            <Logo />
          </Link>
          <nav className="flex items-center gap-1">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn(
                    'rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                    isActive ? 'bg-ink/[0.06] text-ink' : 'text-muted hover:text-ink',
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto text-right leading-tight">
            <div className="text-sm font-medium text-ink">{current.name}</div>
            <div className="text-xs text-muted">
              {checking ? (
                <span
                  className={cn(
                    'inline-flex items-center gap-1.5 transition-colors',
                    flash && (flash.delta > 0 ? 'text-good' : flash.delta < 0 ? 'text-ink' : ''),
                  )}
                >
                  Checking · <span className="num font-medium text-ink">{checking}</span>
                  {flash && flash.delta !== 0 && (
                    <span
                      key={flash.key}
                      className={cn('num font-semibold', flash.delta > 0 ? 'text-good' : 'text-ink-soft')}
                    >
                      {flash.delta > 0 ? '+' : '−'}
                      {money(Math.abs(flash.delta))}
                    </span>
                  )}
                </span>
              ) : current.bank.linked && current.bank.error ? (
                <span className="text-sun">{current.bank.error}</span>
              ) : current.city ? (
                `${current.city.name}, ${current.city.state}`
              ) : (
                current.industry
              )}
            </div>
            <button
              type="button"
              onClick={switchBusiness}
              className="mt-0.5 text-xs text-muted underline-offset-2 hover:text-ink hover:underline"
            >
              Not this business?
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-6 pt-10 pb-24">
        <Outlet />
      </main>
      <footer className="mx-auto flex max-w-5xl items-center justify-between border-t border-line px-6 py-6 text-xs text-muted">
        <span>Prices and results from Kalshi. Bank movements via Capital One Nessie.</span>
        <Link to="/ops" className="hover:text-ink">
          Settlement
        </Link>
      </footer>
    </div>
  )
}
