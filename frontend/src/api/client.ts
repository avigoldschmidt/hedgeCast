import type { components } from './schema'

export type S = components['schemas']
export type PerilId = S['Peril']['id']
export type Side = S['LegRequest']['side']
export type PolicyStatus = S['PolicySummary']['status']

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

function messageFrom(data: unknown, status: number) {
  if (data && typeof data === 'object' && 'detail' in data) {
    const detail = (data as { detail: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg)
  }
  return `Request failed (${status}).`
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method,
    credentials: 'same-origin',
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const data = await response.json().catch(() => null)
  if (!response.ok) throw new ApiError(response.status, messageFrom(data, response.status))
  return data as T
}

export const api = {
  cities: () => request<S['City'][]>('GET', '/cities'),
  perils: () => request<S['Peril'][]>('GET', '/perils'),
  businesses: () => request<S['BusinessListItem'][]>('GET', '/businesses'),
  createBusiness: (body: S['CreateBusiness']) => request<S['Business']>('POST', '/businesses', body),
  startSession: (body: S['SessionRequest']) => request<S['Business']>('POST', '/session', body),
  endSession: () => request<{ ok: boolean }>('DELETE', '/session'),
  me: () => request<S['Business']>('GET', '/me'),
  linkBank: () => request<S['Business']>('POST', '/me/bank'),
  dashboard: () => request<S['Dashboard']>('GET', '/dashboard'),
  markets: (q: string, category: string | null) =>
    request<S['MarketSearch']>('GET', `/markets?${new URLSearchParams({ q, ...(category ? { category } : {}) })}`),
  event: (ticker: string) => request<S['EventDetail']>('GET', `/events/${encodeURIComponent(ticker)}`),
  weather: (peril: PerilId) => request<S['WeatherOptions']>('GET', `/weather?peril=${peril}`),
  quote: (body: S['QuoteRequest']) => request<S['Quote']>('POST', '/quotes', body),
  bind: (body: S['BindRequest']) => request<S['PolicyDetail']>('POST', '/policies', body),
  policies: () => request<S['PolicySummary'][]>('GET', '/policies'),
  policy: (id: number) => request<S['PolicyDetail']>('GET', `/policies/${id}`),
  ops: () => request<S['OpsOverview']>('GET', '/ops'),
  resolve: (id: number, body: S['ResolveRequest']) =>
    request<S['PolicyDetail']>('POST', `/ops/policies/${id}/resolve`, body),
  settle: () => request<S['OpsOverview']>('POST', '/ops/settle'),
}
