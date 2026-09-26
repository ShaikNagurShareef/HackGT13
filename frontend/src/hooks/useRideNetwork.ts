import { useEffect, useState } from 'react'
import type { Meta, ModeInfo } from '../api/schemas'
import { FrameStore } from '../frames/frameStore'
import type { SegmentPath } from '../map/layers'
import { getJson, toSegments, type SegmentCollection } from './bundleFiles'
import { useLatest } from './useLatest'

export interface RideNetwork {
  prefix: string
  segments: SegmentPath[]
  frames: FrameStore
}

const LOAD_FAILED = 'The bike & scooter risk map could not load, so the map shows walking risk.'

/**
 * The ride network's street geometry and Risk Tides frames, loaded the first time a ride mode
 * is chosen (walkers never download it). Same binary frames as walks, under the mode's prefix.
 */
export function useRideNetwork(meta: Meta | null, mode: ModeInfo | null, onError: (message: string) => void): RideNetwork | null {
  const [network, setNetwork] = useState<RideNetwork | null>(null)
  const latest = useLatest(onError)
  const staticBase = meta?.static_base ?? null
  const prefix = mode && mode.network === 'ride' && mode.available ? mode.static_prefix : null
  const declaredSize = mode?.n_segments ?? null
  const loaded = network != null && network.prefix === prefix

  useEffect(() => {
    if (staticBase == null || prefix == null || loaded) return
    let cancelled = false
    getJson<SegmentCollection>(`${staticBase}/${prefix}segments.geojson`)
      .then((geo) => {
        if (cancelled) return
        const segments = toSegments(geo)
        const frames = new FrameStore(staticBase, declaredSize ?? segments.length, undefined, `${prefix}frames`)
        setNetwork({ prefix, segments, frames })
      })
      .catch(() => !cancelled && latest.current(LOAD_FAILED))
    return () => {
      cancelled = true
    }
  }, [staticBase, prefix, declaredSize, loaded, latest])

  return loaded ? network : null
}
