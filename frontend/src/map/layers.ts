import { PathLayer, ScatterplotLayer } from '@deck.gl/layers'
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

interface LayerInput {
  segments: ReadonlyArray<SegmentPath>
  frame: Uint8Array | null
  frameKey: string
  hotspots: ReadonlyArray<Hotspot>
  fastest: Route | null
  pathpulse: Route | null
  selectedSeg: number | null
  reducedMotion: boolean
  onSegment: (id: number) => void
  hex?: HexInput | null
  walker?: [number, number] | null
  reports?: ReadonlyArray<Report>
}

const FAST_GREY: [number, number, number, number] = [154, 166, 178, 235]
const TEAL: [number, number, number, number] = [63, 209, 198, 255]
const TEAL_HALO: [number, number, number, number] = [63, 209, 198, 70]
// Violet sits outside the blue→amber→pink risk ramp, so a report never reads as a score.
const REPORT_FILL: [number, number, number, number] = [182, 156, 255, 255]
const REPORT_RING: [number, number, number, number] = [255, 255, 255, 230]
const REPORT_RADIUS_PX = 5
const REPORT_MAX_BOOST = 4

export function buildLayers(input: LayerInput): Layer[] {
  const { frame, frameKey, reducedMotion } = input
  if (input.hex) {
    const h = input.hex
    const hexLayer = buildHexLayer(h.cells, h.frame, h.frameKey, reducedMotion, h.onPick)
    return [hexLayer, ...routeLayers(input.fastest, input.pathpulse), ...walkerLayer(input.walker)]
  }
  const routing = input.fastest != null
  const alpha = routing ? 110 : 230
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
    ...routeLayers(input.fastest, input.pathpulse),
    ...reportLayers(input.reports, input.onSegment),
    ...walkerLayer(input.walker),
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

function walkerLayer(position: [number, number] | null | undefined): Layer[] {
  if (!position) return []
  return [
    new ScatterplotLayer<[number, number]>({
      id: 'walker',
      data: [position],
      getPosition: (d) => d,
      getRadius: 7,
      radiusUnits: 'pixels',
      getFillColor: [255, 255, 255, 255],
      stroked: true,
      getLineColor: [63, 209, 198, 255],
      lineWidthMinPixels: 3,
      updateTriggers: { getPosition: position },
    }),
  ]
}

function routeLayers(fastest: Route | null, pathpulse: Route | null): Layer[] {
  const out: Layer[] = []
  if (fastest) {
    out.push(
      new PathLayer<Route>({
        id: 'route-fastest',
        data: [fastest],
        getPath: (d) => d.coords,
        getColor: FAST_GREY,
        getWidth: 5,
        widthUnits: 'pixels',
        capRounded: true,
        jointRounded: true,
      }),
    )
  }
  if (pathpulse) {
    out.push(
      new PathLayer<Route>({
        id: 'route-pathpulse-halo',
        data: [pathpulse],
        getPath: (d) => d.coords,
        getColor: TEAL_HALO,
        getWidth: 16,
        widthUnits: 'pixels',
        capRounded: true,
        jointRounded: true,
      }),
      new PathLayer<Route>({
        id: 'route-pathpulse',
        data: [pathpulse],
        getPath: (d) => d.coords,
        getColor: TEAL,
        getWidth: 6,
        widthUnits: 'pixels',
        capRounded: true,
        jointRounded: true,
      }),
    )
  }
  return out
}
