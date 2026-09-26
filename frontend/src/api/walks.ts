import { z } from 'zod'
import { request } from './client'

/** Share my walk: live position, destination, and ETA for a friend (see backend/app/api/walks.py). */

export const walkStatusSchema = z.enum(['walking', 'arrived', 'ended'])
export type WalkStatus = z.infer<typeof walkStatusSchema>

const pointSchema = z.tuple([z.number(), z.number()])

export const createdWalkSchema = z.object({
  walk_id: z.string(),
  owner_token: z.string(),
  follow_path: z.string(),
  expires_at: z.string(),
})
export type CreatedWalk = z.infer<typeof createdWalkSchema>

export const walkSummarySchema = z.object({
  walk_id: z.string(),
  status: walkStatusSchema,
  destination: z.object({ label: z.string(), lat: z.number(), lon: z.number() }),
  eta_s: z.number(),
  eta_at: z.string(),
  position: z
    .object({ lat: z.number(), lon: z.number(), accuracy_m: z.number().nullable(), at: z.string() })
    .nullable(),
  updated_at: z.string(),
  expires_at: z.string(),
})
export type WalkSummary = z.infer<typeof walkSummarySchema>

export const sharedWalkSchema = walkSummarySchema.extend({ route: z.array(pointSchema).nullable() })
export type SharedWalk = z.infer<typeof sharedWalkSchema>

export interface NewWalk {
  destination: { label: string; lat: number; lon: number }
  eta_s: number
  route?: [number, number][]
}

export interface WalkUpdate {
  lat: number
  lon: number
  accuracy_m?: number | null
  eta_s?: number
  status?: WalkStatus
}

const JSON_HEADERS = { 'Content-Type': 'application/json' }
const walkPath = (walkId: string) => `/walks/${encodeURIComponent(walkId)}`

export const walksApi = {
  create: (walk: NewWalk): Promise<CreatedWalk> =>
    request('/walks', createdWalkSchema, { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify(walk) }),
  /** Owner-only: the token is sent in the body, never in the URL. */
  update: (walkId: string, ownerToken: string, update: WalkUpdate): Promise<WalkSummary> =>
    request(`${walkPath(walkId)}/position`, walkSummarySchema, {
      method: 'PUT',
      headers: JSON_HEADERS,
      body: JSON.stringify({ owner_token: ownerToken, ...update }),
    }),
  get: (walkId: string): Promise<SharedWalk> => request(walkPath(walkId), sharedWalkSchema),
}
