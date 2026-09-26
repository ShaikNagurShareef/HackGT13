import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Meta } from '../api/schemas'
import { FrameStore } from '../frames/frameStore'
import type { HotspotNode } from '../lib/hotspots'
import type { SegmentPath } from '../map/layers'

export interface BundleData {
  meta: Meta
  segments: SegmentPath[]
  hotspotNodes: HotspotNode[]
  frames: FrameStore
}

interface GeoJsonLine {
  id: number
  geometry: { coordinates: [number, number][] }
  properties: { n: string }
}

async function getJson<T>(url: string): Promise<T> {
  const resp = await fetch(url)
  if (!resp.ok) throw new Error(`failed to load ${url}`)
  return (await resp.json()) as T
}

/** Loads the model bundle once: meta, street geometry, hotspot nodes, and the frame store. */
export function useBundle(): { data: BundleData | null; error: string | null } {
  const [data, setData] = useState<BundleData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const meta = await api.meta()
        const [geo, hotspotNodes] = await Promise.all([
          getJson<{ features: GeoJsonLine[] }>(`${meta.static_base}/segments.geojson`),
          getJson<HotspotNode[]>(`${meta.static_base}/hotspot_nodes.json`),
        ])
        const segments = geo.features.map((f) => ({
          id: f.id,
          path: f.geometry.coordinates,
          name: f.properties.n,
        }))
        if (!cancelled) {
          setData({ meta, segments, hotspotNodes, frames: new FrameStore(meta.static_base, meta.n_segments) })
        }
      } catch {
        if (!cancelled) setError("Couldn't load the PathPulse map data. Check your connection and refresh.")
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  return { data, error }
}
