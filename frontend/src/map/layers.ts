import { PathLayer, ScatterplotLayer, SolidPolygonLayer } from '@deck.gl/layers'
import type { Layer, PickingInfo } from '@deck.gl/core'
import type { Report, Route } from '../api/schemas'
import { RAMP, widthFor } from '../lib/bands'
import type { Hotspot } from '../lib/hotspots'
import { buildHexLayer } from './hexLayer'

export interface SegmentPath {
  id: number
  path: [number, number][]
  name: string
}

export interface HexInput {
  cells: ReadonlyArray<string>
  frame: Uint8Array | null
  frameKey: string
  onPick: (cell: string) => void
}

/** The walker: GPS fix (with accuracy + heading) or the simulated preview position. */
export interface MeMarker {
  position: [number, number]
  accuracy: number | null
  heading: number | null
}

export type RouteChoice = 'pp' | 'fast'

interface LayerInput {
  segments: ReadonlyArray<SegmentPath>
  frame: Uint8Array | null
  frameKey: string
  hotspots: ReadonlyArray<Hotspot>
  fastest: Route | null
  pathpro: Route | null
  selectedSeg: number | null
  reducedMotion: boolean
  onSegment: (id: number) => void
  hex?: HexInput | null
  me?: MeMarker | null
  selectedRoute?: RouteChoice
  reports?: ReadonlyArray<Report>
}

const FAST_GREY: [number, number, number, number] = [154, 166, 178, 235]
const FAST_PICKED: [number, number, number, number] = [240, 246, 250, 255]
const TEAL: [number, number, number, number] = [63, 209, 198, 255]
const TEAL_HALO: [number, number, number, number] = [63, 209, 198, 70]
// Violet sits outside the blue→amber→pink risk ramp, so a report never reads as a score.
const REPORT_FILL: [number, number, number, number] = [182, 156, 255, 255]
const REPORT_RING: [number, number, number, number] = [255, 255, 255, 230]
const REPORT_RADIUS_PX = 5
const REPORT_MAX_BOOST = 4
const ME_BLUE: [number, number, number, number] = [77, 163, 255, 255]
const ME_HALO: [number, number, number, number] = [77, 163, 255, 46]
const ME_RING: [number, number, number, number] = [255, 255, 255, 255]
const ME_DOT_PX = 7
const HEADING_TIP_M = 26
const HEADING_BASE_M = 9
const HEADING_SPREAD_DEG = 40
const M_PER_DEG_LAT = 111_320
const DIM = 0.45
/** With a route on screen the citywide streets drop to ~35% so the routes stand out. */
const ROUTING_STREET_ALPHA = 90

export function buildLayers(input: LayerInput): Layer[] {
  const { frame, frameKey, reducedMotion } = input
  if (input.hex) {
    const h = input.hex
    const hexLayer = buildHexLayer(h.cells, h.frame, h.frameKey, reducedMotion, h.onPick)
    return [hexLayer, ...routeLayers(input.fastest, input.pathpro, input.selectedRoute), ...meLayers(input.me)]
  }
  const routing = input.fastest != null
  const alpha = routing ? ROUTING_STREET_ALPHA : 230
  const duration = reducedMotion ? 0 : 400
  const score = (id: number) => (frame ? frame[id] : 0)

  const segments = new PathLayer<SegmentPath>({
    id: 'segments',
    data: input.segments,
    getPath: (d) => d.path,
    getColor: (d) => [...RAMP[score(d.id)], alpha] as [number, number, number, number],
    getWidth: (d) => widthFor(score(d.id)),
    widthUnits: 'pixels',
    widthMinPixels: 1,
    capRounded: true,
    jointRounded: true,
    pickable: true,
    autoHighlight: true,
    highlightColor: [255, 212, 121, 200],
    onClick: (info: PickingInfo<SegmentPath>) => {
      if (info.object) input.onSegment(info.object.id)
    },
    updateTriggers: { getColor: [frameKey, routing], getWidth: frameKey },
    transitions: { getColor: duration, getWidth: duration },
  })

  const glow = new ScatterplotLayer<Hotspot>({
    id: 'hotspot-glow',
    data: input.hotspots,
    getPosition: (d) => [d.lon, d.lat],
    getRadius: (d) => 5 + (d.score - 75) * 0.28,
    radiusUnits: 'pixels',
    getFillColor: (d) => [...RAMP[d.score], 55] as [number, number, number, number],
    updateTriggers: { getFillColor: frameKey, getRadius: frameKey },
  })
  const cores = new ScatterplotLayer<Hotspot>({
    id: 'hotspot-core',
    data: input.hotspots,
    getPosition: (d) => [d.lon, d.lat],
    getRadius: 2.5,
    radiusUnits: 'pixels',
    radiusMinPixels: 2.5,
    getFillColor: (d) => [...RAMP[d.score], 255] as [number, number, number, number],
    stroked: true,
    getLineColor: [7, 18, 29, 255],
    lineWidthMinPixels: 1,
    pickable: true,
    onClick: (info: PickingInfo<Hotspot>) => {
      const node = info.object
      if (!node || !frame) return
      const worst = node.segIds.reduce((a, b) => (score(b) > score(a) ? b : a))
      input.onSegment(worst)
    },
    updateTriggers: { getFillColor: frameKey },
  })

  const layers: Layer[] = [segments, glow, cores]
  if (input.selectedSeg != null) {
    const sel = input.segments.find((s) => s.id === input.selectedSeg)
    if (sel) {
      layers.push(
        new PathLayer<SegmentPath>({
          id: 'selected',
          data: [sel],
          getPath: (d) => d.path,
          getColor: [255, 212, 121, 255],
          getWidth: 7,
          widthUnits: 'pixels',
          capRounded: true,
        }),
      )
    }
  }
  return [
    ...layers,
    ...routeLayers(input.fastest, input.pathpro, input.selectedRoute),
    ...reportLayers(input.reports, input.onSegment),
    ...meLayers(input.me),
  ]
}

