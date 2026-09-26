import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { helpPoint, safetyHex, safetyMeta } from '../test/fixtures'
import { DEBOUNCE_MS, useSafetyData } from './useSafetyData'

const JSON_HEADERS = { headers: { 'content-type': 'application/json' } }
const VIEW: [number, number, number, number] = [-84.4, 33.77, -84.38, 33.79]
const WIDE: [number, number, number, number] = [-84.8, 33.5, -84.1, 34.0]

type Handler = (url: string) => unknown

/** Route each request by path so meta, hexes, and help points can answer differently. */
function serve(handler: Handler) {
  const fetcher = vi.fn(async (url: string) => new Response(JSON.stringify(handler(url)), JSON_HEADERS))
  vi.stubGlobal('fetch', fetcher)
  return fetcher
}

const ok = (data: unknown) => ({ success: true, data })
const standard: Handler = (url) => {
  if (url.includes('/safety/meta')) return ok(safetyMeta())
  if (url.includes('/safety/hexes')) return ok([safetyHex()])
  return ok([helpPoint()])
}

function calls(fetcher: ReturnType<typeof serve>, path: string): string[] {
  return fetcher.mock.calls.map((c) => (c as unknown as [string])[0]).filter((u) => u.includes(path))
}

async function settle(ms = DEBOUNCE_MS) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms)
  })
}

describe('useSafetyData', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('probes the safety meta once and reports availability', async () => {
    const fetcher = serve(standard)
    const { result } = renderHook(() => useSafetyData(false, 21))
    expect(result.current.status).toBe('checking')

    await settle(0)

    expect(result.current.available).toBe(true)
    expect(result.current.meta?.data_through).toBe('2026-09-19')
    expect(calls(fetcher, '/safety/meta')).toHaveLength(1)
  })

  it('hides itself when the server has no safety layer (503 on older bundles)', async () => {
    serve(() => ({ success: false, data: null, error: { code: 'SAFETY_UNAVAILABLE', message: 'x' } }))
    const { result } = renderHook(() => useSafetyData(true, 21))

    await settle(0)

    expect(result.current.status).toBe('off')
    expect(result.current.available).toBe(false)
  })

  it('loads hexes and help points for the debounced viewport while active', async () => {
    const fetcher = serve(standard)
    const { result } = renderHook(() => useSafetyData(true, 21))
    await settle(0)

    act(() => {
      result.current.onViewport([-84.5, 33.7, -84.45, 33.75])
      result.current.onViewport(VIEW)
    })
    await settle()

    expect(calls(fetcher, '/safety/hexes')).toEqual(['/api/safety/hexes?bbox=-84.40000,33.77000,-84.38000,33.79000&hour=21'])
    expect(calls(fetcher, '/safety/help-points')).toHaveLength(1)
    expect(result.current.hexes).toHaveLength(1)
    expect(result.current.helpPoints).toHaveLength(1)
  })

  it('remembers the viewport while inactive and loads it when switched on', async () => {
    const fetcher = serve(standard)
    const { result, rerender } = renderHook(({ on }) => useSafetyData(on, 21), { initialProps: { on: false } })
    await settle(0)

    act(() => result.current.onViewport(VIEW))
    await settle()
    expect(calls(fetcher, '/safety/hexes')).toHaveLength(0)
    expect(result.current.hexes).toEqual([])

    rerender({ on: true })
    await settle(0)
    expect(calls(fetcher, '/safety/hexes')).toHaveLength(1)
    expect(result.current.hexes).toHaveLength(1)
  })

  it('refetches hexes only when the Risk Tides hour crosses into another day part', async () => {
    const fetcher = serve(standard)
    const { result, rerender } = renderHook(({ hour }) => useSafetyData(true, hour), { initialProps: { hour: 18 } })
    await settle(0)
    act(() => result.current.onViewport(VIEW))
    await settle()

    rerender({ hour: 19 }) // still evening
    await settle(0)
    expect(calls(fetcher, '/safety/hexes')).toHaveLength(1)

    rerender({ hour: 23 }) // late night
    await settle(0)
    expect(calls(fetcher, '/safety/hexes')).toHaveLength(2)
    expect(calls(fetcher, '/safety/hexes')[1]).toContain('&hour=23')
    expect(calls(fetcher, '/safety/help-points')).toHaveLength(1)
  })

  it('asks the walker to zoom in instead of requesting a too-wide viewport', async () => {
    const fetcher = serve(standard)
    const { result } = renderHook(() => useSafetyData(true, 21))
    await settle(0)

    act(() => result.current.onViewport(WIDE))
    await settle()

    expect(calls(fetcher, '/safety/hexes')).toHaveLength(0)
    expect(result.current.tooWide).toBe(true)
    expect(result.current.hexes).toEqual([])
  })

  it('keeps the last good hexes through a transient error, and turns off on an unavailable code', async () => {
    let mode: 'ok' | 'offline' | 'gone' = 'ok'
    const fetcher = vi.fn(async (url: string) => {
      if (mode === 'offline' && !url.includes('/meta')) throw new TypeError('offline')
      if (mode === 'gone' && !url.includes('/meta')) {
        return new Response(JSON.stringify({ success: false, error: { code: 'SAFETY_UNAVAILABLE', message: 'x' } }), JSON_HEADERS)
      }
      return new Response(JSON.stringify(standard(url)), JSON_HEADERS)
    })
    vi.stubGlobal('fetch', fetcher)
    const { result } = renderHook(() => useSafetyData(true, 21))
    await settle(0)
    act(() => result.current.onViewport(VIEW))
    await settle()

    mode = 'offline'
    act(() => result.current.onViewport([-84.41, 33.77, -84.39, 33.79]))
    await settle()
    expect(result.current.hexes).toHaveLength(1)
    expect(result.current.available).toBe(true)

    mode = 'gone'
    act(() => result.current.onViewport(VIEW))
    await settle()
    expect(result.current.available).toBe(false)
    expect(result.current.hexes).toEqual([])
  })
})
