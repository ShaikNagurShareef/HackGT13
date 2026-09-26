import type { Meta, Report, Route, Routes, SegmentDetail } from '../api/schemas'
import type { HelpPoint, SafetyHex, SafetyMeta } from '../api/safetySchemas'

export const route = (over: Partial<Route> = {}): Route => ({
  coords: [
    [-84.3962, 33.7771],
    [-84.3863, 33.781],
  ],
  duration_s: 1104,
  distance_m: 1432,
  risk_score: 93,
  band: 'High',
  exposure: 2.5,
  high_risk_m: 1262,
  limited_data_m: 0,
  segment_ids: [1, 2],
  alerts: [{ start_m: 300, end_m: 360, names: ['Spring Street'], score: 95, stretches: 1 }],
  top_segments: [
    { seg_id: 11, name: 'Fifth Street Northwest', score: 96 },
    { seg_id: 12, name: 'Peachtree Place Northwest', score: 98 },
  ],
  safety: null,
  ...over,
})

export const routes = (over: Partial<Routes> = {}): Routes => ({
  condition_used: { cond: 'wet', source: 'override', label: 'Wet (your choice)' },
  depart_at: '2026-09-25T22:30:00-04:00',
  fastest: route(),
  pathpro: route({
    duration_s: 1362,
    risk_score: 83,
    exposure: 1.3,
    top_segments: [{ seg_id: 11, name: 'Fifth Street Northwest', score: 96 }],
  }),
  message_code: 'ok',
  message: null,
  time_cost_min: 4.3,
  exposure_reduction_pct: 49,
  unavoidable: ['Fifth Street Northwest'],
  avoided: [{ seg_id: 12, name: 'Peachtree Place Northwest', score: 98 }],
  route_key: 'aaaaaaaaaaaaaaaa',
  reports: [],
  ...over,
})

export const segment = (over: Partial<SegmentDetail> = {}): SegmentDetail => ({
  seg_id: 11,
  name: 'Fifth Street Northwest',
  road_group: 'arterial',
  score: 96,
  band: 'High',
  confidence: 'high',
  baseline_points: 56,
  factors: [
    { key: 'vehicle_crashes', label: 'Vehicle crashes on this street', points: 26 },
    { key: 'intersection', label: 'Intersection complexity', points: 7 },
    { key: 'length', label: 'Block length', points: -6 },
  ],
  remainder_points: 13,
  history: { crashes: 107, ped_crashes: 1, dark_share: 0.16, wet_share: 0.16, period: '2020-2024' },
  condition_used: { cond: 'wet', source: 'override', label: 'Wet (your choice)' },
  at: '2026-09-25T22:30:00-04:00',
  ...over,
})

export const meta = (): Meta => ({
  model_version: 'pp-test',
  data_through: '2026-09-19',
  n_segments: 3,
  coverage_bbox: [-84.415, 33.745, -84.37, 33.795],
  day_groups: ['weekday', 'friday', 'saturday', 'sunday'],
  conditions: ['dry', 'wet'],
  reference_dates: {},
  frame_light: {},
  static_base: '/static/pp-test',
  headline: {
    capture_top10: 0.458,
    capture_top10_ci95: [0.372, 0.556],
    count_only_capture_top10: 0.414,
    capture_at_hin_share: 0.692,
    hin_capture_at_own_share: 0.538,
    test_year: 2024,
  },
  spatial_factors: [],
  temporal_factors: [],
})

export const report = (over: Partial<Report> = {}): Report => ({
  seg_id: 11,
  category: 'construction',
  label: 'Construction detour',
  street: 'Fifth Street Northwest',
  lon: -84.39,
  lat: 33.777,
  confirmations: 2,
  updated_at: '2026-09-26T12:00:00Z',
  expires_at: '2026-10-10T12:00:00Z',
  ...over,
})

const range = (from: number, to: number) => Array.from({ length: to - from }, (_, i) => from + i)

export const safetyMeta = (over: Partial<SafetyMeta> = {}): SafetyMeta => ({
  data_through: '2026-09-19',
  sources: [
    { name: 'Atlanta Police Department Open Data', url: 'https://opendata.atlantapd.org/', license: 'Public records' },
    { name: 'OpenStreetMap', url: 'https://www.openstreetmap.org/copyright', license: 'ODbL' },
  ],
  crime_categories: ['Aggravated assault', 'Robbery'],
  day_parts: [
    { key: 'morning', label: 'Morning', hours: range(6, 11) },
    { key: 'midday', label: 'Midday', hours: range(11, 17) },
    { key: 'evening', label: 'Evening', hours: range(17, 22) },
    { key: 'night', label: 'Late night', hours: [22, 23, ...range(0, 6)] },
  ],
  ...over,
})

export const safetyHex = (over: Partial<SafetyHex> = {}): SafetyHex => ({
  h3: '8944c0a3003ffff',
  lat: 33.777,
  lon: -84.39,
  crimes_persons_12mo: 6,
  crime_band: 'typical',
  lit_share: 0.78,
  activity_band: 'busy',
  help_points: 2,
  ...over,
})

export const helpPoint = (over: Partial<HelpPoint> = {}): HelpPoint => ({
  kind: 'blue_light',
  name: 'Tech Green',
  lat: 33.7745,
  lon: -84.3973,
  ...over,
})
