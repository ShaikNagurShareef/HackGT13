import { H3HexagonLayer } from '@deck.gl/geo-layers'
import { IconLayer, ScatterplotLayer, type IconLayerProps } from '@deck.gl/layers'
import type { Layer, PickingInfo } from '@deck.gl/core'
import type { HelpPoint, SafetyHex } from '../api/safetySchemas'
import type { SafetyMapInput } from '../app/useSafetyMode'
import { CRIME_BAND_INFO, hexSummary, helpPointLabel } from '../lib/safety'
import { helpIconAtlas } from './helpIcons'

type RGBA = [number, number, number, number]

const EDGE_ALPHA = 150
const LAMP: [number, number, number] = [255, 238, 196]
const LAMP_BASE_ALPHA = 30
const LAMP_ALPHA_RANGE = 130
const LAMP_RADIUS_PX = 11
const BUSY_RING: RGBA = [205, 232, 255, 225]
const BUSY_RADIUS_PX: Record<'moderate' | 'busy', number> = { moderate: 5, busy: 9 }
const BLUE_LIGHT_PX = 30
const HELP_PX = 22
const TRANSITION_MS = 400

export const SAFETY_TOOLTIP_STYLE = {
  backgroundColor: '#10263a',
  color: '#e7f1f7',
  fontSize: '13px',
  lineHeight: '1.4',
  borderRadius: '10px',
  padding: '8px 10px',
  maxWidth: '260px',
  whiteSpace: 'pre-line',
  border: '1px solid rgba(120, 170, 200, 0.18)',
}

function crimeFill(hex: SafetyHex): RGBA {
  const { rgb, alpha } = CRIME_BAND_INFO[hex.crime_band]
  return [...rgb, alpha]
}

function crimeEdge(hex: SafetyHex): RGBA {
  return [...CRIME_BAND_INFO[hex.crime_band].rgb, EDGE_ALPHA]
}

function crimeLayer(input: SafetyMapInput, reducedMotion: boolean): Layer {
  return new H3HexagonLayer<SafetyHex>({
    id: 'safety-crimes',
    data: input.hexes as SafetyHex[],
    getHexagon: (d) => d.h3,
    getFillColor: crimeFill,
    getLineColor: crimeEdge,
    stroked: true,
    lineWidthUnits: 'pixels',
    getLineWidth: 1,
    extruded: false,
    pickable: true,
    autoHighlight: true,
    highlightColor: [255, 255, 255, 40],
    onClick: (info: PickingInfo<SafetyHex>) => {
      if (info.object) input.onPick({ kind: 'hex', hex: info.object })
    },
    transitions: { getFillColor: reducedMotion ? 0 : TRANSITION_MS },
  })
}

/** Soft lamp-light glows: stronger where more of the area's streets are lit. */
function litLayer(hexes: ReadonlyArray<SafetyHex>): Layer {
  return new ScatterplotLayer<SafetyHex>({
    id: 'safety-lit',
    data: hexes.filter((h) => h.lit_share != null),
    getPosition: (d) => [d.lon, d.lat],
    getRadius: LAMP_RADIUS_PX,
    radiusUnits: 'pixels',
    getFillColor: (d) => [...LAMP, LAMP_BASE_ALPHA + Math.round((d.lit_share ?? 0) * LAMP_ALPHA_RANGE)] as RGBA,
  })
}

/** Open rings where streets are busier: bigger ring, more foot traffic. */
function busyLayer(hexes: ReadonlyArray<SafetyHex>): Layer {
  return new ScatterplotLayer<SafetyHex>({
    id: 'safety-busy',
    data: hexes.filter((h) => h.activity_band === 'moderate' || h.activity_band === 'busy'),
    getPosition: (d) => [d.lon, d.lat],
    getRadius: (d) => BUSY_RADIUS_PX[d.activity_band === 'busy' ? 'busy' : 'moderate'],
    radiusUnits: 'pixels',
    filled: false,
    stroked: true,
    getLineColor: BUSY_RING,
    lineWidthMinPixels: 1.5,
  })
}

function helpLayer(input: SafetyMapInput): Layer {
  const { canvas, mapping } = helpIconAtlas()
  return new IconLayer<HelpPoint>({
    id: 'safety-help',
    // Blue-light phones draw last, on top.
    data: [...input.helpPoints].sort((a, b) => Number(a.kind === 'blue_light') - Number(b.kind === 'blue_light')),
    // deck's `image` prop type turns a canvas into a texture at runtime; the typings only name string | Texture.
    iconAtlas: canvas as unknown as IconLayerProps<HelpPoint>['iconAtlas'],
    iconMapping: mapping,
    getIcon: (d) => d.kind,
    getPosition: (d) => [d.lon, d.lat],
    getSize: (d) => (d.kind === 'blue_light' ? BLUE_LIGHT_PX : HELP_PX),
    sizeUnits: 'pixels',
    pickable: true,
    onClick: (info: PickingInfo<HelpPoint>) => {
      if (info.object) input.onPick({ kind: 'help', point: info.object })
    },
  })
}

/** Personal safety mode: crime hexes (optional), lighting and foot-traffic overlays, help points. */
export function buildSafetyLayers(input: SafetyMapInput, reducedMotion: boolean): Layer[] {
  const { layers, hexes } = input
  return [
    ...(layers.crimes ? [crimeLayer(input, reducedMotion)] : []),
    ...(layers.lit ? [litLayer(hexes)] : []),
    ...(layers.busy ? [busyLayer(hexes)] : []),
    ...(layers.help ? [helpLayer(input)] : []),
  ]
}

/** Desktop hover text for hexes and help points (a tap opens the same content as a card). */
export function safetyTooltip(dayLabel: string | null) {
  return (info: PickingInfo) => {
    const id = info.layer?.id
    if (!info.object) return null
    if (id === 'safety-help') return { text: helpPointLabel(info.object as HelpPoint), style: SAFETY_TOOLTIP_STYLE }
    if (id === 'safety-crimes') {
      const s = hexSummary(info.object as SafetyHex, dayLabel)
      return { text: [s.title, ...s.lines].join('\n'), style: SAFETY_TOOLTIP_STYLE }
    }
    return null
  }
}
