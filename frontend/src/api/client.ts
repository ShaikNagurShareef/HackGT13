import type { z } from 'zod'
import {
  conditionUsedSchema,
  envelope,
  explainSchema,
  geoResultsSchema,
  hourlySchema,
  areaSchema,
  metaSchema,
  reportSchema,
  reportsSchema,
  routesSchema,
  segmentSchema,
  type ConditionUsed,
  type Explanation,
  type GeoResult,
  type Hourly,
  type Area,
  type Meta,
  type Report,
  type ReportCategory,
  type Routes,
  type SegmentDetail,
} from './schemas'

import { demoResponse, isDemoMode } from './demo'
import { getApiOrigin } from './runtime'

/** API prefix: same-origin by default, or the live origin resolved from live.json. */
export function apiBase(): string {
  return `${getApiOrigin()}/api`
}
const TIMEOUT_MS = 8000

export class ApiError extends Error {
  readonly code: string

  constructor(code: string, message: string) {
    super(message)
    this.code = code
  }
}

async function fetchJson(url: string, init: RequestInit): Promise<unknown> {
  const resp = await fetch(url, init)
  const type = resp.headers.get('content-type') ?? ''
  if (!type.includes('json')) {
    throw new ApiError('SERVER', 'PathPro is busy right now. Please try again.')
  }
  return resp.json()
}

async function request<T extends z.ZodType>(
  path: string,
  schema: T,
  init?: RequestInit,
): Promise<z.infer<T>> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS)
  try {
    const raw = isDemoMode()
      ? await demoResponse(init?.method ?? 'GET', path, init?.body as string | undefined)
      : await fetchJson(`${apiBase()}${path}`, { ...init, signal: controller.signal })
    const parsed = envelope(schema).safeParse(raw)
    if (!parsed.success) throw new ApiError('BAD_RESPONSE', 'Unexpected response from PathPro.')
    const body = parsed.data
    if (!body.success || body.data == null) {
      throw new ApiError(body.error?.code ?? 'UNKNOWN', body.error?.message ?? 'Request failed.')
    }
    return body.data
  } catch (err) {
    if (err instanceof ApiError) throw err
    throw new ApiError('NETWORK', "You're offline. Map still works; routing needs a connection.")
  } finally {
    clearTimeout(timer)
  }
}

export type LatLon = { lat: number; lon: number }
/** [minLon, minLat, maxLon, maxLat] */
export type Bbox = readonly [number, number, number, number]
const BBOX_DECIMALS = 5
export type Condition = 'live' | 'dry' | 'wet'

export const api = {
  meta: async (): Promise<Meta> => {
    const meta = await request('/meta', metaSchema)
    // Model files live next to the API; make their paths absolute when the API is remote.
    const origin = isDemoMode() ? '' : getApiOrigin()
    return origin ? { ...meta, static_base: `${origin}${meta.static_base}` } : meta
  },
  routes: (origin: LatLon, destination: LatLon, departAt: string, cond: Condition): Promise<Routes> =>
    request('/routes', routesSchema, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ origin, destination, depart_at: departAt, cond }),
    }),
  segment: (id: number, t: string, cond: Condition): Promise<SegmentDetail> =>
    request(`/segments/${id}?t=${encodeURIComponent(t)}&cond=${cond}`, segmentSchema),
  explainRoute: (routeKey: string): Promise<Explanation> =>
    request('/explain', explainSchema, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind: 'route', route_key: routeKey }),
    }),
  explainSegment: (id: number, t: string, cond: Condition): Promise<Explanation> =>
    request('/explain', explainSchema, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind: 'segment', seg_id: id, t, cond }),
    }),
  segmentHourly: (id: number): Promise<Hourly> => request(`/segments/${id}/hourly`, hourlySchema),
  areaAt: (lat: number, lon: number, t: string, cond: Condition): Promise<Area> =>
    request(`/areas/lookup?lat=${lat}&lon=${lon}&t=${encodeURIComponent(t)}&cond=${cond}`, areaSchema),
  area: (cell: string, t: string, cond: Condition): Promise<Area> =>
    request(`/areas/${cell}?t=${encodeURIComponent(t)}&cond=${cond}`, areaSchema),
  liveConditions: (): Promise<ConditionUsed> => request('/conditions/live', conditionUsedSchema),
  geocode: (q: string): Promise<GeoResult[]> =>
    request(`/geocode?q=${encodeURIComponent(q)}`, geoResultsSchema),
  /** Community street reports: the server locates the report from the segment. */
  postReport: (segId: number, category: ReportCategory): Promise<Report> =>
    request('/reports', reportSchema, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ seg_id: segId, category }),
    }),
  reportsInBbox: (bbox: Bbox): Promise<Report[]> =>
    request(`/reports?bbox=${bbox.map((v) => v.toFixed(BBOX_DECIMALS)).join(',')}`, reportsSchema),
  segmentReports: (id: number): Promise<Report[]> => request(`/segments/${id}/reports`, reportsSchema),
}
