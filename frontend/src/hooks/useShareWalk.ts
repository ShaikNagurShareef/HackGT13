import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from '../api/client'
import { walksApi, type WalkStatus } from '../api/walks'
import { shareLink, type ShareOutcome } from '../lib/share'
import { downsampleRoute, followUrl } from '../lib/shareWalk'
import { useLatest } from './useLatest'

export const SHARE_UPDATE_MS = 5000
const FINAL_RETRY_MS = 1500
const SHARE_TITLE = 'Follow my walk on PathPro'

export type SharePhase = 'idle' | 'starting' | 'live'

export interface ShareWalkInput {
  /** Offline demo: sharing is simulated on-device, nothing is sent. */
  demo: boolean
  destination: { label: string; lat: number; lon: number } | null
  route: ReadonlyArray<[number, number]> | null
  /** [lon, lat] from the navigation GPS watch (or the preview walker). */
  position: [number, number] | null
  accuracy: number | null
  remainingS: number
  arrived: boolean
}

export interface ShareWalk {
  phase: SharePhase
  followUrl: string | null
  notice: string | null
  /** Start sharing (create the walk, then open the share sheet); when live, re-send the link. */
  start: () => Promise<void>
  /** Re-share the follow link, starting a walk first if needed ("Share my location"). */
  resend: () => Promise<void>
  stop: () => void
  clearNotice: () => void
}

interface Session {
  walkId: string
  /** Null for a simulated demo walk. */
  token: string | null
  url: string
}

const OUTCOME_NOTICE: Record<ShareOutcome, string | null> = {
  shared: 'Live link shared.',
  copied: 'Link copied. Paste it to a friend.',
  cancelled: null,
  failed: "Couldn't open sharing. Tap Send link to try again.",
}
const STOPPED = 'Stopped sharing your walk.'
const EXPIRED = 'Your live link expired. Share again to start a new one.'
const UNAVAILABLE = 'Live sharing is unavailable right now.'

function statusOf(input: ShareWalkInput): WalkStatus {
  return input.arrived ? 'arrived' : 'walking'
}

/** One position update; resolves to the error code on failure (never throws). */
async function postUpdate(session: Session, input: ShareWalkInput, status: WalkStatus): Promise<string | null> {
  if (!session.token || !input.position) return null
  const [lon, lat] = input.position
  try {
    await walksApi.update(session.walkId, session.token, {
      lat,
      lon,
      accuracy_m: input.accuracy,
      eta_s: Math.max(0, Math.round(input.remainingS)),
      status,
    })
    return null
  } catch (err) {
    return err instanceof ApiError ? err.code : 'NETWORK'
  }
}

/** Mark the shared walk ended; one retry if it raced a position update. */
async function endWalk(session: Session, input: ShareWalkInput): Promise<void> {
  const code = await postUpdate(session, input, 'ended')
  if (code !== 'WALK_THROTTLED') return
  await new Promise((resolve) => window.setTimeout(resolve, FINAL_RETRY_MS))
  await postUpdate(session, input, 'ended')
}

async function openSession(input: ShareWalkInput, destination: NonNullable<ShareWalkInput['destination']>): Promise<Session> {
  const origin = window.location.origin
  if (input.demo) {
    const walkId = `demo-${Math.random().toString(36).slice(2, 10)}`
    return { walkId, token: null, url: followUrl(origin, walkId, true) }
  }
  const created = await walksApi.create({
    destination,
    eta_s: Math.max(0, Math.round(input.remainingS)),
    ...(input.route?.length ? { route: downsampleRoute(input.route) } : {}),
  })
  return { walkId: created.walk_id, token: created.owner_token, url: followUrl(origin, created.walk_id, false) }
}

/**
 * Share my walk: creates a followable walk, posts the navigation position every ~5 s and on
 * arrival, and marks it ended when navigation ends (unless the walker already arrived).
 */
export function useShareWalk(input: ShareWalkInput): ShareWalk {
  const [phase, setPhase] = useState<SharePhase>('idle')
  const [url, setUrl] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const latest = useLatest(input)
  const session = useRef<Session | null>(null)
  const starting = useRef(false)
  const inFlight = useRef(false)

  const send = useCallback(
    async (status: WalkStatus, force = false) => {
      const current = session.current
      if (!current || (inFlight.current && !force)) return
      inFlight.current = true
      const code = await postUpdate(current, latest.current, status)
      inFlight.current = false
      if (code !== 'WALK_NOT_FOUND' || session.current !== current) return // throttled/offline: next tick retries
      session.current = null
      setPhase('idle')
      setUrl(null)
      setNotice(EXPIRED)
    },
    [latest],
  )

  const shareUrl = useCallback(async (link: string) => {
    const place = latest.current.destination?.label ?? 'my destination'
    const outcome = await shareLink(link, SHARE_TITLE, `I'm walking to ${place}. Follow along live:`)
    setNotice(OUTCOME_NOTICE[outcome])
  }, [latest])

  const start = useCallback(async () => {
    if (session.current) return shareUrl(session.current.url)
    const destination = latest.current.destination
    if (starting.current || !destination) return
    starting.current = true
    setPhase('starting')
    try {
      const next = await openSession(latest.current, destination)
      session.current = next
      setUrl(next.url)
      setPhase('live')
      await Promise.all([send(statusOf(latest.current), true), shareUrl(next.url)])
    } catch (err) {
      setPhase('idle')
      setNotice(err instanceof ApiError ? err.message : UNAVAILABLE)
    } finally {
      starting.current = false
    }
  }, [latest, send, shareUrl])

  const stop = useCallback(() => {
    const current = session.current
    session.current = null
    setPhase('idle')
    setUrl(null)
    setNotice(STOPPED)
    if (current) void endWalk(current, latest.current)
  }, [latest])

  // Regular position updates while live.
  useEffect(() => {
    if (phase !== 'live') return
    const id = window.setInterval(() => void send(statusOf(latest.current)), SHARE_UPDATE_MS)
    return () => window.clearInterval(id)
  }, [phase, send, latest])

  // Arrival goes out immediately (status changes are never throttled server-side).
  const arrived = input.arrived
  useEffect(() => {
    if (phase === 'live' && arrived) void send('arrived', true)
  }, [phase, arrived, send])

  // Navigation ended (this hook unmounts): end the shared walk unless the walker arrived.
  useEffect(
    () => () => {
      const current = session.current
      session.current = null
      if (current && !latest.current.arrived) void endWalk(current, latest.current)
    },
    [latest],
  )

  const clearNotice = useCallback(() => setNotice(null), [])
  return { phase, followUrl: url, notice, start, resend: start, stop, clearNotice }
}
