import type { ButtonHTMLAttributes } from 'react'
import { cn } from '@/lib/cn'

type Variant = 'primary' | 'ghost' | 'danger'

/**
 * Gold is the app's only accent, so a filled gold button is the only primary
 * action on any screen. Everything else is an outline.
 */
const VARIANTS: Record<Variant, string> = {
  primary:
    'bevel-sm bg-gold text-void hover:bg-[#eec96f] ' +
    'shadow-[inset_0_1px_0_rgb(255_255_255/0.35)] disabled:hover:bg-gold',
  ghost: 'border border-edge bg-panel-2 text-fg hover:border-gold/60 hover:text-gold',
  danger: 'border border-edge bg-panel-2 text-bad hover:border-bad',
}

export function Button({
  variant = 'primary',
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center gap-2 px-3.5 py-2',
        'font-display text-[11px] font-semibold tracking-[0.14em] uppercase',
        'transition-[background-color,border-color,color,transform] duration-150',
        'active:translate-y-px disabled:cursor-not-allowed disabled:opacity-45',
        VARIANTS[variant],
        className,
      )}
      {...props}
    />
  )
}
