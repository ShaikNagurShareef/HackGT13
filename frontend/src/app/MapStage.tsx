import { Suspense, lazy, memo } from 'react'
import { ErrorBoundary } from '../components/ErrorBoundary'
import type { MapViewProps } from '../map/MapView'

// Map libraries (MapLibre + deck.gl) are the bulk of the JS. Start downloading them at page
// load, in parallel with the data, and contain a failed download (offline) to the map area.
const mapModule = import('../map/MapView')
const MapView = lazy(() => mapModule.then((m) => ({ default: m.MapView })))

const MAP_UNAVAILABLE = (
  <div className="map map-fallback" role="img" aria-label="Map unavailable">
    <p>The map couldn't load. Route comparisons and street details still work.</p>
  </div>
)

/** Memoised so container re-renders (typing, sheets, timers) don't rebuild the WebGL layers. */
export const MapStage = memo(function MapStage(props: MapViewProps) {
  return (
    <ErrorBoundary fallback={MAP_UNAVAILABLE}>
      <Suspense fallback={<div className="map map-fallback" aria-busy="true" />}>
        <MapView {...props} />
      </Suspense>
    </ErrorBoundary>
  )
})
