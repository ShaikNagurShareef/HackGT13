import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api } from '../api/client'
import { FrameSet } from '../frames/frameStore'
import { routes, segment } from '../test/fixtures'
import { DEFAULT_STATE, type ViewState } from '../state/urlState'
import { useDemoMode } from './useDemoMode'
import { useLiveCondition } from './useLiveCondition'
import { useRiskFrames } from './useRiskFrames'
import { useRoutes } from './useRoutes'
import { useSegmentDetail } from './useSegmentDetail'

const KLAUS = { lat: 33.7771, lon: -84.3962, label: 'Klaus' }
const MIDTOWN = { lat: 33.781, lon: -84.3863, label: 'Midtown MARTA' }
const TRIP = { from: KLAUS, to: MIDTOWN, depart: 'now', cond: 'wet' as const }

afterEach(() => vi.restoreAllMocks())

describe('useRoutes', () => {
  it('stays empty without both ends', () => {
    const onError = vi.fn()
    const { result } = renderHook(() => useRoutes({ ...TRIP, from: null }, { onError, onOutside: vi.fn(), onLoaded: vi.fn() }))
    expect(result.current).toEqual({ routes: null, loading: false })
  })

  it('loads routes for a trip and reports them', async () => {
    const r = routes()
    vi.spyOn(api, 'routes').mockResolvedValue(r)
    const onLoaded = vi.fn()
    const { result } = renderHook(() => useRoutes(TRIP, { onError: vi.fn(), onOutside: vi.fn(), onLoaded }))

    expect(result.current.loading).toBe(true)
    await waitFor(() => expect(result.current.routes).toBe(r))
    expect(result.current.loading).toBe(false)
    expect(onLoaded).toHaveBeenCalledWith(r)
    expect(api.routes).toHaveBeenCalledWith(KLAUS, MIDTOWN, 'now', 'wet')
  })

  it('surfaces errors and hands an out-of-coverage destination to the area fallback', async () => {
    vi.spyOn(api, 'routes').mockRejectedValue(new ApiError('OUT_OF_COVERAGE', 'PathPro covers the City of Atlanta.'))
    const onError = vi.fn()
    const onOutside = vi.fn()
    const { result } = renderHook(() => useRoutes(TRIP, { onError, onOutside, onLoaded: vi.fn() }))

    await waitFor(() => expect(onError).toHaveBeenLastCalledWith('PathPro covers the City of Atlanta.'))
    expect(onOutside).toHaveBeenCalledWith(MIDTOWN)
    expect(result.current.loading).toBe(false)
  })

  it('uses a generic message for unexpected failures', async () => {
    vi.spyOn(api, 'routes').mockRejectedValue(new Error('boom'))
    const onError = vi.fn()
    renderHook(() => useRoutes(TRIP, { onError, onOutside: vi.fn(), onLoaded: vi.fn() }))
    await waitFor(() => expect(onError).toHaveBeenLastCalledWith('Could not compute routes.'))
  })
})

describe('useSegmentDetail', () => {
  it('loads the selected street and clears when deselected', async () => {
    vi.spyOn(api, 'segment').mockResolvedValue(segment())
    const onError = vi.fn()
    const { result, rerender } = renderHook(({ seg }) => useSegmentDetail(seg, 'now', 'wet', onError), {
      initialProps: { seg: 11 as number | null },
    })

    await waitFor(() => expect(result.current?.seg_id).toBe(11))
    rerender({ seg: null })
    expect(result.current).toBeNull()
  })

  it('reports a failure', async () => {
    vi.spyOn(api, 'segment').mockRejectedValue(new Error('x'))
    const onError = vi.fn()
    renderHook(() => useSegmentDetail(3, 'now', 'dry', onError))
    await waitFor(() => expect(onError).toHaveBeenCalledWith('Could not load details.'))
  })
})

describe('useLiveCondition', () => {
  it('reads live weather only in live mode, with an honest fallback', async () => {
    const live = vi.spyOn(api, 'liveConditions').mockResolvedValue({ cond: 'wet', source: 'live', label: 'Rain · live' })
    const { result, rerender } = renderHook(({ cond }) => useLiveCondition(cond), {
      initialProps: { cond: 'live' as 'live' | 'dry' | 'wet' },
    })
    await waitFor(() => expect(result.current).toEqual({ wet: true, label: 'Rain · live' }))

    rerender({ cond: 'dry' })
    expect(live).toHaveBeenCalledTimes(1)

    live.mockRejectedValue(new Error('down'))
    const second = renderHook(() => useLiveCondition('live'))
    await waitFor(() => expect(second.result.current.label).toMatch(/Live weather unavailable/))
  })
})

describe('useRiskFrames', () => {
  const set = new FrameSet(new Uint8Array(24 * 2), 2)

  it('loads the frame set for the day and condition, prefetching the day', async () => {
    const store = { get: vi.fn().mockResolvedValue(set), prefetch: vi.fn() }
    const { result } = renderHook(() => useRiskFrames(store, 'friday', 'wet', true, vi.fn(), 'failed'))

    await waitFor(() => expect(result.current).toBe(set))
    expect(store.prefetch).toHaveBeenCalledWith('friday')
    expect(store.get).toHaveBeenCalledWith('friday', 'wet')
  })

  it('does nothing while disabled and reports load failures', async () => {
    const store = { get: vi.fn().mockRejectedValue(new Error('404')), prefetch: vi.fn() }
    const onError = vi.fn()
    const { rerender } = renderHook(({ on }) => useRiskFrames(store, 'friday', 'dry', on, onError, 'City Pulse frames could not load.'), {
      initialProps: { on: false },
    })
    expect(store.get).not.toHaveBeenCalled()

    rerender({ on: true })
    await waitFor(() => expect(onError).toHaveBeenCalledWith('City Pulse frames could not load.'))
  })
})

describe('useDemoMode (DEMO-01/02)', () => {
  function keyed(key: string) {
    act(() => void window.dispatchEvent(new KeyboardEvent('keydown', { key })))
  }

  it('opens the scripted route and wires the T / R / D shortcuts', () => {
    const update = vi.fn()
    const view: ViewState = { ...DEFAULT_STATE, demo: true }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 404 })))
    renderHook(() => useDemoMode(true, view, update, vi.fn()))

    expect(update).toHaveBeenCalledWith(expect.objectContaining({ cond: 'wet', depart: '2026-09-25T22:30' }))
    keyed('t')
    expect(update).toHaveBeenLastCalledWith({ hour: 22 })
    keyed('r')
    expect(update).toHaveBeenLastCalledWith({ cond: 'wet' })
    keyed('d')
    expect(update).toHaveBeenLastCalledWith(expect.objectContaining({ seg: null, cond: 'wet' }))
    vi.unstubAllGlobals()
  })

  it('is inert outside demo mode', () => {
    const update = vi.fn()
    renderHook(() => useDemoMode(false, DEFAULT_STATE, update, vi.fn()))
    keyed('t')
    expect(update).not.toHaveBeenCalled()
  })
})
