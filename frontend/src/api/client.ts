import type { z } from 'zod'
import {
  conditionUsedSchema,
  envelope,
  explainSchema,
  geoResultsSchema,
  metaSchema,
  routesSchema,
  segmentSchema,
  type ConditionUsed,
  type Explanation,
  type GeoResult,
  type Meta,
  type Routes,
  type SegmentDetail,
} from './schemas'

import { demoResponse, isDemoMode } from './demo'

export const API_BASE = '/api'
const TIMEOUT_MS = 8000

export class ApiError extends Error {
  readonly code: string

  constructor(code: string, message: string) {
    super(message)
    this.code = code
  }
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
      : await (await fetch(`${API_BASE}${path}`, { ...init, signal: controller.signal })).json()
    const parsed = envelope(schema).safeParse(raw)
    if (!parsed.success) throw new ApiError('BAD_RESPONSE', 'Unexpected response from PathPulse.')
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
export type Condition = 'live' | 'dry' | 'wet'

export const api = {
  meta: (): Promise<Meta> => request('/meta', metaSchema),
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
  liveConditions: (): Promise<ConditionUsed> => request('/conditions/live', conditionUsedSchema),
  geocode: (q: string): Promise<GeoResult[]> =>
    request(`/geocode?q=${encodeURIComponent(q)}`, geoResultsSchema),
}
