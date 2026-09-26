import { bboxParam, request, type Bbox } from './client'
import {
  helpPointsSchema,
  safetyHexesSchema,
  safetyMetaSchema,
  type HelpPoint,
  type SafetyHex,
  type SafetyMeta,
} from './safetySchemas'

const LAST_HOUR = 23

function hourParam(hour: number): number {
  return Math.min(LAST_HOUR, Math.max(0, Math.round(hour)))
}

/** Personal-safety endpoints. Older bundles answer 503 SAFETY_UNAVAILABLE; callers hide the layer then. */
export const safetyApi = {
  meta: (): Promise<SafetyMeta> => request('/safety/meta', safetyMetaSchema),
  hexes: (bbox: Bbox, hour: number): Promise<SafetyHex[]> =>
    request(`/safety/hexes?bbox=${bboxParam(bbox)}&hour=${hourParam(hour)}`, safetyHexesSchema),
  helpPoints: (bbox: Bbox): Promise<HelpPoint[]> =>
    request(`/safety/help-points?bbox=${bboxParam(bbox)}`, helpPointsSchema),
}