/** Community street reports: small violet dots; clicking one opens that street's sheet. */
function reportLayers(reports: ReadonlyArray<Report> | undefined, onSegment: (id: number) => void): Layer[] {
  if (!reports?.length) return []
  return [
    new ScatterplotLayer<Report>({
      id: 'community-reports',
      data: reports,
      getPosition: (d) => [d.lon, d.lat],
      getRadius: (d) => REPORT_RADIUS_PX + Math.min(d.confirmations - 1, REPORT_MAX_BOOST),
      radiusUnits: 'pixels',
      getFillColor: REPORT_FILL,
      stroked: true,
      getLineColor: REPORT_RING,
      lineWidthMinPixels: 1.5,
      pickable: true,
      onClick: (info: PickingInfo<Report>) => {
        if (info.object) onSegment(info.object.seg_id)
      },
    }),
  ]
}

/** Offset a [lon, lat] by metres east/north (small distances only). */
function offsetM([lon, lat]: [number, number], east: number, north: number): [number, number] {
  const mPerDegLon = M_PER_DEG_LAT * Math.cos((lat * Math.PI) / 180)
  return [lon + east / mPerDegLon, lat + north / M_PER_DEG_LAT]
}

function headingWedge(position: [number, number], heading: number): [number, number][] {
  const at = (deg: number, m: number) => {
    const r = (deg * Math.PI) / 180
    return offsetM(position, Math.sin(r) * m, Math.cos(r) * m)
  }
  return [at(heading, HEADING_TIP_M), at(heading - HEADING_SPREAD_DEG, HEADING_BASE_M), at(heading + HEADING_SPREAD_DEG, HEADING_BASE_M)]
}

/** Blue "you are here" dot with an accuracy halo (metres) and a heading wedge when known. */
function meLayers(me: MeMarker | null | undefined): Layer[] {
  if (!me) return []
  const out: Layer[] = []
  if (me.accuracy != null) {
    out.push(
      new ScatterplotLayer<MeMarker>({
        id: 'me-accuracy',
        data: [me],
        getPosition: (d) => d.position,
        getRadius: (d) => d.accuracy ?? 0,
        radiusUnits: 'meters',
        getFillColor: ME_HALO,
        updateTriggers: { getPosition: me.position, getRadius: me.accuracy },
      }),
    )
  }
  if (me.heading != null) {
    out.push(
      new SolidPolygonLayer<MeMarker>({
        id: 'me-heading',
        data: [me],
        getPolygon: (d) => headingWedge(d.position, d.heading ?? 0),
        getFillColor: [77, 163, 255, 150],
        updateTriggers: { getPolygon: [me.position, me.heading] },
      }),
    )
  }
  out.push(
    new ScatterplotLayer<MeMarker>({
      id: 'me-dot',
      data: [me],
      getPosition: (d) => d.position,
      getRadius: ME_DOT_PX,
      radiusUnits: 'pixels',
      getFillColor: ME_BLUE,
      stroked: true,
      getLineColor: ME_RING,
      lineWidthMinPixels: 2.5,
      updateTriggers: { getPosition: me.position },
    }),
  )
  return out
}

function withAlpha([r, g, b, a]: [number, number, number, number], factor: number): [number, number, number, number] {
  return [r, g, b, Math.round(a * factor)]
}

function routeLayers(fastest: Route | null, pathpro: Route | null, selected: RouteChoice = 'pp'): Layer[] {
  const fastPicked = selected === 'fast' || !pathpro
  const fast: Layer[] = fastest
    ? [
        new PathLayer<Route>({
          id: 'route-fastest',
          data: [fastest],
          getPath: (d) => d.coords,
          getColor: fastPicked ? FAST_PICKED : FAST_GREY,
          getWidth: fastPicked ? 7 : 5,
          widthUnits: 'pixels',
          capRounded: true,
          jointRounded: true,
        }),
      ]
    : []
  const pp: Layer[] = pathpro
    ? [
        new PathLayer<Route>({
          id: 'route-pathpro-halo',
          data: [pathpro],
          getPath: (d) => d.coords,
          getColor: fastPicked ? withAlpha(TEAL_HALO, DIM) : TEAL_HALO,
          getWidth: 16,
          widthUnits: 'pixels',
          capRounded: true,
          jointRounded: true,
        }),
        new PathLayer<Route>({
          id: 'route-pathpro',
          data: [pathpro],
          getPath: (d) => d.coords,
          getColor: fastPicked ? withAlpha(TEAL, DIM) : TEAL,
          getWidth: 6,
          widthUnits: 'pixels',
          capRounded: true,
          jointRounded: true,
        }),
      ]
    : []
  // The selected route draws on top.
  return fastPicked ? [...pp, ...fast] : [...fast, ...pp]
}
