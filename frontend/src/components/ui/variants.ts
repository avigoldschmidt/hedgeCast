import { cva } from 'class-variance-authority'

export const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:pointer-events-none disabled:opacity-50 cursor-pointer',
  {
    variants: {
      variant: {
        primary: 'bg-ink text-canvas hover:bg-ink-soft',
        brand: 'bg-brand text-white hover:bg-brand/90',
        outline: 'border border-line-strong bg-surface text-ink hover:bg-canvas',
        ghost: 'text-ink-soft hover:bg-ink/5 hover:text-ink',
        danger: 'border border-bad/30 bg-bad-soft text-bad hover:bg-bad/10',
        good: 'border border-good/30 bg-good-soft text-good hover:bg-good/10',
      },
      size: {
        sm: 'h-8 px-3 text-sm',
        md: 'h-10 px-4 text-sm',
        lg: 'h-12 px-6 text-base',
      },
    },
    defaultVariants: { variant: 'primary', size: 'md' },
  },
)
