import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'

export function Panel({
  title,
  aside,
  children,
  className,
}: {
  title?: string
  aside?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section
      className={cn('rounded-lg border border-line bg-panel overflow-hidden', className)}
    >
      {title && (
        <header className="flex items-center justify-between gap-3 border-b border-line-soft px-4 py-2.5">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted">
            {title}
          </h2>
          {aside}
        </header>
      )}
      {children}
    </section>
  )
}
