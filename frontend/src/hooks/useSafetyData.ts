import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, type Bbox } from '../api/client'
import { safetyApi } from '../api/safety'
import type { HelpPoint, SafetyHex, SafetyMeta } from '../api/safetySchemas'
import { dayPartFor } from '../lib/safety'
import { useLatest } from './useLatest'

export const DEBOUNCE_MS = 400
/** Matches the API's viewport limit; zoomed further out the layer asks to zoom in. */
export const MAX_SPAN_DEG = 0.3
/** Codes meaning "this server has no safety layer" (older bundle, older API, offline demo). */
const OFF_CODES = new Set(['SAFETY_UNAVAILABLE', 'BAD_RESPONSE', 'DEMO_ONLY', 'NOT_FOUND'])

const NO_HEXES: SafetyHex[] = []
const NO_POINTS: HelpPoint[] = []

export type SafetyStatus = 'checking' | 'on' | 'off'

export interface SafetyData {
  status: SafetyStatus
  available: boolean
  meta: SafetyMeta | null
  hexes: ReadonlyArray<SafetyHex>
  helpPoints: ReadonlyArray<HelpPoint>
  /** The viewport is wider than the API serves: ask to zoom in. */
  tooWide: boolean
  onViewport: (bbox: Bbox) => void
}

function isTooWide([w, s, e, n]: Bbox): boolean {
  return e - w > MAX_SPAN_DEG || n - s > MAX_SPAN_DEG
}

function isOff(err: unknown): boolean {
  return err instanceof ApiError && OFF_CODES.has(err.code)
}

/**
 * Personal-safety data for the map viewport: probes /safety/meta once, then (while `active`)
 * loads hexes for the Risk Tides hour and help points on debounced map moves. Hexes refetch
 * only when the hour crosses into another day part.
 */
export function useSafetyData(active: boolean, hour: number): SafetyData {
  const [status, setStatus] = useState<SafetyStatus>('checking')
  const [meta, setMeta] = useState<SafetyMeta | null>(null)
  const [view, setView] = useState<Bbox | null>(null)
  const [hexes, setHexes] = useState<SafetyHex[]>(NO_HEXES)
  const [helpPoints, setHelpPoints] = useState<HelpPoint[]>(NO_POINTS)
  const latestBbox = useRef<Bbox | null>(null)
  const timer = useRef<number | undefined>(undefined)
  const hourRef = useLatest(hour)
  const on = active && status === 'on'
  const tooWide = view != null && isTooWide(view)
  const partKey = meta ? (dayPartFor(hour, meta.day_parts)?.key ?? `h${hour}`) : `h${hour}`

  useEffect(() => {
    let cancelled = false
    safetyApi
      .meta()
      .then((m) => {
        if (cancelled) return
        setMeta(m)
        setStatus('on')
      })
      .catch(() => !cancelled && setStatus('off'))
    return () => {
      cancelled = true
    }
  }, [])

  const onViewport = useCallback(
    (bbox: Bbox) => {
      latestBbox.current = bbox
      window.clearTimeout(timer.current)
      if (on) timer.current = window.setTimeout(() => setView(bbox), DEBOUNCE_MS)
    },
    [on],
  )

  // Switching the layer on loads wherever the map already is; switching off cancels a pending move.
  useEffect(() => {
    if (on) setView(latestBbox.current)
    else window.clearTimeout(timer.current)
  }, [on])
  useEffect(() => () => window.clearTimeout(timer.current), [])

  const fail = useCallback((err: unknown) => {
    // A transient blip keeps the last good layer rather than flicker.
    if (isOff(err)) setStatus('off')
  }, [])

  useEffect(() => {
    if (!on || !view || isTooWide(view)) return
    let cancelled = false
    safetyApi
      .hexes(view, hourRef.current)
      .then((found) => !cancelled && setHexes(found))
      .catch((e: unknown) => !cancelled && fail(e))
    return () => {
      cancelled = true
    }
  }, [on, view, partKey, hourRef, fail])

  useEffect(() => {
    if (!on || !view || isTooWide(view)) return
    let cancelled = false
    safetyApi
      .helpPoints(view)
      .then((found) => !cancelled && setHelpPoints(found))
      .catch((e: unknown) => !cancelled && fail(e))
    return () => {
      cancelled = true
    }
  }, [on, view, fail])

  const showing = on && !tooWide
  return {
    status,
    available: status === 'on',
    meta,
    hexes: showing ? hexes : NO_HEXES,
    helpPoints: showing ? helpPoints : NO_POINTS,
    tooWide: on && tooWide,
    onViewport,
  }
}
