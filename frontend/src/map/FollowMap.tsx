import { useEffect, useRef, useState } from 'react'
import maplibregl, { type Map as MlMap } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { MapLibreOverlay } from '@deck.gl/maplibre'
import { PathLayer, ScatterplotLayer } from '@deck.gl/layers'
import type { Layer } from '@deck.gl/core'
import { meLayers, type MeMarker } from './layers'

const DARK_STYLE = 'https://tiles.openfreemap.org/styles/dark'
const CENTER: [number, number] = [-84.3905, 33.7765]
// Same generous metro box the API accepts for shared walks.
const MAX_BOUNDS: [[number, number], [number, number]] = [
  [-85.1, 33.1],
  [-83.7, 34.5],
]
const FIT_PADDING = { top: 220, bottom: 60, left: 50, right: 50 }
const FIT_MAX_ZOOM = 16.5
const TEAL: [number, number, number, number] = [63, 209, 198, 230]
const TEAL_HALO: [number, number, number, number] = [63, 209, 198, 60]
const DEST_FILL: [number, number, number, number] = [255, 212, 121, 255]
const DEST_RING: [number, number, number, number] = [7, 18, 29, 255]

type Point = [number, number]

export interface FollowMapProps {
  walker: MeMarker | null
  destination: { lat: number; lon: number } | null
  route: ReadonlyArray<Point> | null
}

function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
}

function webglAvailable(): boolean {
  try {
    const canvas = document.createElement('canvas')
    return Boolean(canvas.getContext('webgl2') ?? canvas.getContext('webgl'))
  } catch {
    return false
  }
}

function followLayers({ walker, destination, route }: FollowMapProps): Layer[] {
  const layers: Layer[] = []
  if (route && route.length > 1) {
    const data = [{ path: route as Point[] }]
    layers.push(
      new PathLayer({ id: 'follow-route-halo', data, getPath: (d) => d.path, getColor: TEAL_HALO, getWidth: 14, widthUnits: 'pixels', capRounded: true, jointRounded: true }),
      new PathLayer({ id: 'follow-route', data, getPath: (d) => d.path, getColor: TEAL, getWidth: 5, widthUnits: 'pixels', capRounded: true, jointRounded: true }),
    )
  }
  if (destination) {
    layers.push(
      new ScatterplotLayer({
        id: 'follow-destination',
        data: [destination],
        getPosition: (d) => [d.lon, d.lat],
        getRadius: 8,
        radiusUnits: 'pixels',
        getFillColor: DEST_FILL,
        stroked: true,
        getLineColor: DEST_RING,
        lineWidthMinPixels: 3,
      }),
    )
  }
  return [...layers, ...meLayers(walker)]
}

function boundsOf(points: Point[]): maplibregl.LngLatBoundsLike {
  const lons = points.map((p) => p[0])
  const lats = points.map((p) => p[1])
  return [
    [Math.min(...lons), Math.min(...lats)],
    [Math.max(...lons), Math.max(...lats)],
  ]
}

/** Follow page map: the walker's dot, the destination pin, and the shared route (if any). */
export function FollowMap(props: FollowMapProps) {
  const container = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MlMap | null>(null)
  const overlayRef = useRef<MapLibreOverlay | null>(null)
  const fitted = useRef(false)
  const [supported] = useState(webglAvailable)

  useEffect(() => {
    if (!container.current || !supported) return
    const map = new maplibregl.Map({
      container: container.current,
      style: DARK_STYLE,
      center: CENTER,
      zoom: 14,
      minZoom: 9,
      maxZoom: 18,
      maxBounds: MAX_BOUNDS,
      attributionControl: { compact: true },
    })
    const overlay = new MapLibreOverlay({ interleaved: false, layers: [] })
    map.addControl(overlay)
    mapRef.current = map
    overlayRef.current = overlay
    return () => {
      map.remove()
      mapRef.current = null
      overlayRef.current = null
    }
  }, [supported])

  // Rebuild layers only when the walk data changes (the page re-renders every second for "12 s ago").
  const { walker, destination, route } = props
  useEffect(() => {
    overlayRef.current?.setProps({ layers: followLayers({ walker, destination, route }) })
  }, [walker, destination, route])

  // Frame the walk once, then keep the walker on screen as they move.
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    const duration = prefersReducedMotion() ? 0 : 700
    const points: Point[] = [...(route ?? []), ...(walker ? [walker.position] : [])]
    if (destination) points.push([destination.lon, destination.lat])
    if (!fitted.current && points.length > 0) {
      fitted.current = true
      map.fitBounds(boundsOf(points), { padding: FIT_PADDING, maxZoom: FIT_MAX_ZOOM, duration })
      return
    }
    if (walker && !map.getBounds().contains(walker.position)) map.easeTo({ center: walker.position, duration })
  }, [walker, destination, route])

  if (!supported) {
    return (
      <div className="map map-fallback" role="img" aria-label="Map unavailable">
        <p>Your browser can't show the live map. The walk details are below.</p>
      </div>
    )
  }
  return <div ref={container} className="map" aria-label="Live map of the shared walk" />
}
