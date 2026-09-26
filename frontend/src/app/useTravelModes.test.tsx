import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import type { ModeInfo } from '../api/schemas'
import { meta, route, routes } from '../test/fixtures'
import { DEFAULT_STATE, type ViewState } from '../state/urlState'
import { useHandoff, useTravelModes } from './useTravelModes'

const BIKE: ModeInfo = { key: 'bike', label: 'Bike', available: true, speed_kmh: 18, network: 'ride', static_prefix: 'ride_' }
const withBike = () => ({ ...meta(), modes: [BIKE] })

afterEach(() => vi.restoreAllMocks())

describe('useTravelModes', () => {
  it('uses an available URL mode with its speed, and switches modes through the URL', () => {
    const update = vi.fn()
    const { result } = renderHook(() =>
      useTravelModes({ meta: withBike(), view: { ...DEFAULT_STATE, mode: 'bike' }, update, onNotice: vi.fn() }),
    )

    expect(result.current.mode).toBe('bike')
    expect(result.current.info.network).toBe('ride')
    expect(result.current.speedMps).toBeCloseTo(5)
    act(() => result.current.onMode('walk'))
    expect(update).toHaveBeenCalledWith({ mode: 'walk', seg: null })
  })

  it('falls back to Walk, with a friendly notice, when the mode is not offered here', () => {
    const update = vi.fn()
    const onNotice = vi.fn()
    const view: ViewState = { ...DEFAULT_STATE, mode: 'scooter' }
    const { result } = renderHook(() => useTravelModes({ meta: withBike(), view, update, onNotice }))

    expect(result.current.mode).toBe('walk')
    expect(onNotice).toHaveBeenCalledWith(expect.stringContaining("Scooter routes aren't available"))
    expect(update).toHaveBeenCalledWith({ mode: 'walk', seg: null })
  })

  it('keeps the URL mode until meta arrives, and handles MODE_UNAVAILABLE from the router', () => {
    const update = vi.fn()
    const onNotice = vi.fn()
    const { result } = renderHook(() => useTravelModes({ meta: null, view: { ...DEFAULT_STATE, mode: 'bike' }, update, onNotice }))

    expect(result.current.mode).toBe('bike')
    act(() => result.current.onModeUnavailable('bike'))
    expect(onNotice).toHaveBeenCalledWith(expect.stringContaining("Bike routes aren't available"))
    expect(update).toHaveBeenCalledWith({ mode: 'walk', seg: null })
  })
})

describe('useHandoff', () => {
  const FROM = { lat: 33.7716, lon: -84.3935, label: 'West of North Ave' }
  const TO = { lat: 33.7925, lon: -84.3876, label: 'North of Arts Center' }
  const longWalk = routes({ fastest: route({ duration_s: 40 * 60, distance_m: 3500 }) })
  const handlers = { onPlanStation: vi.fn(), onTryMode: vi.fn() }

  it('offers MARTA and a ride for a long walk, loading stations only then', async () => {
    vi.spyOn(api, 'transitStations').mockResolvedValue([
      { name: 'North Avenue', lat: 33.7716, lon: -84.3872 },
      { name: 'Arts Center', lat: 33.7893, lon: -84.3876 },
    ])
    const { result } = renderHook(() =>
      useHandoff({ routes: longWalk, from: FROM, to: TO, options: [{ ...BIKE, speed_kmh: 15 }], ...handlers }),
    )

    expect(result.current?.ride).toEqual({ mode: 'bike', minutes: 14 })
    await waitFor(() => expect(result.current?.marta?.board.station.name).toBe('North Avenue'))
  })

  it('is quiet for short walks and ride routes', () => {
    const spy = vi.spyOn(api, 'transitStations')
    const short = renderHook(() => useHandoff({ routes: routes(), from: FROM, to: TO, options: [BIKE], ...handlers }))
    const ride = renderHook(() => useHandoff({ routes: { ...longWalk, mode: 'bike' }, from: FROM, to: TO, options: [BIKE], ...handlers }))

    expect(short.result.current).toBeNull()
    expect(ride.result.current).toBeNull()
    expect(spy).not.toHaveBeenCalled()
  })
})
