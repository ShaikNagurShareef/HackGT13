import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { Route } from '../api/schemas'
import {
  hasArrived,
  nearestStreet,
  nextInstruction,
  projectOnRoute,
  remainingSeconds,
  type NamedPath,
  type NavInstruction,
} from '../lib/navigation'
import type { GeoFix } from '../lib/origin'
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
  start: (mode: NavMode) => void
  end: () => void
}

const ARRIVED_TEXT = "You've arrived."
const VIBRATE_MS = 200

/**
 * Navigation mode: follows GPS (or the simulated preview walker) along the route, derives the
 * banner, and speaks each high-risk stretch once (VOX-02).
 */
export function useNavigation({ route, gps, streets, destination }: NavigationInput): Navigation {
  const [active, setActive] = useState(false)
  const [mode, setMode] = useState<NavMode>('gps')
  const [gpsArrived, setGpsArrived] = useState(false)
  const walk = usePreviewWalk(route, false)
  const spoken = useRef<Set<number>>(new Set())
  const lastSpokenS = useRef<number | null>(null)
  const arrivalSpoken = useRef(false)

  const cum = useMemo(() => (route ? cumulativeDistances(route.coords) : []), [route])
  const totalM = cum.length ? cum[cum.length - 1] : 0
  const live = active && route != null
  const position: [number, number] | null = !live
    ? null
    : mode === 'preview'
      ? walk.position
      : gps
        ? [gps.lon, gps.lat]
        : null
  const alongM = route && position ? projectOnRoute(route.coords, cum, { lon: position[0], lat: position[1] }).alongM : 0
  const end = route?.coords[route.coords.length - 1]
  const arrived = live && (mode === 'preview' ? walk.progress >= 1 : gpsArrived)

  useEffect(() => {
    if (!live || mode !== 'gps' || !gps || !end) return
    if (hasArrived(gps, { lon: end[0], lat: end[1] })) setGpsArrived(true)
  }, [live, mode, gps, end])

  // Voice is a side effect of moving along the route, so it lives in an effect, not render.
  useEffect(() => {
    if (!live || !route || !position) return
    if (arrived) {
      if (!arrivalSpoken.current) deviceSpeak(ARRIVED_TEXT)
      arrivalSpoken.current = true
      return
    }
    const walkS = alongM / WALK_SPEED_MPS
    const idx = dueAlert(route.alerts, alongM, walkS, { spoken: spoken.current, lastSpokenS: lastSpokenS.current })
    if (idx == null) return
    spoken.current.add(idx)
    lastSpokenS.current = walkS
    deviceSpeak(alertText(route.alerts[idx]))
    navigator.vibrate?.(VIBRATE_MS)
  }, [live, route, position, alongM, arrived])

  const start = useCallback(
    (next: NavMode) => {
      if (!route) return
      spoken.current = new Set()
      lastSpokenS.current = null
      arrivalSpoken.current = false
      setGpsArrived(false)
      setMode(next)
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
        })
      : null

  return {
    active: live,
    mode,
    arrived,
    position,
    heading: mode === 'gps' ? (gps?.heading ?? null) : null,
    alongM,
    remainingS: route ? remainingSeconds(route.duration_s, totalM, alongM) : 0,
    remainingM: Math.max(0, totalM - alongM),
    instruction,
    start,
    end: endNavigation,
  }
}
