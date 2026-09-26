import type { Meta, Route, Routes, SegmentDetail } from '../api/schemas'

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
  ...over,
})

export const routes = (over: Partial<Routes> = {}): Routes => ({
  condition_used: { cond: 'wet', source: 'override', label: 'Wet (your choice)' },
  depart_at: '2026-09-25T22:30:00-04:00',
  fastest: route(),
  pathpulse: route({
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
