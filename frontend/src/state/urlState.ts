/** Shareable, refresh-safe view state in the URL (PRD §3.3). */

import type { Condition } from '../api/client'
import type { DayGroup } from '../lib/time'

export interface Place {
  lat: number
  lon: number
  label: string
}

export interface ViewState {
  from: Place | null
  to: Place | null
  depart: string // 'now' | '+15m' | '+1h' | ISO
  cond: Condition
  hour: number | null // Risk Tides hour when exploring
  day: DayGroup | null
  seg: number | null
  demo: boolean
}

export const DEFAULT_STATE: ViewState = {
  from: null,
  to: null,
  depart: 'now',
  cond: 'live',
  hour: null,
  day: null,
  seg: null,
  demo: false,
}

const CONDS: ReadonlyArray<Condition> = ['live', 'dry', 'wet']
const DAYS: ReadonlyArray<DayGroup> = ['weekday', 'friday', 'saturday', 'sunday']
const DEPART = /^(now|\+\d{1,3}[mh]|\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?)$/

function parsePlace(raw: string | null): Place | null {
  if (!raw) return null
  const [lat, lon, ...rest] = raw.split(',')
  const la = Number(lat)
  const lo = Number(lon)
  if (!Number.isFinite(la) || !Number.isFinite(lo) || Math.abs(la) > 90 || Math.abs(lo) > 180) {
    return null
  }
  return { lat: la, lon: lo, label: rest.join(',').slice(0, 80) || 'Dropped pin' }
}

function formatPlace(p: Place): string {
  return `${p.lat.toFixed(5)},${p.lon.toFixed(5)},${p.label}`
}

function parseIntIn(raw: string | null, min: number, max: number): number | null {
  if (raw == null || raw === '') return null
  const n = Number(raw)
  return Number.isInteger(n) && n >= min && n <= max ? n : null
}

export function parseState(search: string): ViewState {
  const q = new URLSearchParams(search)
  const cond = q.get('cond') as Condition | null
  const day = q.get('day') as DayGroup | null
  const depart = q.get('t') ?? 'now'
  return {
    from: parsePlace(q.get('from')),
    to: parsePlace(q.get('to')),
    depart: DEPART.test(depart) ? depart : 'now',
    cond: cond && CONDS.includes(cond) ? cond : 'live',
    hour: parseIntIn(q.get('h'), 0, 23),
    day: day && DAYS.includes(day) ? day : null,
    seg: parseIntIn(q.get('seg'), 0, 1_000_000),
    demo: q.get('demo') === '1',
  }
}

export function serializeState(s: ViewState): string {
  const q = new URLSearchParams()
  if (s.from) q.set('from', formatPlace(s.from))
  if (s.to) q.set('to', formatPlace(s.to))
  if (s.depart !== 'now') q.set('t', s.depart)
  if (s.cond !== 'live') q.set('cond', s.cond)
  if (s.hour != null) q.set('h', String(s.hour))
  if (s.day) q.set('day', s.day)
  if (s.seg != null) q.set('seg', String(s.seg))
  if (s.demo) q.set('demo', '1')
  const out = q.toString()
  return out ? `?${out}` : ''
}
