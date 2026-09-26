import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { GeoResult } from '../api/schemas'

const GEOCODE_DEBOUNCE_MS = 250
const MIN_QUERY_CHARS = 3
const NO_RESULTS: GeoResult[] = []

/** Debounced geocoder lookups; failures quietly fall back to the local gazetteer. */
export function useGeocode(text: string): GeoResult[] {
  const [results, setResults] = useState<GeoResult[]>([])
  useEffect(() => {
    const q = text.trim()
    if (q.length < MIN_QUERY_CHARS) return
    let cancelled = false
    const id = window.setTimeout(() => {
      api
        .geocode(q)
        .then((r) => !cancelled && setResults(r))
        .catch(() => !cancelled && setResults([]))
    }, GEOCODE_DEBOUNCE_MS)
    return () => {
      cancelled = true
      window.clearTimeout(id)
    }
  }, [text])
  return text.trim().length < MIN_QUERY_CHARS ? NO_RESULTS : results
}
