import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Geolocation } from '../hooks/useGeolocation'
import type { Navigation } from '../hooks/useNavigation'
import type { Routines } from '../hooks/useRoutines'
import type { TripPlanner } from '../hooks/useTripPlanner'
import type { GeoStatus } from '../lib/origin'
import { route, routes } from '../test/fixtures'
import { DEFAULT_STATE, type ViewState } from '../state/urlState'
import { useTripActions } from './useTripActions'

const KLAUS = { lat: 33.7771, lon: -84.3962, label: 'Klaus Building' }
const MIDTOWN = { lat: 33.781, lon: -84.3863, label: 'Midtown MARTA' }

function setup(over: { view?: Partial<ViewState>; status?: GeoStatus; originPlace?: typeof KLAUS | null; withRoute?: boolean } = {}) {
  const view = { ...DEFAULT_STATE, ...over.view }
  const update = vi.fn()
  const onNotice = vi.fn()
  const geo: Geolocation = { status: over.status ?? 'prompt', position: null, error: null, request: vi.fn() }
  const planner: TripPlanner = {
    origin: { place: over.originPlace ?? null, status: over.originPlace ? 'ready' : 'ask' },
    pickDestination: vi.fn(),
    pickOrigin: vi.fn(),
    swap: vi.fn(),
    clear: vi.fn(),
  }
  const routines: Routines = { suggestions: [], recents: [], saved: {}, record: vi.fn(), setSaved: vi.fn(), clear: vi.fn() }
  const nav = { start: vi.fn(), end: vi.fn() } as unknown as Navigation
  const hook = renderHook(() =>
    useTripActions({
      onNotice,
      view,
      update,
      geo,
      planner,
      routines,
      nav,
      routes: over.withRoute ? routes() : null,
      selectedRoute: over.withRoute ? route() : null,
    }),
  )
  return { ...hook, update, onNotice, geo, planner, routines, nav }
}

describe('useTripActions', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('asks for location politely when "Where to?" opens, and opens the search sheet', () => {
    const { result, geo } = setup()
    act(() => result.current.openSearch('to'))

    expect(geo.request).toHaveBeenCalled()
    expect(result.current.panel).toEqual({ kind: 'search', field: 'to' })
    expect(result.current.searchNote('to')).toBeNull()
    expect(result.current.searchNote('from')).toMatch(/Pick a starting point/)
  })

  it('routes picks by field: destination, start, and saved places', () => {
    const { result, planner, routines } = setup()

    act(() => result.current.pickPlace('to', MIDTOWN))
    act(() => result.current.pickPlace('from', KLAUS))
    act(() => result.current.editSaved('home'))
    expect(result.current.panel).toEqual({ kind: 'search', field: 'home' })
    act(() => result.current.pickPlace('home', KLAUS))

    expect(planner.pickDestination).toHaveBeenCalledWith(MIDTOWN)
    expect(planner.pickOrigin).toHaveBeenCalledWith(KLAUS)
    expect(routines.setSaved).toHaveBeenCalledWith('home', KLAUS)
    expect(result.current.panel).toEqual({ kind: 'search', field: 'to' })
  })

  it('plans a suggestion from its own start or from GPS', () => {
    const { result, update, planner } = setup()

    act(() => result.current.planSuggestion({ from: KLAUS, to: MIDTOWN, reason: 'r', kind: 'routine', score: 2 }))
    act(() => result.current.planSuggestion({ from: null, to: MIDTOWN, reason: 'r', kind: 'return', score: 2 }))

    expect(update).toHaveBeenCalledWith({ from: KLAUS, to: MIDTOWN, seg: null })
    expect(planner.pickDestination).toHaveBeenCalledWith(MIDTOWN)
    expect(result.current.panel).toBeNull()
  })

  it('"Your location" uses the fix, or asks for one', () => {
    const ready = setup({ originPlace: KLAUS })
    act(() => ready.result.current.startFromMyLocation())
    expect(ready.planner.pickOrigin).toHaveBeenCalledWith(KLAUS)

    const asking = setup()
    act(() => asking.result.current.startFromMyLocation())
    expect(asking.update).toHaveBeenCalledWith({ from: null })
    expect(asking.geo.request).toHaveBeenCalled()
  })

  it('locate recentres, or explains when location is off', () => {
    const on = setup()
    act(() => on.result.current.locate())
    expect(on.geo.request).toHaveBeenCalled()
    expect(on.result.current.recenterKey).toBe(1)

    const off = setup({ status: 'denied' })
    act(() => off.result.current.locate())
    expect(off.onNotice).toHaveBeenCalledWith(expect.stringMatching(/Location is off/))
  })

  it('Start records the trip and previews when GPS is unavailable', () => {
    const { result, routines, nav } = setup({ view: { from: KLAUS, to: MIDTOWN }, withRoute: true })
    act(() => result.current.start())

    expect(routines.record).toHaveBeenCalledWith(expect.objectContaining({ from: KLAUS, to: MIDTOWN }))
    expect(nav.start).toHaveBeenCalledWith('preview')
  })

  it('Start clears stale notices and never records a start as "Your location"', () => {
    const here = { lat: 33.7766, lon: -84.3963, label: 'Your location' }
    const { result, routines, onNotice } = setup({ view: { from: here, to: MIDTOWN }, withRoute: true })
    act(() => result.current.start())

    expect(onNotice).toHaveBeenCalledWith(null)
    expect(routines.record).toHaveBeenCalledWith(expect.objectContaining({ from: { ...here, label: 'Klaus Building' } }))
  })

  it('Start does nothing without a route', () => {
    const { result, nav } = setup()
    act(() => result.current.start())
    expect(nav.start).not.toHaveBeenCalled()
  })

  it('shares the trip link and reports a copy', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    const { result } = setup({ view: { from: KLAUS, to: MIDTOWN }, withRoute: true })

    await act(() => result.current.share())

    expect(writeText).toHaveBeenCalledWith(expect.stringContaining('to=33.78100'))
    expect(result.current.shareStatus).toBe('Link copied')
  })

  it('finishing a trip ends navigation and returns home', () => {
    const { result, nav, planner } = setup()
    act(() => result.current.finishTrip())
    expect(nav.end).toHaveBeenCalled()
    expect(planner.clear).toHaveBeenCalled()
  })

  it('opens Ask PathPro with or without an on-screen context', () => {
    const { result } = setup()
    const context = { kind: 'route', route_key: 'rk-123' } as const

    act(() => result.current.openAsk(context, 'this route'))
    expect(result.current.panel).toEqual({ kind: 'ask', context, contextLabel: 'this route' })

    act(() => result.current.openAsk())
    expect(result.current.panel).toEqual({ kind: 'ask' })
  })
})
