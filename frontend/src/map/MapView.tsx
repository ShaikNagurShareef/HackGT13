import { useEffect, useRef, useState } from 'react'
import maplibregl, { type Map as MlMap } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { MapLibreOverlay } from '@deck.gl/maplibre'
import type { Route } from '../api/schemas'
import type { Hotspot } from '../lib/hotspots'
import { buildLayers, type HexInput, type SegmentPath } from './layers'

const DARK_STYLE = 'https://tiles.openfreemap.org/styles/dark'
const CENTER: [number, number] = [-84.3905, 33.7765]

export interface MapViewProps {
  bbox: ReadonlyArray<number>
  segments: ReadonlyArray<SegmentPath>
  frame: Uint8Array | null
  frameKey: string
  hotspots: ReadonlyArray<Hotspot>
  fastest: Route | null
  pathpulse: Route | null
  selectedSeg: number | null
  onSegment: (id: number) => void
  onMapPick: (lat: number, lon: number) => void
  hex?: HexInput | null
  walker?: [number, number] | null
  focus?: { path: [number, number][]; key: number } | null
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

export function MapView(props: MapViewProps) {
  const container = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MlMap | null>(null)
  const overlayRef = useRef<MapLibreOverlay | null>(null)
  const pickRef = useRef(props.onMapPick)
  const [supported] = useState(webglAvailable)
  pickRef.current = props.onMapPick

  useEffect(() => {
    if (!container.current || !supported) return
    const [west, south, east, north] = props.bbox
    const map = new maplibregl.Map({
      container: container.current,
      style: DARK_STYLE,
      center: CENTER,
      zoom: 14.2,
      minZoom: 10,
      maxZoom: 18,
      attributionControl: { compact: true },
      maxBounds: [
        [west - 0.25, south - 0.2],
        [east + 0.2, north + 0.2],
      ],
    })
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right')
    map.on('contextmenu', (e) => pickRef.current(e.lngLat.lat, e.lngLat.lng))
    map.on('load', () => {
      map.addSource('coverage', {
        type: 'geojson',
        data: {
          type: 'Feature',
          properties: {},
          geometry: {
            type: 'Polygon',
            coordinates: [[[west, south], [east, south], [east, north], [west, north], [west, south]]],
          },
        },
      })
      map.addLayer({
        id: 'coverage-outline',
        type: 'line',
        source: 'coverage',
        paint: { 'line-color': '#3fd1c6', 'line-opacity': 0.35, 'line-width': 1.2, 'line-dasharray': [3, 3] },
      })
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
    // bbox is fixed per model version; the map is created once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [supported])

  useEffect(() => {
    overlayRef.current?.setProps({
      layers: buildLayers({ ...props, reducedMotion: prefersReducedMotion(), onSegment: props.onSegment }),
    })
  }, [props])

  useEffect(() => {
    const map = mapRef.current
    const path = props.focus?.path
    if (!map || !path?.length) return
    const lons = path.map((c) => c[0])
    const lats = path.map((c) => c[1])
    map.fitBounds(
      [
        [Math.min(...lons), Math.min(...lats)],
        [Math.max(...lons), Math.max(...lats)],
      ],
      { padding: 160, maxZoom: 17, duration: prefersReducedMotion() ? 0 : 700 },
    )
  }, [props.focus])

  const cityMode = Boolean(props.hex)
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    const duration = prefersReducedMotion() ? 0 : 900
    if (cityMode) map.flyTo({ center: [-84.42, 33.765], zoom: 11.2, duration })
    else map.flyTo({ center: CENTER, zoom: 14.2, duration })
  }, [cityMode])

  useEffect(() => {
    const map = mapRef.current
    const route = props.pathpulse ?? props.fastest
    if (!map || !route || route.coords.length < 2) return
    const lons = route.coords.map((c) => c[0])
    const lats = route.coords.map((c) => c[1])
    map.fitBounds(
      [
        [Math.min(...lons), Math.min(...lats)],
        [Math.max(...lons), Math.max(...lats)],
      ],
      { padding: { top: 120, bottom: 220, left: 60, right: 420 }, duration: prefersReducedMotion() ? 0 : 700 },
    )
  }, [props.fastest, props.pathpulse])

  if (!supported) {
    return (
      <div className="map map-fallback" role="img" aria-label="Map unavailable">
        <p>Your browser can't show the live map. Route summaries still work below.</p>
      </div>
    )
  }
  return <div ref={container} className="map" aria-label="Traffic risk map of Midtown, Georgia Tech, and Downtown Atlanta" />
}
