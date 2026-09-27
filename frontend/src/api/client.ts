import type { z } from 'zod'
import {
  askMemoryForgetSchema,
  askMemoryOnSchema,
  askSchema,
  conditionUsedSchema,
  envelope,
  explainSchema,
  geoResultsSchema,
  hourlySchema,
  imagineSchema,
  areaSchema,
  metaSchema,
  reportSchema,
  reportsSchema,
  routesSchema,
  segmentSchema,
  transitStationsSchema,
  type ConditionUsed,
  type Explanation,
  type GeoResult,
  type Hourly,
  type Imagined,
  type Area,
  type AskAnswer,
  type AskContext,
  type Meta,
  type Report,
  type ReportCategory,
  type Routes,
  type SegmentDetail,
  type TransitStation,
  type TravelMode,
} from './schemas'

import { DEFAULT_PREFERENCE, type RoutePreference } from './safetySchemas'
import { demoResponse, isDemoMode } from './demo'
import { getApiOrigin } from './runtime'

/** API prefix: same-origin by default, or the live origin resolved from live.json. */
export function apiBase(): string {
  return `${getApiOrigin()}/api`
}
const TIMEOUT_MS = 8000
/** Image generation takes tens of seconds; the server itself gives up after 60 s. */
const IMAGINE_TIMEOUT_MS = 75_000
/** The server gives Backboard 12 s, then answers with its fallback. */
const ASK_TIMEOUT_MS = 15_000
/** Each voice gets 6 s on the server; Grok then ElevenLabs. */
const TTS_TIMEOUT_MS = 14_000

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

export async function request<T extends z.ZodType>(
  path: string,
  schema: T,
  init?: RequestInit,
  timeoutMs: number = TIMEOUT_MS,
): Promise<z.infer<T>> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
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
/** Viewport as the API's `bbox` query value. */
export function bboxParam(bbox: Bbox): string {
  return bbox.map((v) => v.toFixed(BBOX_DECIMALS)).join(',')
}
export type Condition = 'live' | 'dry' | 'wet'
/** Which of the two routes a navigation alert belongs to. */
export type AlertKind = 'pp' | 'fast'

const VOICE_UNAVAILABLE = 'Voice is unavailable; using the device voice.'

/**
 * One navigation alert in the server voice. Only the route key, alert index, and route kind are
 * sent: the server writes the words. Demo mode never calls the network (device voice only).
 */
async function ttsAlert(routeKey: string, index: number, kind: AlertKind, signal?: AbortSignal): Promise<Blob> {
  if (isDemoMode()) throw new ApiError('DEMO', 'The offline demo uses the device voice.')
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), TTS_TIMEOUT_MS)
  const abort = () => controller.abort()
  signal?.addEventListener('abort', abort, { once: true })
  try {
    const resp = await fetch(`${apiBase()}/tts/alert`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ route_key: routeKey, index, kind }),
      signal: controller.signal,
    })
    const type = resp.headers.get('content-type') ?? ''
    if (resp.ok && type.includes('audio')) return await resp.blob()
    const body = type.includes('json') ? ((await resp.json()) as { error?: { code?: string } }) : null
    throw new ApiError(body?.error?.code ?? 'TTS_UNAVAILABLE', VOICE_UNAVAILABLE)
  } catch (err) {
    if (err instanceof ApiError) throw err
    throw new ApiError('NETWORK', VOICE_UNAVAILABLE)
  } finally {
    clearTimeout(timer)
    signal?.removeEventListener('abort', abort)
  }
}
export interface AskOptions {
  context?: AskContext | null
  memoryToken?: string | null
}

export const api = {
  meta: async (): Promise<Meta> => {
    const meta = await request('/meta', metaSchema)
    // Model files live next to the API; make their paths absolute when the API is remote.
    const origin = isDemoMode() ? '' : getApiOrigin()
    return origin ? { ...meta, static_base: `${origin}${meta.static_base}` } : meta
  },
  /**
   * `prefer` (walks only) and `mode` (rides only) are sent only when they differ from the
   * defaults, so older servers and the recorded demo see the same walking request.
   */
  routes: (
    origin: LatLon,
    destination: LatLon,
    departAt: string,
    cond: Condition,
    prefer: RoutePreference = DEFAULT_PREFERENCE,
    mode: TravelMode = 'walk',
  ): Promise<Routes> =>
    request('/routes', routesSchema, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        origin,
        destination,
        depart_at: departAt,
        cond,
        ...(mode === 'walk' ? {} : { mode }),
        ...(mode !== 'walk' || prefer === DEFAULT_PREFERENCE ? {} : { prefer }),
      }),
    }),
  /** Ride modes index the ride network, so their segment ids need the mode. */
  segment: (id: number, t: string, cond: Condition, mode: TravelMode = 'walk'): Promise<SegmentDetail> =>
    request(`/segments/${id}?t=${encodeURIComponent(t)}&cond=${cond}${mode === 'walk' ? '' : `&mode=${mode}`}`, segmentSchema),
  transitStations: (): Promise<TransitStation[]> => request('/transit/stations', transitStationsSchema),
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
  ttsAlert,
  segmentHourly: (id: number): Promise<Hourly> => request(`/segments/${id}/hourly`, hourlySchema),
  /** Grok Imagine: the server writes the prompt from the street's risk factors; only the id is sent. */
  imagineSegment: (id: number): Promise<Imagined> =>
    request(
      '/imagine/segment',
      imagineSchema,
      { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ seg_id: id }) },
      IMAGINE_TIMEOUT_MS,
    ),
  /**
   * Ask PathPro: the thread id is opaque and sent only when this tab already has one; the
   * context names what is on screen (the server builds the evidence), and the memory token
   * is sent only while the person has memory switched on.
   */
  ask: (question: string, threadId: string | null, opts: AskOptions = {}): Promise<AskAnswer> =>
    request(
      '/ask',
      askSchema,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question,
          ...(threadId ? { thread_id: threadId } : {}),
          ...(opts.context ? { context: opts.context } : {}),
          ...(opts.memoryToken ? { memory_token: opts.memoryToken } : {}),
        }),
      },
      ASK_TIMEOUT_MS,
    ),
  /** Opt-in memory: a private Backboard assistant for this browser, named by a signed token. */
  askMemoryOn: async (): Promise<string> => {
    const data = await request(
      '/ask/memory',
      askMemoryOnSchema,
      { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' },
      ASK_TIMEOUT_MS,
    )
    return data.memory_token
  },
  /** Deletes the private assistant and everything it remembered. */
  askMemoryForget: async (memoryToken: string): Promise<void> => {
    await request(
      '/ask/memory/forget',
      askMemoryForgetSchema,
      { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ memory_token: memoryToken }) },
      ASK_TIMEOUT_MS,
    )
  },
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
    request(`/reports?bbox=${bboxParam(bbox)}`, reportsSchema),
  segmentReports: (id: number): Promise<Report[]> => request(`/segments/${id}/reports`, reportsSchema),
}
