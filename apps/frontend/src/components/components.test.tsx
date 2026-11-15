import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it, vi } from 'vitest'

import { formatDate, formatDateTime, formatRelative, formatTime } from '@/lib/format'

import { ExternalLink } from './ExternalLink'
import { Loaded } from './Loaded'
import { RouteError } from './RouteError'

describe('format', () => {
  it('shows an unreadable time as Unknown', () => {
    expect(formatDate('nope')).toBe('Unknown')
    expect(formatDateTime('nope')).toBe('Unknown')
    expect(formatTime('nope')).toBe('Unknown')
    expect(formatRelative('nope')).toBe('Unknown')
    expect(formatDate('2026-11-03T14:05:00Z')).not.toBe('Unknown')
  })
})

describe('RouteError', () => {
  function Broken(): never {
    throw new Error('secret internals')
  }

  it('replaces a page that throws while rendering', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    try {
      const router = createMemoryRouter(
        [{ errorElement: <RouteError />, children: [{ path: '/app', element: <Broken /> }] }],
        { initialEntries: ['/app'] },
      )
      render(<RouterProvider router={router} />)

      expect(
        await screen.findByRole('heading', { level: 1, name: 'Something went wrong' }),
      ).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Reload' })).toBeInTheDocument()
      expect(screen.getByRole('link', { name: 'Back to your dashboard' })).toHaveAttribute(
        'href',
        '/app',
      )
      expect(screen.queryByText(/secret internals/)).not.toBeInTheDocument()
    } finally {
      vi.restoreAllMocks()
    }
  })
})

describe('Loaded', () => {
  const show = (query: { data: string | undefined; isError: boolean; isFetching?: boolean }) =>
    render(
      <Loaded query={query} failed={<p>Failed</p>}>
        {(data) => <p>{data}</p>}
      </Loaded>,
    )

  it('shows loading while a failed first load is retried', () => {
    show({ data: undefined, isError: true, isFetching: true })
    expect(screen.getByRole('status')).toHaveTextContent('Loading…')
    expect(screen.queryByText('Failed')).not.toBeInTheDocument()
  })

  it('shows the failure once the retry is over, and data over a failed refetch', () => {
    const { unmount } = show({ data: undefined, isError: true, isFetching: false })
    expect(screen.getByText('Failed')).toBeInTheDocument()
    unmount()
    show({ data: 'kept', isError: true, isFetching: false })
    expect(screen.getByText('kept')).toBeInTheDocument()
  })
})

describe('ExternalLink onOpen', () => {
  it('calls onOpen without arguments', async () => {
    const onOpen = vi.fn()
    render(
      <ExternalLink href="https://github.com/a/b" onOpen={onOpen}>
        GitHub
      </ExternalLink>,
    )
    const link = screen.getByRole('link', { name: 'GitHub' })
    link.addEventListener('click', (event) => event.preventDefault())
    await userEvent.click(link)
    expect(onOpen).toHaveBeenCalledWith()
  })
})
