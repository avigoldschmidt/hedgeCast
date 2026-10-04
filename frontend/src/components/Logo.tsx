export function Logo() {
  return (
    <span className="inline-flex items-center gap-2.5">
      <svg viewBox="0 0 32 32" className="size-8" aria-hidden>
        <rect width="32" height="32" rx="8" fill="#0D1B2A" />
        <path
          d="M9 20.5a5 5 0 0 1 1.6-9.7 6.5 6.5 0 0 1 12.2 2.4A3.8 3.8 0 0 1 22.5 21H10"
          fill="none"
          stroke="#F6F5F1"
          strokeWidth="2.2"
          strokeLinecap="round"
        />
        <path d="M12 24.5h9" stroke="#E8A33D" strokeWidth="2.2" strokeLinecap="round" />
      </svg>
      <span className="font-display text-xl font-semibold tracking-tight text-ink">HedgeCast</span>
    </span>
  )
}
