import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { ROUTINES_STORAGE_KEY, recordTrip, type Place, type TripRecord } from '../lib/routines'
import { useRoutines } from './useRoutines'

const KLAUS: Place = { label: 'Klaus Building', lat: 33.7771, lon: -84.3962 }
const TECH_SQ: Place = { label: 'Tech Square', lat: 33.7765, lon: -84.3893 }
const HOME: Place = { label: 'Home', lat: 33.785, lon: -84.402 }
const FRI_940PM = new Date('2026-09-25T21:40:00-04:00')

const FRIDAY_NIGHTS: ReadonlyArray<TripRecord> = [
  { from: KLAUS, to: TECH_SQ, at: '2026-09-11T22:05:00-04:00' },
  { from: KLAUS, to: TECH_SQ, at: '2026-09-18T22:00:00-04:00' },
]

describe('useRoutines', () => {
  beforeEach(() => window.localStorage.clear())

  it('starts empty with no history', () => {
    const { result } = renderHook(() => useRoutines(null, FRI_940PM))

    expect(result.current.suggestions).toEqual([])
    expect(result.current.recents).toEqual([])
    expect(result.current.saved).toEqual({})
  })

  it('updates recents and suggestions after record()', () => {
    const { result } = renderHook(() => useRoutines(null, FRI_940PM))

    act(() => FRIDAY_NIGHTS.forEach((t) => result.current.record(t)))

    expect(result.current.recents).toEqual([TECH_SQ])
    expect(result.current.suggestions).toEqual([
      expect.objectContaining({ kind: 'routine', to: TECH_SQ, reason: 'You usually walk here on Fridays around 10 PM' }),
    ])
  })

  it('updates saved places and keeps them when history is cleared', () => {
    const { result } = renderHook(() => useRoutines(null, FRI_940PM))

    act(() => {
      result.current.record(FRIDAY_NIGHTS[0])
      result.current.setSaved('home', HOME)
    })
    expect(result.current.saved).toEqual({ home: HOME })

    act(() => result.current.clear())

    expect(result.current.recents).toEqual([])
    expect(result.current.saved).toEqual({ home: HOME })
  })

  it('picks up writes from another tab via the storage event', () => {
    const { result } = renderHook(() => useRoutines(null, FRI_940PM))

    act(() => {
      FRIDAY_NIGHTS.forEach((t) => recordTrip(t))
      window.dispatchEvent(new StorageEvent('storage', { key: ROUTINES_STORAGE_KEY }))
    })

    expect(result.current.recents).toEqual([TECH_SQ])
  })

  it('ignores storage events for unrelated keys', () => {
    const { result } = renderHook(() => useRoutines(null, FRI_940PM))

    act(() => {
      recordTrip(FRIDAY_NIGHTS[0])
      window.dispatchEvent(new StorageEvent('storage', { key: 'something-else' }))
    })

    expect(result.current.recents).toEqual([])
  })

  it('keeps sibling hook instances in the same tab in sync', () => {
    const writer = renderHook(() => useRoutines(null, FRI_940PM))
    const reader = renderHook(() => useRoutines(null, FRI_940PM))

    act(() => writer.result.current.record(FRIDAY_NIGHTS[0]))

    expect(reader.result.current.recents).toEqual([TECH_SQ])
  })

  it('recomputes suggestions when you move', () => {
    const { result, rerender } = renderHook(({ here }) => useRoutines(here, FRI_940PM), {
      initialProps: { here: null as { lat: number; lon: number } | null },
    })
    act(() => FRIDAY_NIGHTS.forEach((t) => result.current.record(t)))
    expect(result.current.suggestions).toHaveLength(1)

    rerender({ here: { lat: TECH_SQ.lat, lon: TECH_SQ.lon } })

    expect(result.current.suggestions).toEqual([])
  })

  it('defaults the clock to now', () => {
    const { result } = renderHook(() => useRoutines(null))

    expect(result.current.suggestions).toEqual([])
  })
})
