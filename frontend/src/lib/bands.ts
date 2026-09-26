/** Risk bands and the luminance-ordered "Deep water" ramp (PRD §7.2, §7.3, EC-54). */

export type Band = 'Lower' | 'Moderate' | 'Elevated' | 'High'
export type RGB = [number, number, number]

export const BANDS: ReadonlyArray<{ band: Band; min: number; max: number }> = [
  { band: 'Lower', min: 0, max: 24 },
  { band: 'Moderate', min: 25, max: 49 },
  { band: 'Elevated', min: 50, max: 74 },
  { band: 'High', min: 75, max: 100 },
]

export const HIGH_SCORE = 75

export function bandFor(score: number): Band {
  const s = Math.max(0, Math.min(100, Math.round(score)))
  return BANDS.find((b) => s >= b.min && s <= b.max)?.band ?? 'Lower'
}

// Stops in OKLCH with increasing lightness and in-gamut chroma, so WCAG luminance rises
// monotonically and the ramp reads correctly in grayscale.
const STOPS: ReadonlyArray<{ at: number; l: number; c: number; h: number }> = [
  { at: 0, l: 0.38, c: 0.06, h: 210 },
  { at: 25, l: 0.55, c: 0.09, h: 195 },
  { at: 50, l: 0.72, c: 0.12, h: 85 },
  { at: 75, l: 0.78, c: 0.13, h: 45 },
  { at: 100, l: 0.86, c: 0.12, h: 350 },
]

function oklchToRgb(l: number, c: number, hDeg: number): RGB {
  const h = (hDeg * Math.PI) / 180
  const a = c * Math.cos(h)
  const b = c * Math.sin(h)
  const l_ = (l + 0.3963377774 * a + 0.2158037573 * b) ** 3
  const m_ = (l - 0.1055613458 * a - 0.0638541728 * b) ** 3
  const s_ = (l - 0.0894841775 * a - 1.291485548 * b) ** 3
  const lin = [
    4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
    -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
    -0.0041960863 * l_ - 0.7034186147 * m_ + 1.707614701 * s_,
  ]
  const gamma = (x: number) => (x <= 0.0031308 ? 12.92 * x : 1.055 * x ** (1 / 2.4) - 0.055)
  return lin.map((x) => Math.round(255 * Math.min(1, Math.max(0, gamma(x))))) as RGB
}

function interpolateStop(score: number): RGB {
  const hi = STOPS.findIndex((s) => s.at >= score)
  if (hi <= 0) return oklchToRgb(STOPS[0].l, STOPS[0].c, STOPS[0].h)
  const a = STOPS[hi - 1]
  const b = STOPS[hi]
  const t = (score - a.at) / (b.at - a.at)
  let dh = b.h - a.h
  if (Math.abs(dh) > 180) dh -= Math.sign(dh) * 360
  return oklchToRgb(a.l + t * (b.l - a.l), a.c + t * (b.c - a.c), a.h + t * dh)
}

/** 101-entry lookup table: RAMP[score] -> RGB. */
export const RAMP: ReadonlyArray<RGB> = Array.from({ length: 101 }, (_, i) => interpolateStop(i))

export function colorFor(score: number): RGB {
  return RAMP[Math.max(0, Math.min(100, Math.round(score)))]
}

export function cssColor(score: number): string {
  const [r, g, b] = colorFor(score)
  return `rgb(${r} ${g} ${b})`
}

/** Line width in pixels: 1.5 px -> 5 px (PRD §7.2); color is never the only carrier. */
export function widthFor(score: number): number {
  return 1.5 + (3.5 * Math.max(0, Math.min(100, score))) / 100
}

export function relativeLuminance([r, g, b]: RGB): number {
  const lin = (v: number) => {
    const x = v / 255
    return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
}
