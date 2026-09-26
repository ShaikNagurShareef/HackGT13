import { PathLayer, ScatterplotLayer } from '@deck.gl/layers'
import type { Layer, PickingInfo } from '@deck.gl/core'
import type { Route } from '../api/schemas'
import { RAMP, widthFor } from '../lib/bands'
import type { Hotspot } from '../lib/hotspots'

export interface SegmentPath {
  id: number
  path: [number, number][]
  name: string
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
}

const FAST_GREY: [number, number, number, number] = [154, 166, 178, 235]
const TEAL: [number, number, number, number] = [63, 209, 198, 255]
const TEAL_HALO: [number, number, number, number] = [63, 209, 198, 70]

export function buildLayers(input: LayerInput): Layer[] {
  const { frame, frameKey, reducedMotion } = input
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
  return [...layers, ...routeLayers(input.fastest, input.pathpulse)]
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
