import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { Route, TravelMode } from '../api/schemas'
import {
  hasArrived,
  nearestStreet,
  nextInstruction,
  projectOnRoute,
  remainingSeconds,
  type NamedPath,
  type NavInstruction,
} from '../lib/navigation'
import { arrivalRadiusM } from '../lib/modes'
import type { GeoFix } from '../lib/origin'
import { arrivalAt as arrivalAtTime } from '../lib/routeSummary'
import { deviceSpeak } from '../lib/voice'
import { WALK_SPEED_MPS, alertText, cumulativeDistances, dueAlert } from '../lib/walk'
import type { Place } from '../state/urlState'
import { usePreviewWalk } from './usePreviewWalk'

export type NavMode = 'gps' | 'preview'

export interface NavigationInput {
  route: Route | null
  gps: GeoFix | null
  streets: ReadonlyArray<NamedPath>
  destination: Place | null
  /** Planned departure (routes.depart_at): a preview walk arrives on that schedule. */
  departAt: string | null
  /** Travel mode: ride wording on the banner and a wider arrival radius. */
  mode?: TravelMode
  /** Travel speed for the preview and alert spacing (defaults to walking pace). */
  speedMps?: number
}

export interface Navigation {
  active: boolean
  mode: NavMode
  arrived: boolean
  position: [number, number] | null
  heading: number | null
  alongM: number
  remainingS: number
  remainingM: number
  instruction: NavInstruction | null
  /** Estimated arrival (wall clock), refreshed while navigating. */
  arrivalAt: Date
  start: (mode: NavMode) => void
  end: () => void
}

const ARRIVED_TEXT = "You've arrived."
const VIBRATE_MS = 200
const CLOCK_TICK_MS = 15_000

/**
 * Navigation mode: follows GPS (or the simulated preview walker) along the route, derives the
 * banner, and speaks each high-risk stretch once (VOX-02).
 */
export function useNavigation(input: NavigationInput): Navigation {
  const { route, gps, streets, destination, departAt, mode: travel = 'walk', speedMps = WALK_SPEED_MPS } = input
  const [active, setActive] = useState(false)
  const [mode, setMode] = useState<NavMode>('gps')
  const [gpsArrived, setGpsArrived] = useState(false)
  const walk = usePreviewWalk(route, false, speedMps)
  const spoken = useRef<Set<number>>(new Set())
  const lastSpokenS = useRef<number | null>(null)
  const arrivalSpoken = useRef(false)
  const [clock, setClock] = useState(() => Date.now())

  const cum = useMemo(() => (route ? cumulativeDistances(route.coords) : []), [route])
  // The drawn geometry can run longer than the routed walk (repeated segment vertices), while
  // alerts and durations are in routed metres; measure progress as a share of the geometry.
  const geometryM = cum.length ? cum[cum.length - 1] : 0
  const totalM = route && route.distance_m > 0 ? route.distance_m : geometryM
  const toRouteM = geometryM > 0 ? totalM / geometryM : 1
  const live = active && route != null
  const position: [number, number] | null = !live
    ? null
    : mode === 'preview'
      ? walk.position
      : gps
        ? [gps.lon, gps.lat]
        : null
  const alongM =
    route && position ? projectOnRoute(route.coords, cum, { lon: position[0], lat: position[1] }).alongM * toRouteM : 0
  const end = route?.coords[route.coords.length - 1]
  const hasPosition = position != null

  // Arrival is sticky: GPS jitter must not bounce the walker out of "You've arrived".
  // Adjusting state during render (not in an effect) is React's pattern for this.
  const radiusM = arrivalRadiusM(travel)
  const reachedEnd = end != null && gps != null && hasArrived(gps, { lon: end[0], lat: end[1] }, radiusM)
  const reachedDestination = destination != null && gps != null && hasArrived(gps, destination, radiusM)
  if (live && mode === 'gps' && !gpsArrived && (reachedEnd || reachedDestination)) setGpsArrived(true)
  const arrived = live && (mode === 'preview' ? walk.progress >= 1 : gpsArrived)

  // Voice is a side effect of moving along the route, so it lives in an effect, not render.
  useEffect(() => {
    if (!live || !route || !hasPosition) return
    if (arrived) {
      if (!arrivalSpoken.current) deviceSpeak(ARRIVED_TEXT)
      arrivalSpoken.current = true
      return
    }
    const walkS = alongM / speedMps
    const idx = dueAlert(route.alerts, alongM, walkS, { spoken: spoken.current, lastSpokenS: lastSpokenS.current })
    if (idx == null) return
    spoken.current.add(idx)
    lastSpokenS.current = walkS
    deviceSpeak(alertText(route.alerts[idx]))
    navigator.vibrate?.(VIBRATE_MS)
  }, [live, route, hasPosition, alongM, arrived, speedMps])

  useEffect(() => {
    if (!live) return
    const id = window.setInterval(() => setClock(Date.now()), CLOCK_TICK_MS)
    return () => window.clearInterval(id)
  }, [live])

  const start = useCallback(
    (next: NavMode) => {
      if (!route) return
      spoken.current = new Set()
      lastSpokenS.current = null
      arrivalSpoken.current = false
      setGpsArrived(false)
      setMode(next)
      setClock(Date.now())
      setActive(true)
      if (next === 'preview') walk.start()
    },
    [route, walk],
  )

  const stop = walk.stop
  const endNavigation = useCallback(() => {
    stop()
    setActive(false)
    setGpsArrived(false)
  }, [stop])

  const street = position ? nearestStreet({ lon: position[0], lat: position[1] }, streets) : null
  const instruction =
    live && route
      ? nextInstruction({
          alerts: route.alerts,
          alongM,
          totalM,
          durationS: route.duration_s,
          street,
          destination: destination?.label ?? 'Your destination',
          mode: travel,
        })
      : null

  const remainingS = route ? remainingSeconds(route.duration_s, totalM, alongM) : 0
  return {
    active: live,
    mode,
    arrived,
    position,
    heading: mode === 'gps' ? (gps?.heading ?? null) : null,
    alongM,
    remainingS,
    arrivalAt:
      mode === 'preview' && departAt && route ? arrivalAtTime(departAt, route.duration_s) : new Date(clock + remainingS * 1000),
    remainingM: Math.max(0, totalM - alongM),
    instruction,
    start,
    end: endNavigation,
  }
}
