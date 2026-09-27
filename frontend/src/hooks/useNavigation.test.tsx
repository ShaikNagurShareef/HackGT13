import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import type { Route } from '../api/schemas'
import type { GeoFix } from '../lib/origin'
import { spokenTexts, stubAudio, stubBlobUrls } from '../test/audio'
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

  it('rides: ride wording on the street banner and a wider arrival radius', () => {
    const quiet = route({ alerts: [] })
    const { result, rerender } = renderHook(
      ({ gps }: { gps: GeoFix }) =>
        useNavigation({ route: quiet, gps, streets: STREETS, destination: DEST, departAt: DEPART, mode: 'bike' }),
      { initialProps: { gps: gpsAt(START) } },
    )

    act(() => result.current.start('gps'))
    expect(result.current.instruction?.headline).toBe('Keep riding on Ferst Drive Northwest')
    // ~35 m short of the end: outside the 30 m walking radius, inside the 40 m ride radius.
    rerender({ gps: gpsAt({ lat: END.lat - 0.000315, lon: END.lon }) })
    expect(result.current.arrived).toBe(true)
  })

  it('a ride preview moves faster than a walk preview', () => {
    vi.useFakeTimers()
    const r = route()
    const walk = setup({ r, gps: null })
    const ride = renderHook(() =>
      useNavigation({ route: r, gps: null, streets: STREETS, destination: DEST, departAt: DEPART, mode: 'bike', speedMps: 4.2 }),
    )

    act(() => walk.result.current.start('preview'))
    act(() => ride.result.current.start('preview'))
    act(() => void vi.advanceTimersByTime(1000))
    expect(ride.result.current.alongM).toBeGreaterThan(walk.result.current.alongM * 2)
  })

  describe('Grok Voice alerts', () => {
    const KEY = 'aaaaaaaaaaaaaaaa'
    const withVoice = () => {
      const r = route() // one route object, as PathPro memoises it
      return renderHook(() =>
        useNavigation({ route: r, gps: null, streets: STREETS, destination: DEST, departAt: DEPART, routeKey: KEY, routeKind: 'fast' }),
      )
    }
    const walkToTheEnd = () => {
      for (let i = 0; i < 120; i++) act(() => void vi.advanceTimersByTime(500))
    }

    afterEach(() => {
      vi.restoreAllMocks()
      window.history.replaceState(null, '', '/')
    })

    it('prefetches the route alert clips on start and plays the Grok clip for each stretch', async () => {
      vi.useFakeTimers()
      stubBlobUrls()
      const audio = stubAudio()
      const fetchClip = vi.spyOn(api, 'ttsAlert').mockResolvedValue(new Blob(['mp3']))
      const { result } = withVoice()

      act(() => result.current.start('preview'))
      await act(async () => {})
      expect(fetchClip).toHaveBeenCalledTimes(1)
      expect(fetchClip).toHaveBeenCalledWith(KEY, 0, 'fast', expect.any(AbortSignal))

      walkToTheEnd()
      expect(audio.sources).toEqual(['blob:clip-0'])
      expect(spokenTexts(speak).filter((t) => t.includes('Spring Street'))).toHaveLength(0)
      expect(spokenTexts(speak)).toContain("You've arrived.")
    })

    it('falls back to the device voice, with the distance, when the clip is missing', async () => {
      vi.useFakeTimers()
      stubBlobUrls()
      const audio = stubAudio()
      vi.spyOn(api, 'ttsAlert').mockRejectedValue(new Error('503'))
      const { result } = withVoice()

      act(() => result.current.start('preview'))
      await act(async () => {})
      walkToTheEnd()

      expect(audio.sources).toEqual([])
      expect(spokenTexts(speak).filter((t) => t.includes('Spring Street'))).toEqual([
        'In 60 meters, Spring Street has high traffic risk. Take extra care crossing.',
      ])
    })

    it('keeps the device voice in demo mode', async () => {
      vi.useFakeTimers()
      window.history.replaceState(null, '', '/?demo=1')
      const fetchClip = vi.spyOn(api, 'ttsAlert')
      const { result } = withVoice()

      act(() => result.current.start('preview'))
      await act(async () => {})
      walkToTheEnd()

      expect(fetchClip).not.toHaveBeenCalled()
      expect(spokenTexts(speak).filter((t) => t.includes('Spring Street'))).toHaveLength(1)
    })
  })
})
