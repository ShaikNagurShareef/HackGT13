import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import type { TransitStation } from '../api/schemas'

const NONE: ReadonlyArray<TransitStation> = []

/** MARTA rail stations, fetched once and only when a long walk could use them; none (card hidden) on failure. */
export function useTransitStations(enabled: boolean): ReadonlyArray<TransitStation> {
  const [stations, setStations] = useState<ReadonlyArray<TransitStation>>(NONE)
  const requested = useRef(false)

  useEffect(() => {
    if (!enabled || requested.current) return
    requested.current = true
    api
      .transitStations()
      .then(setStations)
      .catch(() => setStations(NONE)) // an optional hint: without stations the MARTA card stays hidden
  }, [enabled])

  return stations
}
