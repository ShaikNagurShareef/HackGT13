import { Suspense, lazy, useEffect, useMemo, useState } from 'react'
import { isDemoMode } from '../api/demo'
import { ErrorBoundary } from '../components/ErrorBoundary'
import { FollowCard } from '../components/share/FollowCard'
import { useFollowWalk } from '../components/share/useFollowWalk'
import type { MeMarker } from '../map/layers'

// MapLibre + deck.gl load in parallel with the first poll; a failed download only hides the map.
const FollowMap = lazy(() => import('../map/FollowMap').then((m) => ({ default: m.FollowMap })))
const CLOCK_TICK_MS = 1000

const MAP_UNAVAILABLE = (
  <div className="map map-fallback" role="img" aria-label="Map unavailable">
    <p>The map couldn't load. The walk details are below.</p>
  </div>
)

/** Ticks once a second so "Updated 12 s ago" stays current between polls. */
function useNow(): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), CLOCK_TICK_MS)
    return () => window.clearInterval(id)
  }, [])
  return now
}

/** /follow/<id>: a friend's view of a shared walk. Standalone: no model bundle, no GPS prompt. */
export function FollowPage({ walkId }: { walkId: string }) {
  const { state, walk, reconnecting } = useFollowWalk(walkId, isDemoMode())
  const now = useNow()
  const position = walk?.position ?? null
  const walker = useMemo<MeMarker | null>(
    () => (position ? { position: [position.lon, position.lat], accuracy: position.accuracy_m, heading: null } : null),
    [position],
  )

  return (
    <main className="app follow-page">
      <ErrorBoundary fallback={MAP_UNAVAILABLE}>
        <Suspense fallback={<div className="map map-fallback" aria-busy="true" />}>
          <FollowMap walker={walker} destination={walk?.destination ?? null} route={walk?.route ?? null} />
        </Suspense>
      </ErrorBoundary>
      <FollowCard state={state} walk={walk} nowMs={now} reconnecting={reconnecting} />
    </main>
  )
}
