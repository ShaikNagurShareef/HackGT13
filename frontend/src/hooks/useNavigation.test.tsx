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

function setup(initial: Props) {
  return renderHook(({ r, gps }: Props) => useNavigation({ route: r, gps, streets: STREETS, destination: DEST }), {
    initialProps: initial,
  })
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

    rerender({ r: route(), gps: gpsAt(END) })
    expect(result.current.arrived).toBe(true)
    rerender({ r: route(), gps: gpsAt({ lat: 33.7795, lon: -84.39 }) })
    expect(result.current.arrived).toBe(true)

    act(() => result.current.end())
    expect(result.current.active).toBe(false)
    expect(result.current.arrived).toBe(false)
  })

  it('names the street it is on when no stretch is near', () => {
    const quiet = route({ alerts: [] })
    const { result } = setup({ r: quiet, gps: gpsAt(START) })

    act(() => result.current.start('gps'))
    expect(result.current.instruction?.headline).toBe('Continue on Ferst Drive Northwest')
  })

  it('stays idle without a route', () => {
    const { result } = setup({ r: null, gps: gpsAt(START) })
    act(() => result.current.start('gps'))
    expect(result.current.instruction).toBeNull()
  })
})
