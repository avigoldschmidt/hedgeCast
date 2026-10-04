import { cva, type VariantProps } from 'class-variance-authority'
import type { HTMLAttributes } from 'react'
import { cn } from '@/lib/format'

const badgeVariants = cva('inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap', {
  variants: {
    tone: {
      neutral: 'bg-ink/5 text-ink-soft',
      brand: 'bg-brand-soft text-brand',
      sky: 'bg-sky-soft text-sky',
      good: 'bg-good-soft text-good',
      sun: 'bg-sun-soft text-sun',
      bad: 'bg-bad-soft text-bad',
    },
  },
  defaultVariants: { tone: 'neutral' },
})

type BadgeProps = HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants> & { dot?: boolean }

export function Badge({ className, tone, dot, children, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ tone }), className)} {...props}>
      {dot && <span className="size-1.5 rounded-full bg-current" />}
      {children}
    </span>
  )
}
