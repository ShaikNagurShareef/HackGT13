/** Static model files next to the API: JSON fetch and street geometry (walk and ride networks). */

import type { SegmentPath } from '../map/layers'

interface GeoJsonLine {
  id: number
  geometry: { coordinates: [number, number][] }
  properties: { n: string }
}

export interface SegmentCollection {
  features: GeoJsonLine[]
}

export async function getJson<T>(url: string): Promise<T> {
  const resp = await fetch(url)
  if (!resp.ok) throw new Error(`failed to load ${url}`)
  return (await resp.json()) as T
}

export function toSegments(geo: SegmentCollection): SegmentPath[] {
  return geo.features.map((f) => ({ id: f.id, path: f.geometry.coordinates, name: f.properties.n }))
}
