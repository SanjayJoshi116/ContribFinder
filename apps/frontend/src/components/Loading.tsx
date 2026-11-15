import { cn } from '@/lib/utils'

/** The one loading text, announced politely to screen readers (CMP-10). */
export function Loading({ className }: { className?: string }) {
  return (
    <p role="status" className={cn('text-muted-foreground text-sm', className)}>
      Loading…
    </p>
  )
}
