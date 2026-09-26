import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { sharedWalk } from '../test/walkFixtures'
import { SHARE_UPDATE_MS, useShareWalk, type ShareWalkInput } from './useShareWalk'

const JSON_HEADERS = { headers: { 'content-type': 'application/json' } }
const CREATED = { walk_id: 'w1', owner_token: 'secret-token', follow_path: '/follow/w1', expires_at: '2026-09-27T08:30:00Z' }
const DEST = { label: 'Midtown MARTA', lat: 33.781, lon: -84.3863 }

type Reply = { success: boolean; data?: unknown; error?: { code: string; message: string } }

function walkServer(overrides: { create?: Reply; update?: Reply } = {}) {
  const fetcher = vi.fn(async (_url: string, init?: RequestInit) => {
    const method = init?.method ?? 'GET'
    let body: Reply
    if (method === 'POST') body = overrides.create ?? { success: true, data: CREATED }
    else {
      const sent = JSON.parse(String(init?.body ?? '{}')) as { status?: string }
      body = overrides.update ?? { success: true, data: { ...sharedWalk({ status: (sent.status ?? 'walking') as 'walking' }), route: undefined } }
    }
    return new Response(JSON.stringify(body), JSON_HEADERS)
  })
  vi.stubGlobal('fetch', fetcher)
  return fetcher
}

function puts(fetcher: ReturnType<typeof walkServer>): Array<Record<string, unknown>> {
  return fetcher.mock.calls
    .filter(([, init]) => init?.method === 'PUT')
    .map(([, init]) => JSON.parse(String(init?.body)) as Record<string, unknown>)
}

function input(over: Partial<ShareWalkInput> = {}): ShareWalkInput {
  return {
    demo: false,
    destination: DEST,
    route: [
      [-84.3962, 33.7771],
      [-84.3863, 33.781],
    ],
    position: [-84.395, 33.7775],
    accuracy: 9,
    remainingS: 720.4,
    arrived: false,
    ...over,
  }
}

async function flush(ms = 0) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms)
  })
}

