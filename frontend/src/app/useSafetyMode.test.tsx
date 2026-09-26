import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { MapMode } from '../lib/options'
import { DEFAULT_SAFETY_LAYERS } from '../lib/safety'
import { helpPoint, safetyHex, safetyMeta } from '../test/fixtures'
import { useSafetyMode } from './useSafetyMode'

const JSON_HEADERS = { headers: { 'content-type': 'application/json' } }
const VIEW: [number, number, number, number] = [-84.4, 33.77, -84.38, 33.79]

function serve(available = true) {
  const fetcher = vi.fn(async (url: string) => {
    if (!available) return new Response(JSON.stringify({ success: false, error: { code: 'SAFETY_UNAVAILABLE', message: 'x' } }), JSON_HEADERS)
    const data = url.includes('/meta') ? safetyMeta() : url.includes('/hexes') ? [safetyHex({ activity_band: null })] : [helpPoint()]
    return new Response(JSON.stringify({ success: true, data }), JSON_HEADERS)
  })
  vi.stubGlobal('fetch', fetcher)
  return fetcher
}

describe('useSafetyMode', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('stays off the map outside personal safety mode but reports availability', async () => {
    serve()
    const { result } = renderHook(() => useSafetyMode('streets', 21))

    await waitFor(() => expect(result.current.available).toBe(true))
    expect(result.current.mapInput).toBeNull()
    expect(result.current.legend).toBeNull()
    expect(result.current.controls).not.toBeNull()
  })

  it('is fully hidden when the server has no safety layer', async () => {
    serve(false)
    const { result } = renderHook(() => useSafetyMode('safety', 21))

    await waitFor(() => expect(result.current.status).toBe('off'))
    expect(result.current.available).toBe(false)
    expect(result.current.controls).toBeNull()
    expect(result.current.mapInput).toBeNull()
    expect(result.current.legend).toBeNull()
  })

  it('feeds the map, legend, and toggles in safety mode, following the hour', async () => {
    serve()
    const { result, rerender } = renderHook(({ hour }) => useSafetyMode('safety', hour), { initialProps: { hour: 21 } })
    await waitFor(() => expect(result.current.available).toBe(true))

    act(() => result.current.onViewport(VIEW))
    await waitFor(() => expect(result.current.mapInput?.hexes).toHaveLength(1))

    expect(result.current.mapInput?.helpPoints).toHaveLength(1)
    expect(result.current.mapInput?.layers).toEqual(DEFAULT_SAFETY_LAYERS)
    expect(result.current.legend).toMatchObject({ hour: 21, layers: DEFAULT_SAFETY_LAYERS, tooWide: false })
    expect(result.current.controls).toMatchObject({ hasLit: true, hasBusy: false })
    expect(result.current.dayLabel).toBe('Evening')

    rerender({ hour: 8 })
    expect(result.current.dayLabel).toBe('Morning')
    act(() => result.current.controls?.onLayers({ ...DEFAULT_SAFETY_LAYERS, crimes: false }))
    expect(result.current.mapInput?.layers.crimes).toBe(false)
  })

  it('shows a tapped hex or help point until closed or the mode changes', async () => {
    serve()
    const { result, rerender } = renderHook(({ mode }: { mode: MapMode }) => useSafetyMode(mode, 21), {
      initialProps: { mode: 'safety' as MapMode },
    })
    await waitFor(() => expect(result.current.mapInput).not.toBeNull())

    act(() => result.current.mapInput?.onPick({ kind: 'help', point: helpPoint() }))
    expect(result.current.pick).toEqual({ kind: 'help', point: helpPoint() })
    act(() => result.current.closePick())
    expect(result.current.pick).toBeNull()

    act(() => result.current.mapInput?.onPick({ kind: 'hex', hex: safetyHex() }))
    rerender({ mode: 'streets' })
    expect(result.current.pick).toBeNull()
  })
})
