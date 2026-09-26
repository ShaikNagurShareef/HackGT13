import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, api, type Bbox } from '../api/client'
import type { Report } from '../api/schemas'

export const DEBOUNCE_MS = 400
/** Matches the API's viewport limit; zoomed further out, reports are simply not drawn. */
export const MAX_SPAN_DEG = 0.3
/** Codes meaning "this server has no community reports" (unset Atlas, or an older API). */
const OFF_CODES = new Set(['REPORTS_UNAVAILABLE', 'BAD_RESPONSE', 'DEMO_ONLY'])

function tooWide([w, s, e, n]: Bbox): boolean {
  return e - w > MAX_SPAN_DEG || n - s > MAX_SPAN_DEG
}

/** Community reports in the map viewport, fetched on move end (debounced). */
export function useViewportReports(enabled: boolean) {
  const [reports, setReports] = useState<Report[]>([])
  const [serviceOn, setServiceOn] = useState(true)
  const timer = useRef<number | undefined>(undefined)
  const lastBbox = useRef<Bbox | null>(null)
  const seq = useRef(0)
  const active = enabled && serviceOn

  const load = useCallback((bbox: Bbox) => {
    if (tooWide(bbox)) {
      setReports([])
      return
    }
    const id = ++seq.current
    api
      .reportsInBbox(bbox)
      .then((found) => id === seq.current && setReports(found))
      .catch((e: unknown) => {
        if (id !== seq.current) return
        setReports([])
        if (e instanceof ApiError && OFF_CODES.has(e.code)) setServiceOn(false)
      })
  }, [])

  const schedule = useCallback(
    (bbox: Bbox, delay: number) => {
      lastBbox.current = bbox
      window.clearTimeout(timer.current)
      if (!active) return
      timer.current = window.setTimeout(() => load(bbox), delay)
    },
    [active, load],
  )

  const onViewport = useCallback((bbox: Bbox) => schedule(bbox, DEBOUNCE_MS), [schedule])
  const refresh = useCallback(() => {
    if (lastBbox.current) schedule(lastBbox.current, 0)
  }, [schedule])

  useEffect(() => () => window.clearTimeout(timer.current), [])

  return { reports: active ? reports : [], available: active, onViewport, refresh }
}
