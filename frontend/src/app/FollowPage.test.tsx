import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { FOLLOW_NOW, sharedWalk } from '../test/walkFixtures'
import { FollowPage } from './FollowPage'

vi.mock('../map/FollowMap', () => ({
  FollowMap: (p: { walker: { position: [number, number] } | null; destination: unknown; route: unknown }) => (
    <div data-testid="follow-map" data-walker={p.walker ? p.walker.position.join(',') : 'none'} data-route={p.route ? 'yes' : 'no'} />
  ),
}))

const JSON_HEADERS = { headers: { 'content-type': 'application/json' } }

async function flush(ms = 0) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms)
  })
}

describe('FollowPage', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(FOLLOW_NOW)
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    window.history.replaceState(null, '', '/')
  })

  it('shows the walker, destination, route, arrival time, and freshness', async () => {
    const fetcher = vi.fn(async () => new Response(JSON.stringify({ success: true, data: sharedWalk() }), JSON_HEADERS))
    vi.stubGlobal('fetch', fetcher)

    render(<FollowPage walkId="AbCdEfGhIjKlMnOpQrStUv" />)
    await flush()

    expect(fetcher).toHaveBeenCalledWith('/api/walks/AbCdEfGhIjKlMnOpQrStUv', expect.anything())
    expect(screen.getByRole('heading', { name: 'Walking to Midtown MARTA' })).toBeInTheDocument()
    expect(screen.getByText('Arrives ~10:54 PM')).toBeInTheDocument()
    expect(screen.getByText('Updated 12 s ago')).toBeInTheDocument()
    const map = await screen.findByTestId('follow-map')
    expect(map).toHaveAttribute('data-walker', '-84.395,33.7775')
    expect(map).toHaveAttribute('data-route', 'yes')

    await flush(3000)
    expect(screen.getByText('Updated 15 s ago')).toBeInTheDocument()
  })

  it('shows "Link expired" for a missing walk', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify({ success: false, error: { code: 'WALK_NOT_FOUND', message: 'x' } }), JSON_HEADERS)),
    )

    render(<FollowPage walkId="gone" />)
    await flush()

    expect(screen.getByRole('status')).toHaveTextContent('Link expired')
  })

  it('stays offline in demo mode', async () => {
    const fetcher = vi.fn()
    vi.stubGlobal('fetch', fetcher)
    window.history.replaceState(null, '', '/follow/demo123?demo=1')

    render(<FollowPage walkId="demo123" />)
    await flush()

    expect(screen.getByRole('status')).toHaveTextContent('Live sharing needs a connection')
    expect(fetcher).not.toHaveBeenCalled()
  })

  it('links back to PathPro', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ success: true, data: sharedWalk() }), JSON_HEADERS)))

    render(<FollowPage walkId="AbCdEfGhIjKlMnOpQrStUv" />)
    await flush()

    expect(screen.getByRole('link', { name: 'Open PathPro' })).toHaveAttribute('href', '/')
  })
})
