import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { ExternalLink } from './ExternalLink'

const auxClick = (element: Element, button: number) =>
  fireEvent(element, new MouseEvent('auxclick', { bubbles: true, cancelable: true, button }))

describe('ExternalLink', () => {
  it('opens in a new tab without the opener', () => {
    render(<ExternalLink href="https://github.com/a/b">GitHub</ExternalLink>)
    const link = screen.getByRole('link', { name: 'GitHub' })
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('counts a click and a middle click, not a right click', async () => {
    const onOpen = vi.fn()
    render(
      <ExternalLink href="https://github.com/a/b" onOpen={onOpen}>
        GitHub
      </ExternalLink>,
    )
    const link = screen.getByRole('link', { name: 'GitHub' })
    // jsdom does not navigate; the default action is irrelevant here.
    link.addEventListener('click', (event) => event.preventDefault())

    await userEvent.click(link)
    expect(onOpen).toHaveBeenCalledTimes(1)
    auxClick(link, 1)
    expect(onOpen).toHaveBeenCalledTimes(2)
    auxClick(link, 2)
    expect(onOpen).toHaveBeenCalledTimes(2)
  })
})
