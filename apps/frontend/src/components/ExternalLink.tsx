import type { ReactNode } from 'react'

/** A link that opens outside the app in a new tab. `onOpen` runs when it is followed by a click
 * or by the middle mouse button (`auxclick`), so both count as opening it (FI-6). "Open link in
 * new tab" from the context menu sends no event and is not counted. */
export function ExternalLink({
  href,
  onOpen,
  className,
  children,
}: {
  href: string
  onOpen?: () => void
  className?: string
  children: ReactNode
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={className}
      onClick={onOpen}
      onAuxClick={(event) => {
        if (event.button === 1) onOpen?.()
      }}
    >
      {children}
    </a>
  )
}
