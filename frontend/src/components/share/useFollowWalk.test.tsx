import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { sharedWalk } from '../../test/walkFixtures'
import { FOLLOW_MAX_BACKOFF_MS, FOLLOW_POLL_MS, useFollowWalk } from './useFollowWalk'

const JSON_HEADERS = { headers: { 'content-type': 'application/json' } }

function reply(body: unknown) {
  return new Response(JSON.stringify(body), JSON_HEADERS)
}

async function flush(ms = 0) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms)
  })
}

describe('useFollowWalk', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('loads the walk and polls about every five seconds', async () => {
    const fetcher = vi.fn(async () => reply({ success: true, data: sharedWalk() }))
    vi.stubGlobal('fetch', fetcher)
    const { result } = renderHook(() => useFollowWalk('w1', false))
    expect(result.current.state).toBe('loading')

    await flush()
    expect(result.current.state).toBe('live')
    expect(result.current.walk?.destination.label).toBe('Midtown MARTA')

    fetcher.mockImplementation(async () => reply({ success: true, data: sharedWalk({ status: 'arrived' }) }))
    await flush(FOLLOW_POLL_MS)

    expect(FOLLOW_POLL_MS).toBe(5000)
    expect(fetcher).toHaveBeenCalledTimes(2)
    expect(result.current.walk?.status).toBe('arrived')
  })

  it('stops polling once the walk has ended', async () => {
    const fetcher = vi.fn(async () => reply({ success: true, data: sharedWalk({ status: 'ended' }) }))
    vi.stubGlobal('fetch', fetcher)
    const { result } = renderHook(() => useFollowWalk('w1', false))

    await flush()
    await flush(FOLLOW_POLL_MS * 3)

    expect(result.current.walk?.status).toBe('ended')
    expect(fetcher).toHaveBeenCalledTimes(1)
  })

  it('shows an expired link and stops polling', async () => {
    const fetcher = vi.fn(async () => reply({ success: false, error: { code: 'WALK_NOT_FOUND', message: 'gone' } }))
    vi.stubGlobal('fetch', fetcher)
    const { result } = renderHook(() => useFollowWalk('w1', false))

    await flush()
    await flush(FOLLOW_POLL_MS * 3)

    expect(result.current.state).toBe('expired')
    expect(fetcher).toHaveBeenCalledTimes(1)
  })

  it('backs off on errors, keeps the last position, and recovers', async () => {
    const fetcher = vi.fn(async () => reply({ success: true, data: sharedWalk() }))
    vi.stubGlobal('fetch', fetcher)
    const { result } = renderHook(() => useFollowWalk('w1', false))
    await flush()

    fetcher.mockRejectedValue(new TypeError('offline'))
    await flush(FOLLOW_POLL_MS)
    expect(result.current.reconnecting).toBe(true)
    expect(result.current.walk).not.toBeNull()
    expect(fetcher).toHaveBeenCalledTimes(2)

    await flush(FOLLOW_POLL_MS) // backing off: the next try waits twice as long
    expect(fetcher).toHaveBeenCalledTimes(2)
    fetcher.mockImplementation(async () => reply({ success: true, data: sharedWalk() }))
    await flush(FOLLOW_POLL_MS)

    expect(fetcher).toHaveBeenCalledTimes(3)
    expect(result.current.reconnecting).toBe(false)
    expect(result.current.state).toBe('live')
  })

  it('caps the backoff', async () => {
    const fetcher = vi.fn(async () => Promise.reject(new TypeError('offline')))
    vi.stubGlobal('fetch', fetcher)
    const { result } = renderHook(() => useFollowWalk('w1', false))

    await flush()
    await flush(FOLLOW_MAX_BACKOFF_MS * 6)

    expect(result.current.state).toBe('error')
    expect(fetcher.mock.calls.length).toBeGreaterThanOrEqual(6)
  })

  it('never calls the network in demo mode', async () => {
    const fetcher = vi.fn()
    vi.stubGlobal('fetch', fetcher)
    const { result } = renderHook(() => useFollowWalk('w1', true))

    await flush(FOLLOW_POLL_MS * 2)

    expect(result.current.state).toBe('demo')
    expect(fetcher).not.toHaveBeenCalled()
  })

  it('stops polling on unmount', async () => {
    const fetcher = vi.fn(async () => reply({ success: true, data: sharedWalk() }))
    vi.stubGlobal('fetch', fetcher)
    const { unmount } = renderHook(() => useFollowWalk('w1', false))
    await flush()

    unmount()
    await flush(FOLLOW_POLL_MS * 3)

    expect(fetcher).toHaveBeenCalledTimes(1)
  })
})
