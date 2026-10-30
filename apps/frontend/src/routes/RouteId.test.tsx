import { act, render, screen } from '@testing-library/react'
import { useEffect } from 'react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it } from 'vitest'

import { RouteId } from './RouteId'

/** Records each mount, so a test can tell a remount from a re-render with a new id. */
function Thing({ id, mounts }: { id: number; mounts: number[] }) {
  useEffect(() => {
    mounts.push(id)
    // Mount-only on purpose: a re-render with another id must not count.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  return (
    <p>
      thing {typeof id} {id}
    </p>
  )
}

function renderAt(path: string) {
  const mounts: number[] = []
  const router = createMemoryRouter(
    [
      {
        path: '/things/:id',
        element: (
          <RouteId invalid="No such thing.">{(id) => <Thing id={id} mounts={mounts} />}</RouteId>
        ),
      },
    ],
    { initialEntries: [path] },
  )
  render(<RouterProvider router={router} />)
  return { router, mounts }
}

describe('RouteId', () => {
  it('renders the page with the id as a number', () => {
    renderAt('/things/42')
    expect(screen.getByText('thing number 42')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('remounts the page when the route moves to another id', async () => {
    const { router, mounts } = renderAt('/things/1')
    await act(() => router.navigate('/things/2'))

    expect(screen.getByText('thing number 2')).toBeInTheDocument()
    expect(mounts).toEqual([1, 2])
  })

  // '%207' reaches the route as ' 7' (the router decodes params).
  it.each(['abc', '0', '1.5', '0x1f', '%207', '9007199254740993'])(
    'renders the dead end for %s',
    (param) => {
      renderAt(`/things/${param}`)
      expect(screen.getByRole('alert')).toHaveTextContent('No such thing.')
      expect(screen.getByRole('link', { name: 'Back to your dashboard' })).toHaveAttribute(
        'href',
        '/app',
      )
      expect(screen.queryByText(/^thing/)).not.toBeInTheDocument()
    },
  )
})
