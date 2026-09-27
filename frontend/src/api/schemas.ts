import { z } from 'zod'
import { routeSafetySchema } from './safetySchemas'

const apiError = z.object({ code: z.string(), message: z.string() })

export const envelope = <T extends z.ZodType>(data: T) =>
  z.object({
    success: z.boolean(),
    data: data.nullable().optional(),
    error: apiError.nullable().optional(),
    model_version: z.string().nullable().optional(),
  })

export const factorSchema = z.object({ key: z.string(), label: z.string(), points: z.number() })

/** Travel modes, in tab order. Walk is the pedestrian network; the others share the ride network. */
export const travelModeSchema = z.enum(['walk', 'bike', 'ebike', 'scooter'])
export type TravelMode = z.infer<typeof travelModeSchema>

/** `static_prefix` is joined into static file URLs, so only a bare lowercase prefix is accepted. */
const STATIC_PREFIX = /^([a-z]+_)?$/

export const modeInfoSchema = z.object({
  key: travelModeSchema,
  label: z.string().min(1).max(24),
  available: z.boolean(),
  speed_kmh: z.number().positive().max(60),
  network: z.enum(['walk', 'ride']),
  static_prefix: z.string().regex(STATIC_PREFIX),
  /** Segments in the mode's network (frame width); defaults to the geometry's feature count. */
  n_segments: z.number().int().positive().optional(),
})
export type ModeInfo = z.infer<typeof modeInfoSchema>

/** Keep the well-formed modes; an unknown or malformed entry never breaks the whole meta. */
const modesSchema = z
  .array(z.unknown())
  .catch([])
  .transform((items) =>
    items.flatMap((item) => {
      const parsed = modeInfoSchema.safeParse(item)
      return parsed.success ? [parsed.data] : []
    }),
  )

export const metaSchema = z.object({
  model_version: z.string(),
  data_through: z.string(),
  n_segments: z.number().int().positive(),
  coverage_bbox: z.array(z.number()).length(4),
  day_groups: z.array(z.string()),
  conditions: z.array(z.string()),
  reference_dates: z.record(z.string(), z.string()),
  frame_light: z.record(z.string(), z.array(z.string())),
  static_base: z.string(),
  headline: z.record(z.string(), z.unknown()),
  spatial_factors: z.array(factorSchema),
  temporal_factors: z.array(factorSchema),
  /** Absent on older servers and the recorded demo: the app then offers Walk only. */
  modes: modesSchema,
  ride_model: z.record(z.string(), z.unknown()).nullable().catch(null),
})

export const conditionUsedSchema = z.object({
  cond: z.enum(['dry', 'wet']),
  source: z.enum(['live', 'override', 'assumed']),
  label: z.string(),
})

export const routeSchema = z.object({
  coords: z.array(z.tuple([z.number(), z.number()])),
  duration_s: z.number(),
  distance_m: z.number(),
  risk_score: z.number().int(),
  band: z.string(),
  exposure: z.number(),
  high_risk_m: z.number(),
  limited_data_m: z.number(),
  segment_ids: z.array(z.number().int()),
  top_segments: z.array(z.object({ seg_id: z.number(), name: z.string(), score: z.number() })),
  alerts: z
    .array(
      z.object({
        start_m: z.number(),
        end_m: z.number(),
        names: z.array(z.string()),
        score: z.number(),
        stretches: z.number(),
      }),
    )
    .default([]),
  /** Personal-safety signals along the route; null on older bundles (or if malformed). */
  safety: routeSafetySchema.nullable().default(null).catch(null),
})

/** Community street report categories (fixed list; no free text). Mirrors backend/app/domain/reports.py. */
export const REPORT_CATEGORIES = [
  'sidewalk_blocked',
  'signal_out',
  'construction',
  'poor_lighting',
  'flooding',
  'fast_traffic',
] as const
export type ReportCategory = (typeof REPORT_CATEGORIES)[number]
export const CATEGORY_LABELS: Record<ReportCategory, string> = {
  sidewalk_blocked: 'Sidewalk blocked',
  signal_out: 'Crossing signal out',
  construction: 'Construction detour',
  poor_lighting: 'Poor street lighting',
  flooding: 'Flooding or standing water',
  fast_traffic: 'Fast-moving traffic',
}

export const reportSchema = z.object({
  seg_id: z.number().int(),
  category: z.enum(REPORT_CATEGORIES),
  label: z.string(),
  street: z.string(),
  lon: z.number(),
  lat: z.number(),
  confirmations: z.number().int().nonnegative(),
  updated_at: z.string(),
  expires_at: z.string(),
})
export const reportsSchema = z.array(reportSchema)
export type Report = z.infer<typeof reportSchema>

export const routesSchema = z.object({
  condition_used: conditionUsedSchema,
  depart_at: z.string(),
  fastest: routeSchema,
  pathpro: routeSchema.nullable(),
  message_code: z.string(),
  message: z.string().nullable(),
  time_cost_min: z.number().nullable(),
  exposure_reduction_pct: z.number().nullable(),
  unavoidable: z.array(z.string()),
  avoided: z.array(z.object({ seg_id: z.number(), name: z.string(), score: z.number() })).default([]),
  route_key: z.string(),
  reports: reportsSchema.default([]),
  mode: travelModeSchema.catch('walk'),
})

