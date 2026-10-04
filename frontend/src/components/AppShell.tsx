import { useQuery, useQueryClient } from '@tanstack/react-query'
import { LogOut } from 'lucide-react'
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

  async function switchBusiness() {
    await api.endSession()
    queryClient.clear()
    navigate('/welcome')
  }

  const checking =
    current.bank.linked && current.bank.balance_cents != null ? money(current.bank.balance_cents) : null

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
          <div className="ml-auto flex items-center gap-3">
            <div className="text-right leading-tight">
              <div className="text-sm font-medium text-ink">{current.name}</div>
              <div className="text-xs text-muted">
                {checking ? (
                  <>
                    Checking · <span className="num">{checking}</span>
                  </>
                ) : current.city ? (
                  `${current.city.name}, ${current.city.state}`
                ) : (
                  current.industry
                )}
              </div>
            </div>
            <button
              onClick={switchBusiness}
              title="Switch business"
              className="rounded-lg p-2 text-muted transition-colors hover:bg-ink/5 hover:text-ink"
            >
              <LogOut className="size-4" />
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-6 pt-10 pb-24">
        <Outlet />
      </main>
      <footer className="mx-auto flex max-w-5xl items-center justify-between border-t border-line px-6 py-6 text-xs text-muted">
        <span>Prices and results from Kalshi. Bank movements via Capital One Nessie sandbox.</span>
        <Link to="/ops" className="hover:text-ink">
          Risk desk
        </Link>
      </footer>
    </div>
  )
}
