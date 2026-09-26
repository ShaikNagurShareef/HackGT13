import { useCallback, useEffect, useRef, useState } from 'react'
import type { Route } from '../api/schemas'
import { deviceSpeak } from '../lib/voice'
import { WALK_SPEED_MPS, alertText, cumulativeDistances, dueAlert, pointAlong } from '../lib/walk'

export const PREVIEW_SPEEDUP = 15 // 5x in the PRD; 15x keeps the demo under two minutes
const TICK_MS = 100

export interface PreviewWalk {
  active: boolean
  position: [number, number] | null
  progress: number
  banner: string | null
  start: () => void
  stop: () => void
}

/** Deterministic simulated walk (or ride, at `speedMps`) along a route with spoken alerts (VOX-02/05, EC-44/45). */
export function usePreviewWalk(route: Route | null, voiceOn: boolean, speedMps: number = WALK_SPEED_MPS): PreviewWalk {
  const [active, setActive] = useState(false)
  const [walked, setWalked] = useState(0)
  const [banner, setBanner] = useState<string | null>(null)
  const walkedRef = useRef(0)
  const spoken = useRef<Set<number>>(new Set())
  const lastSpokenS = useRef<number | null>(null)
  const cum = route ? cumulativeDistances(route.coords) : []
  const total = cum.length ? cum[cum.length - 1] : 0

  const stop = useCallback(() => {
    setActive(false)
    setBanner(null)
  }, [])

  const start = useCallback(() => {
    spoken.current = new Set()
    lastSpokenS.current = null
    walkedRef.current = 0
    setWalked(0)
    setBanner(null)
    setActive(true)
  }, [])

  useEffect(() => stop(), [route, stop])

  // Side effects (voice, vibration) live in the interval callback, never in a state updater.
  useEffect(() => {
    if (!active || !route) return
    const id = window.setInterval(() => {
      const next = Math.min(walkedRef.current + (speedMps * PREVIEW_SPEEDUP * TICK_MS) / 1000, total)
      walkedRef.current = next
      setWalked(next)
      const walkS = next / speedMps
      const idx = dueAlert(route.alerts, next, walkS, { spoken: spoken.current, lastSpokenS: lastSpokenS.current })
      if (idx == null) return
      spoken.current.add(idx)
      lastSpokenS.current = walkS
      const text = alertText(route.alerts[idx])
      setBanner(text)
      if (voiceOn) deviceSpeak(text)
      navigator.vibrate?.(200)
    }, TICK_MS)
    return () => window.clearInterval(id)
  }, [active, route, total, voiceOn, speedMps])

  useEffect(() => {
    if (active && total > 0 && walked >= total) setActive(false)
  }, [active, walked, total])

  const position = route && (active || walked > 0) ? pointAlong(route.coords, cum, walked) : null
  return { active, position, progress: total ? walked / total : 0, banner, start, stop }
}