/** MARTA rail stations for the transit hand-off. */
export const transitStationsSchema = z.array(
  z.object({ name: z.string().min(1).max(80), lat: z.number(), lon: z.number(), lines: z.array(z.string()).optional() }),
)
export type TransitStation = z.infer<typeof transitStationsSchema>[number]

export const segmentSchema = z.object({
  seg_id: z.number().int(),
  name: z.string(),
  road_group: z.string(),
  score: z.number().int(),
  band: z.string(),
  confidence: z.enum(['high', 'medium', 'limited']),
  baseline_points: z.number().int(),
  factors: z.array(factorSchema),
  remainder_points: z.number().int(),
  history: z.object({
    crashes: z.number(),
    ped_crashes: z.number(),
    dark_share: z.number(),
    wet_share: z.number(),
    period: z.string(),
  }),
  condition_used: conditionUsedSchema,
  at: z.string(),
})

export type Meta = z.infer<typeof metaSchema>
export type Route = z.infer<typeof routeSchema>
export type Routes = z.infer<typeof routesSchema>
export type SegmentDetail = z.infer<typeof segmentSchema>
export type ConditionUsed = z.infer<typeof conditionUsedSchema>

export const explainSchema = z.object({ text: z.string(), source: z.string() })
export const geoResultsSchema = z.array(
  z.object({
    label: z.string(),
    address: z.string(),
    lat: z.number(),
    lon: z.number(),
    in_coverage: z.boolean(),
  }),
)
export type Explanation = z.infer<typeof explainSchema>
export type GeoResult = z.infer<typeof geoResultsSchema>[number]
export const hourlySchema = z.object({
  seg_id: z.number().int(),
  crashes: z.array(z.number()).length(24),
  ped_crashes: z.array(z.number()).length(24),
  source: z.literal('tiger_data'),
})
export type Hourly = z.infer<typeof hourlySchema>
/** Grok Imagine street redesign illustration (backend/app/api/imagine.py). */
export const imagineSchema = z.object({
  seg_id: z.number().int(),
  image_url: z.string().regex(/^\/imagine\/segment\/\d+\.png$/),
  prompt_summary: z.string(),
  fixes: z.array(z.string()),
  label: z.string(),
  cached: z.boolean(),
  /** Gemini's review of the picture; null or absent when it could not be checked. */
  check: z
    .object({
      by: z.literal('gemini'),
      fixes_shown: z.array(z.string()),
      fixes_total: z.number().int().nonnegative(),
    })
    .nullish(),
})
export type Imagined = z.infer<typeof imagineSchema>
/** Server-signed Ask thread token "<uuid>.<sig>"; a bare Backboard thread id never validates. */
export const ASK_THREAD_TOKEN_RE = /^[0-9a-f-]{36}\.[A-Za-z0-9_-]{22,}$/
/** Ask PathPro (Backboard): a validated answer, or the fixed fallback that points to the model card. */
/** A document an answer came from; only plain https links are ever rendered. */
const askSourceSchema = z.object({
  label: z.string().min(1).max(80),
  url: z
    .string()
    .max(500)
    .refine((u) => {
      try {
        return new URL(u).protocol === 'https:'
      } catch {
        return false
      }
    }, 'https only'),
})
export type AskSource = z.infer<typeof askSourceSchema>
/** Invalid entries are dropped one by one, so one bad link never hides the answer. */
const askSourcesSchema = z
  .array(z.unknown())
  .catch([])
  .transform((items) =>
    items.flatMap((item) => {
      const parsed = askSourceSchema.safeParse(item)
      return parsed.success ? [parsed.data] : []
    }),
  )
export const askSchema = z.object({
  answer: z.string(),
  thread_id: z.string().regex(ASK_THREAD_TOKEN_RE).nullable(),
  source: z.enum(['backboard', 'fallback']),
  note: z.string(),
  // v2 fields: tolerant, so an older server (or an odd value) degrades to "no sources, no memory".
  sources: askSourcesSchema,
  memory: z.enum(['on', 'off']).catch('off'),
  context_used: z.enum(['segment', 'route', 'area', 'conditions']).catch('conditions'),
  context_dropped: z.boolean().catch(false),
})
export type AskAnswer = z.infer<typeof askSchema>
/** What the question is about; the server resolves the evidence, the browser only names it. */
export type AskContext =
  | { kind: 'segment'; seg_id: number; t: string; cond: 'live' | 'dry' | 'wet'; mode: TravelMode }
  | { kind: 'route'; route_key: string }
  | { kind: 'area'; cell: string; t: string; cond: 'live' | 'dry' | 'wet' }
export const askMemoryOnSchema = z.object({ memory_token: z.string().regex(ASK_THREAD_TOKEN_RE) })
export const askMemoryForgetSchema = z.object({ forgotten: z.literal(true) })
export const areaSchema = z.object({
  cell: z.string(),
  lat: z.number(),
  lon: z.number(),
  score: z.number().int(),
  band: z.string(),
  confidence: z.enum(['high', 'medium', 'limited']),
  baseline_points: z.number().int(),
  factors: z.array(factorSchema),
  remainder_points: z.number().int(),
  crashes: z.number(),
  ped_crashes: z.number(),
  period: z.string(),
  in_street_coverage: z.boolean(),
  condition_used: conditionUsedSchema,
  at: z.string(),
})
export type Area = z.infer<typeof areaSchema>