describe('useShareWalk', () => {
  let share: ReturnType<typeof vi.fn>

  beforeEach(() => {
    vi.useFakeTimers()
    share = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { share })
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('creates the walk, posts the first position, and opens the share sheet with the full link', async () => {
    const fetcher = walkServer()
    const { result } = renderHook(() => useShareWalk(input()))

    await act(async () => {
      await result.current.start()
    })

    const create = JSON.parse(String((fetcher.mock.calls[0][1] as RequestInit).body)) as Record<string, unknown>
    expect(create).toEqual({ destination: DEST, eta_s: 720, route: input().route })
    expect(puts(fetcher)[0]).toEqual({
      owner_token: 'secret-token',
      lat: 33.7775,
      lon: -84.395,
      accuracy_m: 9,
      eta_s: 720,
      status: 'walking',
    })
    const url = `${window.location.origin}/follow/w1`
    expect(share).toHaveBeenCalledWith(expect.objectContaining({ url }))
    expect(result.current.phase).toBe('live')
    expect(result.current.followUrl).toBe(url)
    expect(result.current.notice).toBe('Live link shared.')
  })

  it('sends a position update about every five seconds while live', async () => {
    const fetcher = walkServer()
    const { result, rerender } = renderHook((p: ShareWalkInput) => useShareWalk(p), { initialProps: input() })
    await act(async () => {
      await result.current.start()
    })

    rerender(input({ position: [-84.392, 33.778], remainingS: 600 }))
    await flush(SHARE_UPDATE_MS)

    expect(SHARE_UPDATE_MS).toBe(5000)
    expect(puts(fetcher)).toHaveLength(2)
    expect(puts(fetcher)[1]).toMatchObject({ lat: 33.778, lon: -84.392, eta_s: 600, status: 'walking' })
  })

  it('reports arrival straight away and does not end the walk afterwards', async () => {
    const fetcher = walkServer()
    const { result, rerender, unmount } = renderHook((p: ShareWalkInput) => useShareWalk(p), { initialProps: input() })
    await act(async () => {
      await result.current.start()
    })

    rerender(input({ arrived: true }))
    await flush()
    unmount()
    await flush()

    const statuses = puts(fetcher).map((b) => b.status)
    expect(statuses).toEqual(['walking', 'arrived'])
  })

  it('ends the shared walk when navigation ends (unmount)', async () => {
    const fetcher = walkServer()
    const { result, unmount } = renderHook(() => useShareWalk(input()))
    await act(async () => {
      await result.current.start()
    })

    unmount()
    await flush()

    expect(puts(fetcher).at(-1)).toMatchObject({ status: 'ended' })
  })

  it('stops sharing on request', async () => {
    const fetcher = walkServer()
    const { result } = renderHook(() => useShareWalk(input()))
    await act(async () => {
      await result.current.start()
    })

    await act(async () => {
      result.current.stop()
      await vi.advanceTimersByTimeAsync(0)
    })
    await flush(SHARE_UPDATE_MS * 2)

    expect(puts(fetcher).at(-1)).toMatchObject({ status: 'ended' })
    expect(puts(fetcher)).toHaveLength(2)
    expect(result.current.phase).toBe('idle')
    expect(result.current.notice).toBe('Stopped sharing your walk.')
  })

  it('explains when live sharing is unavailable', async () => {
    walkServer({
      create: { success: false, error: { code: 'WALKS_UNAVAILABLE', message: 'Live sharing is unavailable right now.' } },
    })
    const { result } = renderHook(() => useShareWalk(input()))

    await act(async () => {
      await result.current.start()
    })

    expect(result.current.phase).toBe('idle')
    expect(result.current.notice).toBe('Live sharing is unavailable right now.')
    expect(share).not.toHaveBeenCalled()
  })

  it('stops quietly when the link has expired', async () => {
    const fetcher = walkServer()
    const { result } = renderHook(() => useShareWalk(input()))
    await act(async () => {
      await result.current.start()
    })
    fetcher.mockImplementation(
      async () => new Response(JSON.stringify({ success: false, error: { code: 'WALK_NOT_FOUND', message: 'x' } }), JSON_HEADERS),
    )

    await flush(SHARE_UPDATE_MS)

    expect(result.current.phase).toBe('idle')
    expect(result.current.notice).toBe('Your live link expired. Share again to start a new one.')
  })

  it('keeps sharing through a dropped connection', async () => {
    const fetcher = walkServer()
    const { result } = renderHook(() => useShareWalk(input()))
    await act(async () => {
      await result.current.start()
    })
    fetcher.mockRejectedValueOnce(new TypeError('offline'))

    await flush(SHARE_UPDATE_MS)
    await flush(SHARE_UPDATE_MS)

    expect(result.current.phase).toBe('live')
    expect(puts(fetcher).length).toBeGreaterThanOrEqual(2)
  })

  it('copies the link when the share sheet is unavailable', async () => {
    walkServer()
    const writeText = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    const { result } = renderHook(() => useShareWalk(input()))

    await act(async () => {
      await result.current.start()
    })

    expect(writeText).toHaveBeenCalledWith(`${window.location.origin}/follow/w1`)
    expect(result.current.notice).toBe('Link copied. Paste it to a friend.')
  })

  it('offers a retry when neither sharing nor copying works', async () => {
    walkServer()
    vi.stubGlobal('navigator', {})
    const { result } = renderHook(() => useShareWalk(input()))

    await act(async () => {
      await result.current.start()
    })

    expect(result.current.phase).toBe('live')
    expect(result.current.notice).toBe(`Couldn't open sharing. Tap Send link to try again.`)
  })

  it('re-sends the same link without creating another walk', async () => {
    const fetcher = walkServer()
    const { result } = renderHook(() => useShareWalk(input()))
    await act(async () => {
      await result.current.start()
    })

    await act(async () => {
      await result.current.resend()
    })

    expect(fetcher.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1)
    expect(share).toHaveBeenCalledTimes(2)
  })

  it('resend starts sharing when not live yet', async () => {
    const fetcher = walkServer()
    const { result } = renderHook(() => useShareWalk(input()))

    await act(async () => {
      await result.current.resend()
    })

    expect(fetcher.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1)
    expect(result.current.phase).toBe('live')
  })

  it('simulates sharing locally in demo mode (no network)', async () => {
    const fetcher = walkServer()
    const { result, unmount } = renderHook(() => useShareWalk(input({ demo: true })))

    await act(async () => {
      await result.current.start()
    })
    await flush(SHARE_UPDATE_MS * 2)
    unmount()

    expect(fetcher).not.toHaveBeenCalled()
    expect(result.current.phase).toBe('live')
    expect(result.current.followUrl).toMatch(/\/follow\/demo[\w-]+\?demo=1$/)
    expect(share).toHaveBeenCalled()
  })

  it('cannot start without a destination', async () => {
    const fetcher = walkServer()
    const { result } = renderHook(() => useShareWalk(input({ destination: null })))

    await act(async () => {
      await result.current.start()
    })

    expect(fetcher).not.toHaveBeenCalled()
    expect(result.current.phase).toBe('idle')
  })

  it('clears a notice', async () => {
    walkServer()
    const { result } = renderHook(() => useShareWalk(input()))
    await act(async () => {
      await result.current.start()
    })

    act(() => result.current.clearNotice())

    expect(result.current.notice).toBeNull()
  })
})
