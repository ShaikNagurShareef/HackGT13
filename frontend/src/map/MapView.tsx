import { useEffect, useRef, useState } from 'react'
import maplibregl, { type Map as MlMap } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { MapLibreOverlay } from '@deck.gl/maplibre'
import type { Bbox } from '../api/client'
import type { Report, Route } from '../api/schemas'
import type { Hotspot } from '../lib/hotspots'
import { buildLayers, type HexInput, type MeMarker, type RouteChoice, type SegmentPath } from './layers'

const DARK_STYLE = 'https://tiles.openfreemap.org/styles/dark'
const CENTER: [number, number] = [-84.3905, 33.7765]
const PHONE_MAX_WIDTH = 760
const DESKTOP_MIN_WIDTH = 1024
const FOLLOW_ZOOM = 17
const RECENTER_ZOOM = 16
const SHEET_SHARE = 0.44 // the route sheet's peek covers roughly this share of a phone screen

export interface MapViewProps {
  bbox: ReadonlyArray<number>
  outlineUrl?: string
  segments: ReadonlyArray<SegmentPath>
  frame: Uint8Array | null
  frameKey: string
  hotspots: ReadonlyArray<Hotspot>
  fastest: Route | null
  pathpro: Route | null
  selectedSeg: number | null
  onSegment: (id: number) => void
  onMapPick: (lat: number, lon: number) => void
  hex?: HexInput | null
  me?: MeMarker | null
  /** Navigation mode: keep the camera on the walker. */
  follow?: boolean
  /** Bump to fly to the walker (locate button). */
  recenterKey?: number
  selectedRoute?: RouteChoice
  focus?: { path: [number, number][]; key: number } | null
  reports?: ReadonlyArray<Report>
  onViewport?: (bbox: Bbox) => void
}

function viewportOf(map: MlMap): Bbox {
  const b = map.getBounds()
  return [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()]
}

function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
}

function isPhone(): boolean {
  return typeof window !== 'undefined' && window.innerWidth <= PHONE_MAX_WIDTH
}

/** Keep routes clear of the floating chrome: bottom sheet on phones, left panel on desktop. */
function routePadding(): maplibregl.PaddingOptions {
  if (isPhone()) return { top: 150, bottom: Math.round(window.innerHeight * SHEET_SHARE), left: 36, right: 36 }
  // Desktop: the sidebar sits beside the map, Risk Tides docks along the bottom.
  if (window.innerWidth >= DESKTOP_MIN_WIDTH) return { top: 60, bottom: 190, left: 60, right: 100 }
  return { top: 110, bottom: 80, left: 440, right: 90 }
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
  const viewportRef = useRef(props.onViewport)
  const outlineRef = useRef<string | undefined>(props.outlineUrl)
  const [supported] = useState(webglAvailable)
  pickRef.current = props.onMapPick
  viewportRef.current = props.onViewport

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
    if (!isPhone()) map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right')
    map.on('contextmenu', (e) => pickRef.current(e.lngLat.lat, e.lngLat.lng))
    map.on('moveend', () => viewportRef.current?.(viewportOf(map)))
    // Keep the attribution as its compact (i) button so it never covers the floating chrome.
    map.once('idle', () => {
      container.current?.querySelector('.maplibregl-compact-show')?.classList.remove('maplibregl-compact-show')
    })
    map.on('load', () => {
      viewportRef.current?.(viewportOf(map))
      const rectangle = {
        type: 'Feature' as const,
        properties: {},
        geometry: {
          type: 'Polygon' as const,
          coordinates: [[[west, south], [east, south], [east, north], [west, north], [west, south]]],
        },
      }
      // Prefer the real city boundary; fall back to the coverage rectangle.
      map.addSource('coverage', { type: 'geojson', data: outlineRef.current ?? rectangle })
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
    const route = props.pathpro ?? props.fastest
    if (!map || !route || route.coords.length < 2) return
    const lons = route.coords.map((c) => c[0])
    const lats = route.coords.map((c) => c[1])
    map.fitBounds(
      [
        [Math.min(...lons), Math.min(...lats)],
        [Math.max(...lons), Math.max(...lats)],
      ],
      { padding: routePadding(), duration: prefersReducedMotion() ? 0 : 700 },
    )
  }, [props.fastest, props.pathpro])

  const mePosition = props.me?.position
  const follow = props.follow ?? false
  useEffect(() => {
    const map = mapRef.current
    if (!map || !follow || !mePosition) return
    map.easeTo({
      center: mePosition,
      zoom: Math.max(map.getZoom(), FOLLOW_ZOOM),
      padding: { top: 140, bottom: 160, left: 0, right: 0 },
      duration: prefersReducedMotion() ? 0 : 600,
    })
  }, [follow, mePosition])

  // Locate: fly to the walker once per tap, as soon as a fix exists (it may arrive after the tap).
  const recenterKey = props.recenterKey ?? 0
  const handledRecenter = useRef(0)
  useEffect(() => {
    const map = mapRef.current
    if (!map || !recenterKey || !mePosition || handledRecenter.current === recenterKey) return
    handledRecenter.current = recenterKey
    map.flyTo({ center: mePosition, zoom: Math.max(map.getZoom(), RECENTER_ZOOM), duration: prefersReducedMotion() ? 0 : 800 })
  }, [recenterKey, mePosition])

  if (!supported) {
    return (
      <div className="map map-fallback" role="img" aria-label="Map unavailable">
        <p>Your browser can't show the live map. Route summaries still work below.</p>
      </div>
    )
  }
  return <div ref={container} className="map" aria-label="Traffic risk map of Midtown, Georgia Tech, and Downtown Atlanta" />
}
