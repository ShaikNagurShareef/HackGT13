import { useCallback, useEffect, useRef, useState } from 'react'
import type { Route } from '../api/schemas'
import { walksApi } from '../api/walks'
import { EXPIRED } from '../hooks/useShareWalk'
import type { Navigation } from '../hooks/useNavigation'
import { clearShareSession, loadShareSession, sameDestination, type StoredShareSession } from '../lib/shareSession'
import type { Place } from '../state/urlState'

const STOPPED = 'Stopped sharing your walk.'

export interface ShareResumeDeps {
  demo: boolean
  /** The trip's destination (from the URL, so it survives the reload). */
  destination: Place | null
  /** The selected route, once it has loaded. */
  route: Route | null
  nav: Pick<Navigation, 'active' | 'start'>
  onNotice: (message: string | null) => void
}

export interface ShareResume {
  /** A live walk this tab was sharing before a reload: ask whether to resume it. */
  pending: StoredShareSession | null
  /** The walk the walker chose to resume (navigation or the position-only bar picks it up). */
  resumed: StoredShareSession | null
  resume: () => void
  stopSharing: () => void
}

/**
 * Share my walk after a reload: offers to resume the saved walk. Resuming restarts navigation
 * when its destination matches the trip in the URL (as soon as the route loads); until then, or
 * if it never does, the walk keeps posting the GPS position alone. The demo never resumes.
 */
export function useShareResume({ demo, destination, route, nav, onNotice }: ShareResumeDeps): ShareResume {
  const [pending, setPending] = useState<StoredShareSession | null>(() => (demo ? null : loadShareSession()))
  const [resumed, setResumed] = useState<StoredShareSession | null>(null)
  /** Resumed for the trip's destination: start navigation once its route is ready. */
  const awaitingNav = useRef(false)

  const resume = useCallback(() => {
    setPending(null)
    const stored = loadShareSession()
    if (!stored) {
      onNotice(EXPIRED)
      return
    }
    awaitingNav.current = sameDestination(stored.destination, destination)
    setResumed(stored)
  }, [destination, onNotice])

  // Restore navigation once the route for the resumed destination is ready, if the walk is still live.
  const { active, start } = nav
  useEffect(() => {
    if (!awaitingNav.current || !resumed || !route || active) return
    awaitingNav.current = false
    const stillLive = loadShareSession()?.walk_id === resumed.walk_id
    if (stillLive && sameDestination(resumed.destination, destination)) start('gps')
  }, [resumed, route, active, destination, start])

  const stopSharing = useCallback(() => {
    const stored = pending
    setPending(null)
    onNotice(STOPPED)
    if (!stored) return
    clearShareSession(stored.walk_id)
    // Already gone (404/403) or offline: the link simply expires on its own.
    void walksApi.end(stored.walk_id, stored.owner_token).catch(() => undefined)
  }, [pending, onNotice])

  return { pending, resumed, resume, stopSharing }
}
