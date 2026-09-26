/** Home status chip: a one-line summary shown only when map options differ from the defaults. */

import type { Condition } from '../api/client'
import type { RoutePreference } from '../api/safetySchemas'
import { MODE_LABELS, isRideMode, type TravelMode } from './modes'
import { hourLabel } from './time'

/** Map scale / layer: traffic risk on streets, City Pulse hexes, or the personal-safety layer. */
export type MapMode = 'streets' | 'city' | 'safety'

export interface OptionsState {
  cond: Condition
  depart: string
  hour: number | null
  cityMode: boolean
  safetyMode?: boolean
  prefer?: RoutePreference
  mode?: TravelMode
}

const RELATIVE = /^\+(\d{1,3})([mh])$/
const WALL_CLOCK = /T(\d{2}):(\d{2})/

/** Departure value as people say it. Custom times are Atlanta wall-clock already. */
export function departLabel(depart: string): string {
  const rel = depart.match(RELATIVE)
  if (rel) return `In ${rel[1]} ${rel[2] === 'h' ? 'h' : 'min'}`
  const clock = depart.match(WALL_CLOCK)
  if (!clock) return 'Now'
  const hour = Number(clock[1])
  const minute = Number(clock[2])
  if (minute === 0) return hourLabel(hour)
  const [h, suffix] = hourLabel(hour).split(' ')
  return `${h}:${clock[2]} ${suffix}`
}

export function statusLabel(s: OptionsState): string | null {
  const ride = s.mode != null && isRideMode(s.mode)
  const parts = [
    ride && s.mode ? MODE_LABELS[s.mode] : null,
    s.cond === 'wet' ? '☂ Wet' : s.cond === 'dry' ? 'Dry' : null,
    s.depart !== 'now' ? departLabel(s.depart) : null,
    s.hour != null ? `Tides ${hourLabel(s.hour)}` : null,
    s.cityMode ? 'City Pulse' : null,
    s.safetyMode ? 'Personal safety' : null,
    !ride && s.prefer === 'lit_and_busy' ? 'Well-lit & busier' : null,
  ].filter((p): p is string => p != null)
  return parts.length ? parts.join(' · ') : null
}
