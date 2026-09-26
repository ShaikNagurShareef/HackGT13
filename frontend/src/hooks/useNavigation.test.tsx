import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Route } from '../api/schemas'
import type { GeoFix } from '../lib/origin'
import { route } from '../test/fixtures'
import { useNavigation } from './useNavigation'

const START = { lat: 33.7771, lon: -84.3962 }
const END = { lat: 33.781, lon: -84.3863 }
const DEST = { ...END, label: 'Midtown MARTA' }
const STREETS = [{ name: 'Ferst Drive Northwest', path: route().coords }]

const gpsAt = (p: { lat: number; lon: number }): GeoFix => ({ ...p, accuracy: 8, heading: 45, at: 0 })

interface Props {
  r: Route | null
  gps: GeoFix | null
}

const DEPART = '2026-09-25T22:30:00-04:00'

function setup(initial: Props) {
  return renderHook(
    ({ r, gps }: Props) => useNavigation({ route: r, gps, streets: STREETS, destination: DEST, departAt: DEPART }),
    { initialProps: initial },
  )
}

describe('useNavigation', () => {
  const speak = vi.fn()
  beforeEach(() => {
    speak.mockReset()
    vi.stubGlobal('speechSynthesis', { cancel: vi.fn(), speak })
    vi.stubGlobal('SpeechSynthesisUtterance', class { text: string; constructor(text: string) { this.text = text } })
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('is idle until started', () => {
    const { result } = setup({ r: route(), gps: null })
    expect(result.current.active).toBe(false)
    expect(result.current.instruction).toBeNull()
  })

  it('previews the walk with the same banner, speaks each stretch once, and arrives', () => {
    vi.useFakeTimers()
    const { result } = setup({ r: route(), gps: null })

    act(() => result.current.start('preview'))
    act(() => void vi.advanceTimersByTime(500))
    expect(result.current.active).toBe(true)
    expect(result.current.mode).toBe('preview')
    expect(result.current.position).not.toBeNull()
    expect(result.current.instruction?.headline).toBe('High traffic risk ahead')
    expect(result.current.instruction?.detail).toMatch(/^Spring Street in \d+ m$/)

    // Advance tick by tick so every position renders, as it does on a phone.
    for (let i = 0; i < 120; i++) act(() => void vi.advanceTimersByTime(500))
    expect(result.current.arrived).toBe(true)
    const texts = speak.mock.calls.map(([u]) => (u as { text: string }).text)
    expect(texts.filter((t) => t.includes('Spring Street'))).toHaveLength(1)
    expect(texts).toContain("You've arrived.")
  })

  it('follows GPS: projects onto the route, counts down, and sticks on arrival', () => {
    const { result, rerender } = setup({ r: route(), gps: gpsAt(START) })

    act(() => result.current.start('gps'))
    expect(result.current.mode).toBe('gps')
    expect(result.current.alongM).toBeCloseTo(0, 0)
    expect(result.current.remainingS).toBeCloseTo(1104, -1)
    expect(result.current.heading).toBe(45)
    expect(result.current.arrivalAt.getTime()).toBeGreaterThan(Date.now() + 1000 * 1000)

    rerender({ r: route(), gps: gpsAt(END) })
    expect(result.current.arrived).toBe(true)
    rerender({ r: route(), gps: gpsAt({ lat: 33.7795, lon: -84.39 }) })
    expect(result.current.arrived).toBe(true)

    act(() => result.current.end())
    expect(result.current.active).toBe(false)
    expect(result.current.arrived).toBe(false)
  })

  it('also arrives within 30 m of the chosen destination when the route ends at a snapped node', () => {
    const snapped = route({ coords: [[-84.3962, 33.7771], [-84.3868, 33.7806]] })
    const { result, rerender } = setup({ r: snapped, gps: gpsAt(START) })

    act(() => result.current.start('gps'))
    rerender({ r: snapped, gps: gpsAt({ lat: 33.7811, lon: -84.3864 }) })
    expect(result.current.arrived).toBe(true)
  })

  it('names the street it is on when no stretch is near', () => {
    const quiet = route({ alerts: [] })
    const { result } = setup({ r: quiet, gps: gpsAt(START) })

    act(() => result.current.start('gps'))
    expect(result.current.instruction?.headline).toBe('Continue on Ferst Drive Northwest')
  })

  it('measures progress in route metres even when the drawn geometry runs longer', () => {
    // Geometry is ~1 km; the router says the walk is 500 m with an alert at 200-260 m.
    const r = route({ distance_m: 500, alerts: [{ start_m: 200, end_m: 260, names: ['Spring Street'], score: 95, stretches: 1 }] })
    const halfway = { lat: (START.lat + END.lat) / 2, lon: (START.lon + END.lon) / 2 }
    const { result } = setup({ r, gps: gpsAt(halfway) })

    act(() => result.current.start('gps'))
    expect(result.current.alongM).toBeCloseTo(250, -1)
    expect(result.current.remainingM).toBeCloseTo(250, -1)
    expect(result.current.instruction?.headline).toBe('High traffic risk here')
  })

  it('a preview walk arrives at the planned time; live GPS uses now', () => {
    vi.useFakeTimers()
    const { result } = setup({ r: route(), gps: null })

    act(() => result.current.start('preview'))
    expect(result.current.arrivalAt.toISOString()).toBe('2026-09-26T02:48:24.000Z')
  })

  it('stays idle without a route', () => {
    const { result } = setup({ r: null, gps: gpsAt(START) })
    act(() => result.current.start('gps'))
    expect(result.current.instruction).toBeNull()
  })
})
