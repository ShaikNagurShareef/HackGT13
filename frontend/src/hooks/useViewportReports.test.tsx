import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { report } from '../test/fixtures'
import { DEBOUNCE_MS, useViewportReports } from './useViewportReports'

const JSON_HEADERS = { headers: { 'content-type': 'application/json' } }
const VIEW: [number, number, number, number] = [-84.4, 33.77, -84.38, 33.79]

function respond(body: unknown) {
  const fetcher = vi.fn(async () => new Response(JSON.stringify(body), JSON_HEADERS))
  vi.stubGlobal('fetch', fetcher)
  return fetcher
}

async function settle(ms = DEBOUNCE_MS) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms)
  })
}

describe('useViewportReports', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('debounces map moves into one viewport request', async () => {
    const fetcher = respond({ success: true, data: [report()] })
    const { result } = renderHook(() => useViewportReports(true))

    act(() => {
      result.current.onViewport([-84.5, 33.7, -84.45, 33.75])
      result.current.onViewport(VIEW)
    })
    await settle()

    expect(fetcher).toHaveBeenCalledTimes(1)
    expect((fetcher.mock.calls[0] as unknown as [string])[0]).toContain('/api/reports?bbox=-84.40000,33.77000')
    expect(result.current.reports).toHaveLength(1)
    expect(result.current.available).toBe(true)
  })

  it('skips the request when zoomed out past the viewport limit', async () => {
    const fetcher = respond({ success: true, data: [report()] })
    const { result } = renderHook(() => useViewportReports(true))

    act(() => result.current.onViewport([-84.8, 33.5, -84.1, 34.0]))
    await settle()

    expect(fetcher).not.toHaveBeenCalled()
    expect(result.current.reports).toEqual([])
  })

  it('turns itself off when the service is unavailable', async () => {
    const fetcher = respond({ success: false, error: { code: 'REPORTS_UNAVAILABLE', message: 'x' } })
    const { result } = renderHook(() => useViewportReports(true))

    act(() => result.current.onViewport(VIEW))
    await settle()
    act(() => result.current.onViewport(VIEW))
    await settle()

    expect(fetcher).toHaveBeenCalledTimes(1)
    expect(result.current.available).toBe(false)
    expect(result.current.reports).toEqual([])
  })

  it('keeps trying after a transient network error', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('offline'))))
    const { result } = renderHook(() => useViewportReports(true))

    act(() => result.current.onViewport(VIEW))
    await settle()

    expect(result.current.available).toBe(true)
    const fetcher = respond({ success: true, data: [report()] })
    act(() => result.current.refresh())
    await settle(0)
    expect(fetcher).toHaveBeenCalledTimes(1)
    expect(result.current.reports).toHaveLength(1)
  })

  it('keeps the last good markers through a transient error', async () => {
    respond({ success: true, data: [report()] })
    const { result } = renderHook(() => useViewportReports(true))
    act(() => result.current.onViewport(VIEW))
    await settle()

    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('offline'))))
    act(() => result.current.refresh())
    await settle(0)

    expect(result.current.reports).toHaveLength(1)
    expect(result.current.available).toBe(true)
  })

  it('cancels a pending fetch when switched off (e.g. City Pulse)', async () => {
    const fetcher = respond({ success: true, data: [report()] })
    const { result, rerender } = renderHook(({ on }) => useViewportReports(on), { initialProps: { on: true } })

    act(() => result.current.onViewport(VIEW))
    rerender({ on: false })
    await settle()

    expect(fetcher).not.toHaveBeenCalled()
  })

  it('does nothing while disabled (demo mode, City Pulse)', async () => {
    const fetcher = respond({ success: true, data: [report()] })
    const { result } = renderHook(() => useViewportReports(false))

    act(() => {
      result.current.onViewport(VIEW)
      result.current.refresh()
    })
    await settle()

    expect(fetcher).not.toHaveBeenCalled()
    expect(result.current.available).toBe(false)
  })
})
