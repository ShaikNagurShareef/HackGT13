import { useCallback, useEffect, useMemo } from 'react'
import type { Meta, ModeInfo, Routes, TravelMode } from '../api/schemas'
import type { HandoffCardProps } from '../components/route/HandoffCard'
import { useTransitStations } from '../hooks/useTransitStations'
import { HANDOFF_MIN_S, martaHandoff, rideSuggestion } from '../lib/handoff'
import { modeInfo, modeOptions, modeUnavailableMessage, resolveMode, speedMps } from '../lib/modes'
import type { Place, ViewState } from '../state/urlState'

export interface TravelModes {
  options: ModeInfo[]
  /** The mode in use: the URL's mode when available here, otherwise Walk. */
  mode: TravelMode
  info: ModeInfo
  speedMps: number
  onMode: (mode: TravelMode) => void
  /** The server said this ride mode can't route here: tell the person and fall back to Walk. */
  onModeUnavailable: (mode: TravelMode) => void
}

interface TravelModesInput {
  meta: Meta | null
  view: ViewState
  update: (patch: Partial<ViewState>) => void
  onNotice: (message: string) => void
}

/** Travel-mode state (Walk · Bike · E-bike · Scooter) on top of the URL and the server's mode list. */
export function useTravelModes({ meta, view, update, onNotice }: TravelModesInput): TravelModes {
  const options = useMemo(() => modeOptions(meta?.modes ?? []), [meta])
  // Until meta arrives the URL's mode is used as-is; a server without it answers MODE_UNAVAILABLE.
  const mode = meta ? resolveMode(view.mode, options) : view.mode
  const requested = view.mode

  useEffect(() => {
    if (!meta || requested === mode) return
    onNotice(modeUnavailableMessage(requested))
    update({ mode, seg: null })
  }, [meta, requested, mode, onNotice, update])

  const onMode = useCallback((next: TravelMode) => update({ mode: next, seg: null }), [update])
  const onModeUnavailable = useCallback(
    (unavailable: TravelMode) => {
      onNotice(modeUnavailableMessage(unavailable))
      update({ mode: 'walk', seg: null })
    },
    [onNotice, update],
  )
  return { options, mode, info: modeInfo(mode, options), speedMps: speedMps(mode, options), onMode, onModeUnavailable }
}

interface HandoffInput {
  routes: Routes | null
  from: Place | null
  to: Place | null
  options: ReadonlyArray<ModeInfo>
  onPlanStation: (place: Place) => void
  onTryMode: (mode: TravelMode) => void
}

/** MARTA hand-off and "Try Bike" for long walks; stations load only once a walk is long enough. */
export function useHandoff({ routes, from, to, options, onPlanStation, onTryMode }: HandoffInput): HandoffCardProps | null {
  const walk = routes && routes.mode === 'walk' ? routes.fastest : null
  const stations = useTransitStations(walk != null && walk.duration_s > HANDOFF_MIN_S)
  if (!walk) return null
  const marta = martaHandoff({ from, to, walkDurationS: walk.duration_s, stations })
  const ride = rideSuggestion({ walkDurationS: walk.duration_s, distanceM: walk.distance_m, options })
  return marta || ride ? { marta, ride, onPlanStation, onTryMode } : null
}
