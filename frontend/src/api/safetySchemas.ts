import { z } from 'zod'

/**
 * Personal-safety layer contract (GET /safety/*). Informational only: crime reports are
 * never used to choose routes; lighting and foot traffic feed the optional route preference.
 */

export const CRIME_BANDS = ['lower', 'typical', 'higher'] as const
export const ACTIVITY_BANDS = ['quiet', 'moderate', 'busy'] as const
export const HELP_POINT_KINDS = ['blue_light', 'police', 'fire', 'hospital', 'marta'] as const
export const ROUTE_PREFERENCES = ['lower_traffic_risk', 'lit_and_busy'] as const

export type CrimeBand = (typeof CRIME_BANDS)[number]
export type ActivityBand = (typeof ACTIVITY_BANDS)[number]
export type HelpPointKind = (typeof HELP_POINT_KINDS)[number]
export type RoutePreference = (typeof ROUTE_PREFERENCES)[number]
export const DEFAULT_PREFERENCE: RoutePreference = 'lower_traffic_risk'

const hour = z.number().int().min(0).max(23)
const share = z.number().min(0).max(1)

/** `hours` is a list of hours, a [start, end) pair, or a "22-6" string: all are accepted. */
export const dayPartSchema = z.object({
  key: z.string(),
  label: z.string(),
  hours: z.union([z.array(hour), z.string()]),
})

export const safetyMetaSchema = z.object({
  data_through: z.string(),
  sources: z.array(z.object({ name: z.string(), url: z.string(), license: z.string() })),
  crime_categories: z.array(z.string()),
  day_parts: z.array(dayPartSchema),
})

export const safetyHexSchema = z.object({
  h3: z.string().min(1),
  lat: z.number(),
  lon: z.number(),
  crimes_persons_12mo: z.number().int().nonnegative(),
  crime_band: z.enum(CRIME_BANDS),
  lit_share: share.nullable().default(null),
  activity_band: z.enum(ACTIVITY_BANDS).nullable().default(null),
  help_points: z.number().int().nonnegative(),
})
export const safetyHexesSchema = z.array(safetyHexSchema)

export const helpPointSchema = z.object({
  kind: z.enum(HELP_POINT_KINDS),
  name: z.string(),
  lat: z.number(),
  lon: z.number(),
})

/** A new kind of help point on the server should not blank the whole layer: skip what we can't draw. */
export const helpPointsSchema = z.array(z.unknown()).transform((items) =>
  items.flatMap((item) => {
    const parsed = helpPointSchema.safeParse(item)
    return parsed.success ? [parsed.data] : []
  }),
)

export const routeSafetySchema = z.object({
  lit_share: share.nullable(),
  busy_share: share.nullable(),
  help_points_within_100m: z.number().int().nonnegative(),
  crimes_persons_nearby: z.number().int().nonnegative(),
  day_part: z.string(),
})

export type DayPart = z.infer<typeof dayPartSchema>
export type SafetyMeta = z.infer<typeof safetyMetaSchema>
export type SafetyHex = z.infer<typeof safetyHexSchema>
export type HelpPoint = z.infer<typeof helpPointSchema>
export type RouteSafety = z.infer<typeof routeSafetySchema>
