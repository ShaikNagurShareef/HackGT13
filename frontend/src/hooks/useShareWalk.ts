import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from '../api/client'
import { walksApi, type WalkStatus, type WalkSummary } from '../api/walks'
import { shareLink, type ShareOutcome } from '../lib/share'
import {
  clearShareSession,
  loadShareSession,
  refreshShareExpiry,
  sameDestination,
  saveShareSession,
  type StoredShareSession,
} from '../lib/shareSession'
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
  /** Seconds left; null when unknown (sharing without navigation), so no ETA is sent. */
  remainingS: number | null
  arrived: boolean
  /** On mount, pick up the walk this tab was sharing before a reload (same destination only). */
  resume?: boolean
  /** Default true. False hands the walk on (e.g. to navigation) instead of ending it on unmount. */
  endOnUnmount?: boolean
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
  url: string
  /** What survives a reload; null for a simulated demo walk (no token, nothing sent). */
  stored: StoredShareSession | null
}

type UpdateResult = { kind: 'skipped' } | { kind: 'sent'; summary: WalkSummary } | { kind: 'failed'; code: string }

const OUTCOME_NOTICE: Record<ShareOutcome, string | null> = {
  shared: 'Live link shared.',
  copied: 'Link copied. Paste it to a friend.',
  cancelled: null,
  failed: "Couldn't open sharing. Tap Send link to try again.",
}
const STOPPED = 'Stopped sharing your walk.'
export const EXPIRED = 'Your live link expired. Share again to start a new one.'
const FORBIDDEN = "This live link can't be updated anymore. Share again to start a new one."
const UNAVAILABLE = 'Live sharing is unavailable right now.'
/** Server answers that mean this walk can never be updated again. */
const TERMINAL: Record<string, string> = { WALK_NOT_FOUND: EXPIRED, WALK_FORBIDDEN: FORBIDDEN }

function statusOf(input: ShareWalkInput): WalkStatus {
  return input.arrived ? 'arrived' : 'walking'
}

function etaOf(input: ShareWalkInput): { eta_s?: number } {
  return input.remainingS == null ? {} : { eta_s: Math.max(0, Math.round(input.remainingS)) }
}

/** One position update; never throws. */
async function postUpdate(session: Session, input: ShareWalkInput, status: WalkStatus): Promise<UpdateResult> {
  if (!session.stored || !input.position) return { kind: 'skipped' }
  const [lon, lat] = input.position
  try {
    const summary = await walksApi.update(session.walkId, session.stored.owner_token, {
      lat,
      lon,
      accuracy_m: input.accuracy,
      ...etaOf(input),
      status,
    })
    return { kind: 'sent', summary }
  } catch (err) {
    return { kind: 'failed', code: err instanceof ApiError ? err.code : 'NETWORK' }
  }
}

/** Mark the shared walk ended; one retry if it raced a position update. Without a fix, re-send the last one. */
async function endWalk(session: Session, input: ShareWalkInput): Promise<void> {
  if (!session.stored) return
  if (!input.position) {
    await walksApi.end(session.walkId, session.stored.owner_token).catch(() => undefined)
    return
  }
  const first = await postUpdate(session, input, 'ended')
  if (first.kind !== 'failed' || first.code !== 'WALK_THROTTLED') return
  await new Promise((resolve) => window.setTimeout(resolve, FINAL_RETRY_MS))
  await postUpdate(session, input, 'ended')
}

async function openSession(input: ShareWalkInput, destination: NonNullable<ShareWalkInput['destination']>): Promise<Session> {
  const origin = window.location.origin
  if (input.demo) {
    const walkId = `demo-${Math.random().toString(36).slice(2, 10)}`
    return { walkId, url: followUrl(origin, walkId, true), stored: null }
  }
  const created = await walksApi.create({
    destination,
    eta_s: etaOf(input).eta_s ?? 0,
    ...(input.route?.length ? { route: downsampleRoute(input.route) } : {}),
  })
  const stored: StoredShareSession = { ...created, destination }
  return { walkId: created.walk_id, url: followUrl(origin, created.walk_id, false), stored }
}

/** The walk this tab was sharing before a reload, if it is still live and goes to the same place. */
function storedSessionFor(input: ShareWalkInput): Session | null {
  if (!input.resume || input.demo) return null
  const stored = loadShareSession()
  if (!stored || !sameDestination(stored.destination, input.destination)) return null
  return { walkId: stored.walk_id, url: followUrl(window.location.origin, stored.walk_id, false), stored }
}

/**
 * Share my walk: creates a followable walk, posts the navigation position every ~5 s and on
 * arrival, and marks it ended when navigation ends (unless the walker already arrived). The live
 * session is kept in sessionStorage so a reload can resume it (see lib/shareSession).
 */
