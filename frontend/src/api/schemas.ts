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
/** Ask PathPro (Backboard): a validated answer, or the fixed fallback that points to the model card. */
export const askSchema = z.object({
  answer: z.string(),
  thread_id: z.guid().nullable(),
  source: z.enum(['backboard', 'fallback']),
  note: z.string(),
})
export type AskAnswer = z.infer<typeof askSchema>
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
