import { useCallback, useMemo, useState } from 'react'
import type { Bbox } from '../api/client'
import type { HelpPoint, SafetyHex, SafetyMeta } from '../api/safetySchemas'
import type { SafetyOptions } from '../components/options/OptionsContent'
import type { SafetyLegendProps } from '../components/safety/SafetyLegend'
import { useSafetyData, type SafetyStatus } from '../hooks/useSafetyData'
import type { MapMode } from '../lib/options'
import { DEFAULT_SAFETY_LAYERS, dayPartFor, type SafetyLayers, type SafetyPick } from '../lib/safety'

/** What the map draws in personal safety mode (see map/safetyLayers.ts). */
export interface SafetyMapInput {
  hexes: ReadonlyArray<SafetyHex>
  helpPoints: ReadonlyArray<HelpPoint>
  layers: SafetyLayers
  dayLabel: string | null
  onPick: (pick: SafetyPick) => void
}

export type SafetyControls = Omit<SafetyOptions, 'prefer' | 'onPrefer'>

export interface SafetyMode {
  status: SafetyStatus
  available: boolean
  meta: SafetyMeta | null
  onViewport: (bbox: Bbox) => void
  dayLabel: string | null
  /** Null outside personal safety mode (or without the layer). */
  mapInput: SafetyMapInput | null
  legend: SafetyLegendProps | null
  /** Null when the server has no safety layer: the mode and preference stay hidden. */
  controls: SafetyControls | null
  pick: SafetyPick | null
  closePick: () => void
}

/** Personal safety map mode: layer toggles, legend, tapped item, and the data behind them. */
export function useSafetyMode(mapMode: MapMode, hour: number): SafetyMode {
  const active = mapMode === 'safety'
  const data = useSafetyData(active, hour)
  const [layers, setLayers] = useState<SafetyLayers>(DEFAULT_SAFETY_LAYERS)
  const [pick, setPick] = useState<SafetyPick | null>(null)
  // A tapped item belongs to the mode it was tapped in: clear it when the mode changes.
  const [pickMode, setPickMode] = useState(active)
  if (pickMode !== active) {
    setPickMode(active)
    setPick(null)
  }

  const { meta, hexes, helpPoints, tooWide, available } = data
  const dayLabel = meta ? (dayPartFor(hour, meta.day_parts)?.label ?? null) : null
  const hasLit = hexes.some((h) => h.lit_share != null)
  const hasBusy = hexes.some((h) => h.activity_band != null)
  const shown = active && available

  const legendProps = useMemo<SafetyLegendProps>(() => ({ meta, hour, layers, tooWide }), [meta, hour, layers, tooWide])
  const mapInput = useMemo<SafetyMapInput | null>(
    () => (shown ? { hexes, helpPoints, layers, dayLabel, onPick: setPick } : null),
    [shown, hexes, helpPoints, layers, dayLabel],
  )
  const controls = useMemo<SafetyControls | null>(
    () => (available ? { legend: legendProps, onLayers: setLayers, hasLit, hasBusy } : null),
    [available, legendProps, hasLit, hasBusy],
  )
  const closePick = useCallback(() => setPick(null), [])

  return {
    status: data.status,
    available,
    meta,
    onViewport: data.onViewport,
    dayLabel,
    mapInput,
    legend: shown ? legendProps : null,
    controls,
    pick,
    closePick,
  }
}
