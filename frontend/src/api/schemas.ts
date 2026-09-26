import { z } from 'zod'

const apiError = z.object({ code: z.string(), message: z.string() })

export const envelope = <T extends z.ZodType>(data: T) =>
  z.object({
    success: z.boolean(),
    data: data.nullable().optional(),
    error: apiError.nullable().optional(),
    model_version: z.string().nullable().optional(),
  })

export const factorSchema = z.object({ key: z.string(), label: z.string(), points: z.number() })

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
})

export const routesSchema = z.object({
  condition_used: conditionUsedSchema,
  depart_at: z.string(),
  fastest: routeSchema,
  pathpulse: routeSchema.nullable(),
  message_code: z.string(),
  message: z.string().nullable(),
  time_cost_min: z.number().nullable(),
  exposure_reduction_pct: z.number().nullable(),
  unavoidable: z.array(z.string()),
  avoided: z.array(z.object({ seg_id: z.number(), name: z.string(), score: z.number() })).default([]),
  route_key: z.string(),
})

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
