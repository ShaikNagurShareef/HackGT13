import { renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api } from '../api/client'
import type { ModeInfo } from '../api/schemas'
import { meta } from '../test/fixtures'
import { useRideNetwork } from './useRideNetwork'
import { useTransitStations } from './useTransitStations'

const BIKE: ModeInfo = { key: 'bike', label: 'Bike', available: true, speed_kmh: 15, network: 'ride', static_prefix: 'ride_' }
const WALK: ModeInfo = { key: 'walk', label: 'Walk', available: true, speed_kmh: 4.7, network: 'walk', static_prefix: '' }

const RIDE_GEOJSON = {
  features: [
    { id: 0, geometry: { coordinates: [[-84.39, 33.77], [-84.38, 33.77]] }, properties: { n: 'Tenth Street' } },
    { id: 1, geometry: { coordinates: [[-84.38, 33.77], [-84.38, 33.78]] }, properties: { n: 'Spring Street' } },
  ],
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('useRideNetwork', () => {
  it('stays empty for walking', () => {
    const fetcher = vi.fn()
    vi.stubGlobal('fetch', fetcher)
    const { result } = renderHook(() => useRideNetwork(meta(), WALK, vi.fn()))

    expect(result.current).toBeNull()
    expect(fetcher).not.toHaveBeenCalled()
  })

  it('loads the ride geometry under the ride prefix and a ride frame store', async () => {
    const fetcher = vi.fn(async (url: string) => {
      if (url.endsWith('.geojson')) return new Response(JSON.stringify(RIDE_GEOJSON))
      return new Response(new Uint8Array(24 * 2).buffer)
    })
    vi.stubGlobal('fetch', fetcher)
    const { result } = renderHook(() => useRideNetwork(meta(), BIKE, vi.fn()))

    await waitFor(() => expect(result.current).not.toBeNull())
    expect(fetcher).toHaveBeenCalledWith('/static/pp-test/ride_segments.geojson')
    expect(result.current?.segments.map((s) => s.name)).toEqual(['Tenth Street', 'Spring Street'])
    const frames = await result.current!.frames.get('weekday', 'dry')
    expect(frames.nSegments).toBe(2)
    expect(fetcher).toHaveBeenCalledWith('/static/pp-test/ride_frames_weekday_dry.bin')
  })

  it('reports a failed ride network download', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('nope', { status: 404 })))
    const onError = vi.fn()
    renderHook(() => useRideNetwork(meta(), BIKE, onError))

    await waitFor(() => expect(onError).toHaveBeenCalledWith('The bike & scooter risk map could not load.'))
  })
})

describe('useTransitStations', () => {
  it('loads stations once, only when needed', async () => {
    const spy = vi.spyOn(api, 'transitStations').mockResolvedValue([{ name: 'North Ave', lat: 33.77, lon: -84.38 }])
    const { result, rerender } = renderHook(({ on }) => useTransitStations(on), { initialProps: { on: false } })

    expect(result.current).toEqual([])
    expect(spy).not.toHaveBeenCalled()
    rerender({ on: true })
    await waitFor(() => expect(result.current).toHaveLength(1))
    rerender({ on: false })
    rerender({ on: true })
    expect(spy).toHaveBeenCalledTimes(1)
  })

  it('hides the MARTA card when stations are unavailable', async () => {
    const spy = vi.spyOn(api, 'transitStations').mockRejectedValue(new ApiError('NOT_FOUND', 'x'))
    const { result } = renderHook(() => useTransitStations(true))

    await waitFor(() => expect(spy).toHaveBeenCalled())
    expect(result.current).toEqual([])
  })
})
