import { CloudSun, Fuel, Landmark, Shield, Ship, ShoppingBasket, Trophy, Users, type LucideIcon } from 'lucide-react'
import type { TopicId } from '@/api/client'

export const TOPICS: Record<TopicId, { name: string; icon: LucideIcon; tint: string }> = {
  weather: { name: 'Weather', icon: CloudSun, tint: 'bg-sky-soft text-sky' },
  fuel: { name: 'Fuel and gas', icon: Fuel, tint: 'bg-sun-soft text-sun' },
  rates: { name: 'Interest rates', icon: Landmark, tint: 'bg-brand-soft text-brand' },
  prices: { name: 'Prices', icon: ShoppingBasket, tint: 'bg-good-soft text-good' },
  tariffs: { name: 'Trade and tariffs', icon: Ship, tint: 'bg-brand-soft text-brand' },
  sports: { name: 'Sports and events', icon: Trophy, tint: 'bg-sun-soft text-sun' },
  jobs: { name: 'Jobs and wages', icon: Users, tint: 'bg-sky-soft text-sky' },
  other: { name: 'Something else', icon: Shield, tint: 'bg-ink/5 text-ink-soft' },
}
