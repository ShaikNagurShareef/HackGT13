/** Risk Tides frames: one uint8 buffer per (day group, condition), hour-major [24][N]. */

import type { DayGroup } from '../lib/time'

export type Cond = 'dry' | 'wet'
export const HOURS = 24

export class FrameSet {
  readonly buffer: Uint8Array
  readonly nSegments: number

  constructor(buffer: Uint8Array, nSegments: number) {
    if (buffer.length !== HOURS * nSegments) {
      throw new Error(`frame size ${buffer.length} != 24 x ${nSegments}`)
    }
    this.buffer = buffer
    this.nSegments = nSegments
  }

  /** Zero-copy view of one hour's scores (0-100 per segment). */
  hour(h: number): Uint8Array {
    const hh = ((h % HOURS) + HOURS) % HOURS
    return this.buffer.subarray(hh * this.nSegments, (hh + 1) * this.nSegments)
  }

  /** Citywide median score per hour, for the sparkline and screen-reader label. */
  medians(): number[] {
    return Array.from({ length: HOURS }, (_, h) => median(this.hour(h)))
  }
}

export function median(values: Uint8Array): number {
  const counts = new Uint32Array(101)
  for (const v of values) counts[Math.min(100, v)]++
  const half = values.length / 2
  let seen = 0
  for (let s = 0; s <= 100; s++) {
    seen += counts[s]
    if (seen >= half) return s
  }
  return 100
}

export function frameUrl(staticBase: string, day: DayGroup, cond: Cond): string {
  return `${staticBase}/frames_${day}_${cond}.bin`
}

type Fetcher = (url: string) => Promise<ArrayBuffer>

const defaultFetcher: Fetcher = async (url) => {
  const resp = await fetch(url)
  if (!resp.ok) throw new Error(`frame fetch failed: ${resp.status}`)
  return resp.arrayBuffer()
}

/** Caches frame sets so scrubbing never touches the network (EC-56). */
export class FrameStore {
  private readonly cache = new Map<string, Promise<FrameSet>>()
  private readonly staticBase: string
  private readonly nSegments: number
  private readonly fetcher: Fetcher

  constructor(staticBase: string, nSegments: number, fetcher: Fetcher = defaultFetcher) {
    this.staticBase = staticBase
    this.nSegments = nSegments
    this.fetcher = fetcher
  }

  get(day: DayGroup, cond: Cond): Promise<FrameSet> {
    const url = frameUrl(this.staticBase, day, cond)
    let entry = this.cache.get(url)
    if (!entry) {
      entry = this.fetcher(url).then((buf) => new FrameSet(new Uint8Array(buf), this.nSegments))
      entry.catch(() => this.cache.delete(url))
      this.cache.set(url, entry)
    }
    return entry
  }

  /** Warm both conditions for a day group so the Dry/Wet toggle is instant. */
  prefetch(day: DayGroup): void {
    void this.get(day, 'dry').catch(() => undefined)
    void this.get(day, 'wet').catch(() => undefined)
  }
}
