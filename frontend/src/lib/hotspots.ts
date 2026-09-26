/** Intersection hotspots: node score = max incident segment score; top 5% glow (MAP-03). */

export type HotspotNode = [number, number, number[]] // lon, lat, incident segment ids

export interface Hotspot {
  lon: number
  lat: number
  score: number
  segIds: number[]
}

export const HOTSPOT_SHARE = 0.05
export const HOTSPOT_MIN_SCORE = 75

export function hotspotsFor(nodes: ReadonlyArray<HotspotNode>, frame: Uint8Array): Hotspot[] {
  const scored = nodes.map(([lon, lat, segIds]) => ({
    lon,
    lat,
    segIds,
    score: segIds.reduce((m, id) => Math.max(m, frame[id] ?? 0), 0),
  }))
  if (scored.length === 0) return []
  const sorted = scored.map((n) => n.score).sort((a, b) => b - a)
  const cutoffIdx = Math.max(0, Math.ceil(sorted.length * HOTSPOT_SHARE) - 1)
  const threshold = Math.max(HOTSPOT_MIN_SCORE, sorted[cutoffIdx])
  return scored.filter((n) => n.score >= threshold)
}
