import { act, renderHook } from '@testing-library/react'
import { StrictMode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { SHARE_SESSION_KEY, loadShareSession, saveShareSession, type StoredShareSession } from '../lib/shareSession'
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

describe('useShareWalk session persistence', () => {
  const NOW = Date.parse('2026-09-27T02:45:00Z')
  const STORED: StoredShareSession = { ...CREATED, destination: DEST }
  let share: ReturnType<typeof vi.fn>

  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(NOW)
    share = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { share })
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    window.sessionStorage.clear()
    window.localStorage.clear()
  })

  async function startLive(over: Partial<ShareWalkInput> = {}) {
    const fetcher = walkServer()
    const hook = renderHook((p: ShareWalkInput) => useShareWalk(p), { initialProps: input(over) })
    await act(async () => {
      await hook.result.current.start()
    })
    return { fetcher, ...hook }
  }

  function failNextUpdates(fetcher: ReturnType<typeof walkServer>, code: string) {
    fetcher.mockImplementation(
      async () => new Response(JSON.stringify({ success: false, error: { code, message: 'x' } }), JSON_HEADERS),
    )
  }

  it('remembers the live walk for this tab only', async () => {
    await startLive()

    expect(loadShareSession()).toEqual(STORED)
    expect(JSON.stringify({ ...window.localStorage })).not.toContain('secret-token')
    expect(window.location.href).not.toContain('secret-token')
  })

  it('does not remember a simulated demo walk', async () => {
    await startLive({ demo: true })

    expect(window.sessionStorage.getItem(SHARE_SESSION_KEY)).toBeNull()
  })

  it('forgets the session when sharing stops', async () => {
    const { result } = await startLive()

    act(() => result.current.stop())

    expect(loadShareSession()).toBeNull()
  })

  it('forgets the session on arrival', async () => {
    const { rerender } = await startLive()

    rerender(input({ arrived: true }))
    await flush()

    expect(loadShareSession()).toBeNull()
  })

  it('forgets the session when navigation ends', async () => {
    const { fetcher, unmount } = await startLive()

    unmount()
    await flush()

    expect(loadShareSession()).toBeNull()
    expect(puts(fetcher).at(-1)).toMatchObject({ status: 'ended' })
  })

  it('forgets the session when the link has expired (404)', async () => {
    const { fetcher, result } = await startLive()
    failNextUpdates(fetcher, 'WALK_NOT_FOUND')

    await flush(SHARE_UPDATE_MS)

    expect(loadShareSession()).toBeNull()
    expect(result.current.phase).toBe('idle')
  })

  it('stops and forgets the session when the server refuses the token (403)', async () => {
    const { fetcher, result } = await startLive()
    failNextUpdates(fetcher, 'WALK_FORBIDDEN')

    await flush(SHARE_UPDATE_MS)

    expect(loadShareSession()).toBeNull()
    expect(result.current.phase).toBe('idle')
    expect(result.current.notice).toBe("This live link can't be updated anymore. Share again to start a new one.")
  })

  it('stops when the walk was already ended elsewhere', async () => {
    const { fetcher, result } = await startLive()
    fetcher.mockImplementation(
      async () =>
        new Response(JSON.stringify({ success: true, data: { ...sharedWalk({ status: 'ended' }), route: undefined } }), JSON_HEADERS),
    )

    await flush(SHARE_UPDATE_MS)

    expect(loadShareSession()).toBeNull()
    expect(result.current.phase).toBe('idle')
  })

  it('extends the stored expiry after each accepted update', async () => {
    await startLive()

    expect(loadShareSession()?.expires_at).toBe(sharedWalk().expires_at)
  })

  it('resumes a stored walk without creating a new one', async () => {
    saveShareSession(STORED)
    const fetcher = walkServer()

    const { result } = renderHook(() => useShareWalk(input({ resume: true })))
    await flush()

    expect(result.current.phase).toBe('live')
    expect(result.current.followUrl).toBe(`${window.location.origin}/follow/w1`)
    expect(fetcher.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(0)
    expect(puts(fetcher)[0]).toMatchObject({ owner_token: 'secret-token', lat: 33.7775, lon: -84.395, status: 'walking' })

    await flush(SHARE_UPDATE_MS)
    expect(puts(fetcher)).toHaveLength(2)
  })

  it('resumes under StrictMode without ending the walk', async () => {
    saveShareSession(STORED)
    const fetcher = walkServer()

    const { result } = renderHook(() => useShareWalk(input({ resume: true })), { wrapper: StrictMode })
    await flush(SHARE_UPDATE_MS)

    expect(result.current.phase).toBe('live')
    expect(puts(fetcher).map((b) => b.status)).not.toContain('ended')
    expect(loadShareSession()?.walk_id).toBe('w1')
  })

  it('does not resume a walk to a different destination', async () => {
    saveShareSession(STORED)
    const fetcher = walkServer()

    const { result } = renderHook(() =>
      useShareWalk(input({ resume: true, destination: { label: 'Georgia Aquarium', lat: 33.7634, lon: -84.3951 } })),
    )
    await flush()

    expect(result.current.phase).toBe('idle')
    expect(fetcher).not.toHaveBeenCalled()
  })

  it('does not resume in demo mode', async () => {
    saveShareSession(STORED)
    const fetcher = walkServer()

    const { result } = renderHook(() => useShareWalk(input({ resume: true, demo: true })))
    await flush()

    expect(result.current.phase).toBe('idle')
    expect(fetcher).not.toHaveBeenCalled()
  })

  it('keeps the stored walk going when told not to end it on unmount (hand-off)', async () => {
    saveShareSession(STORED)
    const fetcher = walkServer()

    const { unmount } = renderHook(() => useShareWalk(input({ resume: true, endOnUnmount: false })))
    await flush()
    unmount()
    await flush(SHARE_UPDATE_MS)

    expect(puts(fetcher).map((b) => b.status)).not.toContain('ended')
    expect(loadShareSession()?.walk_id).toBe('w1')
  })

  it('omits the ETA when it is unknown', async () => {
    const { fetcher } = await startLive({ remainingS: null })

    expect(puts(fetcher)[0]).not.toHaveProperty('eta_s')
  })

  it('never logs the owner token', async () => {
    const spies = (['log', 'info', 'warn', 'error', 'debug'] as const).map((m) => vi.spyOn(console, m))
    const { result, fetcher } = await startLive()
    failNextUpdates(fetcher, 'WALK_FORBIDDEN')
    await flush(SHARE_UPDATE_MS)
    act(() => result.current.stop())

    const logged = JSON.stringify(spies.flatMap((s) => s.mock.calls))
    expect(logged).not.toContain('secret-token')
    spies.forEach((s) => s.mockRestore())
  })
})
