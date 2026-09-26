import { useEffect, useState } from 'react'
import { ApiError } from '../../api/client'
import { walksApi, type SharedWalk } from '../../api/walks'

export const FOLLOW_POLL_MS = 5000
export const FOLLOW_MAX_BACKOFF_MS = 60_000

/** loading → live; `expired` for a missing link, `error` when the first load keeps failing. */
export type FollowState = 'loading' | 'live' | 'expired' | 'error' | 'demo'

export interface FollowWalk {
  state: FollowState
  walk: SharedWalk | null
  /** A poll failed after the walk loaded: the last known position is still shown. */
  reconnecting: boolean
}

interface Snapshot {
  state: FollowState
  walk: SharedWalk | null
  failures: number
}

function backoffMs(failures: number): number {
  return Math.min(FOLLOW_POLL_MS * 2 ** failures, FOLLOW_MAX_BACKOFF_MS)
}

/** Polls GET /walks/{id} about every 5 s, backing off on errors; stops when ended or expired. */
export function useFollowWalk(walkId: string, demo: boolean): FollowWalk {
  const [snap, setSnap] = useState<Snapshot>({ state: 'loading', walk: null, failures: 0 })

  useEffect(() => {
    if (demo) return
    let cancelled = false
    let timer: number | undefined
    let failures = 0

    const poll = async () => {
      try {
        const walk = await walksApi.get(walkId)
        if (cancelled) return
        failures = 0
        setSnap({ state: 'live', walk, failures })
        if (walk.status !== 'ended') timer = window.setTimeout(poll, FOLLOW_POLL_MS)
      } catch (err) {
        if (cancelled) return
        if (err instanceof ApiError && err.code === 'WALK_NOT_FOUND') {
          setSnap({ state: 'expired', walk: null, failures: 0 })
          return
        }
        failures += 1
        setSnap((s) => ({ state: s.walk ? 'live' : 'error', walk: s.walk, failures }))
        timer = window.setTimeout(poll, backoffMs(failures))
      }
    }

    void poll()
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [walkId, demo])

  if (demo) return { state: 'demo', walk: null, reconnecting: false }
  return { state: snap.state, walk: snap.walk, reconnecting: snap.failures > 0 }
}
