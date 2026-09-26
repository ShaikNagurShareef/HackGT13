import type { HelpPointKind } from '../api/safetySchemas'
import { HELP_POINT_KINDS } from '../api/safetySchemas'
import { HELP_POINT_INFO } from '../lib/safety'

/**
 * Help-point badges drawn once onto a canvas atlas. Drawing locally (no data: URLs) keeps
 * the icons working under the production CSP, where connect-src does not allow data:.
 */

const CELL = 64
const INSET = 6
const RADIUS = 16
const RING = 3.5

/** Phone handset (Material "call" icon, Apache-2.0) on a 24 px grid, scaled into the round badge. */
const HANDSET =
  'M6.62 10.79c1.44 2.83 3.76 5.14 6.59 6.59l2.2-2.2c.27-.27.67-.36 1.02-.24 1.12.37 2.33.57 3.57.57.55 0 1 .45 1 1V20c0 .55-.45 1-1 1-9.39 0-17-7.61-17-17 0-.55.45-1 1-1h3.5c.55 0 1 .45 1 1 0 1.25.2 2.45.57 3.57.11.35.03.74-.25 1.02l-2.2 2.2z'
const HANDSET_GRID = 24
const HANDSET_SCALE = 1.4

/** White glyphs on a 64 px badge: shield, flame, cross, "M" (blue-light phones use the handset). */
const GLYPHS: Record<Exclude<HelpPointKind, 'blue_light'>, string> = {
  police: 'M32 13l15 6v12c0 10-7 17-15 20c-8-3-15-10-15-20V19z',
  fire: 'M32 12c7 10 14 16 14 26a14 14 0 0 1-28 0c0-7 5-11 7-17c2 4 4 6 5 8c1-5 1-11 2-17z',
  hospital: 'M27 16h10v11h11v10H37v11H27V37H16V27h11z',
  marta: 'M16 48V16h7l9 15l9-15h7v32h-7V29l-9 14l-9-14v19z',
}

export type IconMapping = Record<HelpPointKind, { x: number; y: number; width: number; height: number; anchorY: number; mask: boolean }>

let atlas: { canvas: HTMLCanvasElement; mapping: IconMapping } | null = null

function drawBadge(ctx: CanvasRenderingContext2D, kind: HelpPointKind, x: number): void {
  const [r, g, b] = HELP_POINT_INFO[kind].rgb
  ctx.save()
  ctx.translate(x, 0)
  ctx.beginPath()
  // Blue-light phones are round (the most recognisable, and the one people look for); the rest are squircles.
  if (kind === 'blue_light') ctx.arc(CELL / 2, CELL / 2, CELL / 2 - INSET, 0, Math.PI * 2)
  else ctx.roundRect(INSET, INSET, CELL - 2 * INSET, CELL - 2 * INSET, RADIUS)
  ctx.fillStyle = `rgb(${r} ${g} ${b})`
  ctx.fill()
  ctx.lineWidth = RING
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.95)'
  ctx.stroke()
  ctx.fillStyle = kind === 'marta' || kind === 'fire' ? '#1a1206' : '#ffffff'
  if (kind === 'blue_light') {
    const offset = (CELL - HANDSET_GRID * HANDSET_SCALE) / 2
    ctx.translate(offset, offset)
    ctx.scale(HANDSET_SCALE, HANDSET_SCALE)
    ctx.fill(new Path2D(HANDSET))
  } else {
    ctx.fill(new Path2D(GLYPHS[kind]))
  }
  ctx.restore()
}

/** Lazily build the atlas (browser only). */
export function helpIconAtlas(): { canvas: HTMLCanvasElement; mapping: IconMapping } {
  if (atlas) return atlas
  const canvas = document.createElement('canvas')
  canvas.width = CELL * HELP_POINT_KINDS.length
  canvas.height = CELL
  const ctx = canvas.getContext('2d')
  const mapping = {} as IconMapping
  HELP_POINT_KINDS.forEach((kind, i) => {
    if (ctx) drawBadge(ctx, kind, i * CELL)
    mapping[kind] = { x: i * CELL, y: 0, width: CELL, height: CELL, anchorY: CELL / 2, mask: false }
  })
  atlas = { canvas, mapping }
  return atlas
}