export function useShareWalk(input: ShareWalkInput): ShareWalk {
  const [phase, setPhase] = useState<SharePhase>('idle')
  const [url, setUrl] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const latestRef = useLatest(input)
  const session = useRef<Session | null>(null)
  const starting = useRef(false)
  const inFlight = useRef(false)
  const pendingEnd = useRef<number | null>(null)

  /** This walk is over for good: forget it here and in storage. */
  const finish = useCallback((current: Session, message: string) => {
    if (session.current === current) session.current = null
    clearShareSession(current.walkId)
    setPhase('idle')
    setUrl(null)
    setNotice(message)
  }, [])

  const send = useCallback(
    async (status: WalkStatus, force = false) => {
      const current = session.current
      if (!current || (inFlight.current && !force)) return
      inFlight.current = true
      const result = await postUpdate(current, latestRef.current, status)
      inFlight.current = false
      if (session.current !== current) return
      if (result.kind === 'sent') {
        if (result.summary.status === 'ended') finish(current, STOPPED)
        else if (status !== 'arrived') refreshShareExpiry(current.walkId, result.summary.expires_at)
        return
      }
      // Throttled or offline: the next tick retries.
      if (result.kind === 'failed' && TERMINAL[result.code]) finish(current, TERMINAL[result.code])
    },
    [latestRef, finish],
  )

  const shareUrl = useCallback(async (link: string) => {
    const place = latestRef.current.destination?.label ?? 'my destination'
    const outcome = await shareLink(link, SHARE_TITLE, `I'm walking to ${place}. Follow along live:`)
    setNotice(OUTCOME_NOTICE[outcome])
  }, [latestRef])

  const start = useCallback(async () => {
    if (session.current) return shareUrl(session.current.url)
    const destination = latestRef.current.destination
    if (starting.current || !destination) return
    starting.current = true
    setPhase('starting')
    try {
      const next = await openSession(latestRef.current, destination)
      session.current = next
      if (next.stored) saveShareSession(next.stored)
      setUrl(next.url)
      setPhase('live')
      await Promise.all([send(statusOf(latestRef.current), true), shareUrl(next.url)])
    } catch (err) {
      setPhase('idle')
      setNotice(err instanceof ApiError ? err.message : UNAVAILABLE)
    } finally {
      starting.current = false
    }
  }, [latestRef, send, shareUrl])

  const stop = useCallback(() => {
    const current = session.current
    session.current = null
    setPhase('idle')
    setUrl(null)
    setNotice(STOPPED)
    if (!current) return
    clearShareSession(current.walkId)
    void endWalk(current, latestRef.current)
  }, [latestRef])

  /** Navigation ended: end the shared walk unless the walker arrived (or it already ended). */
  const endAfterUnmount = useCallback(
    (current: Session) => {
      pendingEnd.current = null
      if (session.current !== current) return
      session.current = null
      if (!latestRef.current.arrived) void endWalk(current, latestRef.current)
    },
    [latestRef],
  )

  // Mount: resume a walk from before a reload. Unmount: forget it and end it (unless handing it
  // on). The end is deferred one tick so StrictMode's simulated unmount/remount keeps it going.
  useEffect(() => {
    if (pendingEnd.current != null) window.clearTimeout(pendingEnd.current)
    pendingEnd.current = null
    const endOnUnmount = latestRef.current.endOnUnmount !== false
    const kept = session.current
    if (kept?.stored) saveShareSession(kept.stored)
    const resumed = kept ? null : storedSessionFor(latestRef.current)
    if (resumed) {
      session.current = resumed
      setUrl(resumed.url)
      setPhase('live')
      void send(statusOf(latestRef.current), true)
    }
    return () => {
      const current = session.current
      if (!current || !endOnUnmount) return
      clearShareSession(current.walkId)
      pendingEnd.current = window.setTimeout(() => endAfterUnmount(current), 0)
    }
  }, [latestRef, send, endAfterUnmount])

  // Regular position updates while live.
  useEffect(() => {
    if (phase !== 'live') return
    const id = window.setInterval(() => void send(statusOf(latestRef.current)), SHARE_UPDATE_MS)
    return () => window.clearInterval(id)
  }, [phase, send, latestRef])

  // Arrival goes out immediately (status changes are never throttled server-side); the walk is
  // done, so a reload no longer offers to resume it.
  const arrived = input.arrived
  useEffect(() => {
    const current = session.current
    if (phase !== 'live' || !arrived || !current) return
    clearShareSession(current.walkId)
    void send('arrived', true)
  }, [phase, arrived, send])

  const clearNotice = useCallback(() => setNotice(null), [])
  return { phase, followUrl: url, notice, start, resend: start, stop, clearNotice }
}
