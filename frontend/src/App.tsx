import { useQuery } from '@tanstack/react-query'
import { Navigate, Route, Routes } from 'react-router'
import { api } from '@/api/client'
import { AppShell } from '@/components/AppShell'
import { ErrorNote, Loading } from '@/components/domain'
import { Home } from '@/pages/Home'
import { Ops } from '@/pages/Ops'
import { Policies } from '@/pages/Policies'
import { PolicyPage } from '@/pages/PolicyPage'
import { Welcome } from '@/pages/Welcome'

function RequireBusiness() {
  const me = useQuery({ queryKey: ['me'], queryFn: api.me })
  if (me.isPending) {
    return (
      <div className="mx-auto max-w-5xl px-6">
        <Loading />
      </div>
    )
  }
  if (me.isError) {
    const status = (me.error as { status?: number }).status
    if (status === 401 || status === 404) return <Navigate to="/welcome" replace />
    return (
      <div className="mx-auto max-w-5xl px-6 py-16">
        <ErrorNote error={me.error} />
      </div>
    )
  }
  return <AppShell business={me.data} />
}

export default function App() {
  return (
    <Routes>
      <Route path="/welcome" element={<Welcome />} />
      <Route path="/ops" element={<Ops />} />
      <Route element={<RequireBusiness />}>
        <Route index element={<Home />} />
        <Route path="/policies" element={<Policies />} />
        <Route path="/policies/:id" element={<PolicyPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
