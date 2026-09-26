import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useGeolocation } from './useGeolocation'

type Success = (p: GeolocationPosition) => void
type Failure = (e: GeolocationPositionError) => void

function fakeGeolocation() {
  const calls: { success: Success; failure: Failure }[] = []
  const geo = {
    watchPosition: vi.fn((success: Success, failure: Failure) => {
      calls.push({ success, failure })
      return calls.length
    }),
    clearWatch: vi.fn(),
    getCurrentPosition: vi.fn(),
  }
  return { geo, calls }
}

function fix(lat: number, lon: number, accuracy = 12, heading: number | null = null): GeolocationPosition {
  return {
    coords: { latitude: lat, longitude: lon, accuracy, heading, altitude: null, altitudeAccuracy: null, speed: null },
    timestamp: 1000,
  } as unknown as GeolocationPosition
}

function failure(code: number): GeolocationPositionError {
  return { code, message: 'x', PERMISSION_DENIED: 1, POSITION_UNAVAILABLE: 2, TIMEOUT: 3 } as GeolocationPositionError
}

function install(geo: unknown, permission?: PermissionState | 'throws') {
  Object.defineProperty(navigator, 'geolocation', { value: geo, configurable: true })
  const query =
    permission === 'throws'
      ? vi.fn().mockRejectedValue(new Error('unsupported'))
      : vi.fn().mockResolvedValue({ state: permission ?? 'prompt' })
  Object.defineProperty(navigator, 'permissions', { value: permission ? { query } : undefined, configurable: true })
  return query
}

describe('useGeolocation', () => {
  afterEach(() => {
    install(undefined)
  })

  it('reports unavailable when the device has no geolocation', () => {
    install(undefined)
    const { result } = renderHook(() => useGeolocation())

    expect(result.current.status).toBe('unavailable')
    act(() => result.current.request())
    expect(result.current.position).toBeNull()
  })

  it('does not ask for permission until request() is called', async () => {
    const { geo, calls } = fakeGeolocation()
    install(geo, 'prompt')
    const { result } = renderHook(() => useGeolocation())

    await waitFor(() => expect(result.current.status).toBe('prompt'))
    expect(geo.watchPosition).not.toHaveBeenCalled()

    act(() => result.current.request())
    expect(result.current.status).toBe('locating')
    act(() => calls[0].success(fix(33.7766, -84.3963, 9, 90)))

    expect(result.current.status).toBe('granted')
    expect(result.current.position).toMatchObject({ lat: 33.7766, lon: -84.3963, accuracy: 9, heading: 90 })
    act(() => result.current.request())
    expect(geo.watchPosition).toHaveBeenCalledTimes(1)
  })

  it('starts watching on its own when permission was already granted, and cleans up', async () => {
    const { geo, calls } = fakeGeolocation()
    install(geo, 'granted')
    const { result, unmount } = renderHook(() => useGeolocation())

    await waitFor(() => expect(geo.watchPosition).toHaveBeenCalled())
    act(() => calls[calls.length - 1].success(fix(33.78, -84.39, 20, Number.NaN)))
    expect(result.current.position?.heading).toBeNull()

    unmount()
    expect(geo.clearWatch).toHaveBeenCalled()
  })

  it('knows a previously denied permission without prompting', async () => {
    const { geo } = fakeGeolocation()
    install(geo, 'denied')
    const { result } = renderHook(() => useGeolocation())

    await waitFor(() => expect(result.current.status).toBe('denied'))
    expect(geo.watchPosition).not.toHaveBeenCalled()
  })

  it('keeps watching through timeouts and signal loss, and stops only when denied', async () => {
    const { geo, calls } = fakeGeolocation()
    install(geo, 'throws')
    const { result } = renderHook(() => useGeolocation())

    act(() => result.current.request())
    act(() => calls[0].failure(failure(3)))
    expect(result.current.status).toBe('locating')
    expect(result.current.error).toMatch(/Still looking/)

    act(() => calls[0].failure(failure(2)))
    expect(result.current.status).toBe('unavailable')
    expect(geo.clearWatch).not.toHaveBeenCalled()

    act(() => calls[0].success(fix(33.78, -84.39)))
    expect(result.current.status).toBe('granted')
    act(() => calls[0].failure(failure(2)))
    expect(result.current.status).toBe('granted')
    expect(result.current.position).toMatchObject({ lat: 33.78 })

    act(() => calls[0].failure(failure(1)))
    expect(result.current.status).toBe('denied')
    expect(geo.clearWatch).toHaveBeenCalled()
    act(() => result.current.request())
    expect(geo.watchPosition).toHaveBeenCalledTimes(2)
  })
})
