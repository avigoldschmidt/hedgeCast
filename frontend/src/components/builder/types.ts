import type { Side, TopicId } from '@/api/client'

export type BuilderSelection = {
  topic: TopicId
  title: string
  why: string
  catch: string
  legs: { ticker: string; side: Side }[]
}

export type BuilderStep = 'kind' | 'narrow' | 'cover'
