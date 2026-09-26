import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ROUTINES_STORAGE_KEY,
  clearHistory,
  recentPlaces,
  recordTrip,
  savedPlaces,
  setSavedPlace,
  suggestTrips,
  type Place,
  type RoutineSuggestion,
  type SavedKind,
  type TripRecord,
} from '../lib/routines'

/** Same-tab broadcast so every mounted useRoutines re-reads after a write (the `storage` event is cross-tab only). */
const CHANGED_EVENT = 'pathpro:routines-changed'
const HOUR_MS = 3_600_000
const HERE_DECIMALS = 3 // ~100 m buckets for memoizing on location

export interface Routines {
  suggestions: RoutineSuggestion[]
  recents: Place[]
  saved: Partial<Record<SavedKind, Place>>
  record: (trip: TripRecord) => void
  setSaved: (kind: SavedKind, place: Place | null) => void
  clear: () => void
}

function announceChange(): void {
  window.dispatchEvent(new Event(CHANGED_EVENT))
}

interface StoredView {
  recents: Place[]
  saved: Partial<Record<SavedKind, Place>>
}

function readStoredView(): StoredView {
  return { recents: recentPlaces(), saved: savedPlaces() }
}

/** On-device routine suggestions, recents and saved places backed by localStorage. */
export function useRoutines(here: { lat: number; lon: number } | null, now?: Date): Routines {
  const [{ recents, saved }, setStoredView] = useState(readStoredView)
  const [version, setVersion] = useState(0)

  useEffect(() => {
    const refresh = () => {
      setStoredView(readStoredView())
      setVersion((v) => v + 1)
    }
    const onStorage = (e: StorageEvent) => {
      if (e.key === null || e.key === ROUTINES_STORAGE_KEY) refresh()
    }
    window.addEventListener('storage', onStorage)
    window.addEventListener(CHANGED_EVENT, refresh)
    return () => {
      window.removeEventListener('storage', onStorage)
      window.removeEventListener(CHANGED_EVENT, refresh)
    }
  }, [])

  const nowMs = (now ?? new Date()).getTime()
  const hourKey = Math.floor(nowMs / HOUR_MS)
  const hereKey = here ? `${here.lat.toFixed(HERE_DECIMALS)},${here.lon.toFixed(HERE_DECIMALS)}` : 'none'
  const suggestions = useMemo(
    () => suggestTrips(new Date(nowMs), here),
    // Recompute per ~100 m of movement, per hour, or after a write — not on every GPS tick.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [hereKey, hourKey, version],
  )

  const record = useCallback((trip: TripRecord) => {
    recordTrip(trip)
    announceChange()
  }, [])
  const setSaved = useCallback((kind: SavedKind, place: Place | null) => {
    setSavedPlace(kind, place)
    announceChange()
  }, [])
  const clear = useCallback(() => {
    clearHistory()
    announceChange()
  }, [])

  return { suggestions, recents, saved, record, setSaved, clear }
}
