/**
 * Ask PathPro context: names what is on screen so the server can build the evidence.
 * Only ids, times, and conditions leave the browser (never GPS, places, or routines).
 */

import type { Condition } from '../api/client'
import type { Area, AskContext, SegmentDetail, TravelMode } from '../api/schemas'
import { atlantaParts, hourLabel } from './time'

export interface AskTarget {
  context: AskContext
  label: string
}

export const ROUTE_ASK_LABEL = 'this route'
export const AREA_ASK_LABEL = 'this area'

/** "Fifth Street Northwest · 10 PM" */
export function segmentAskTarget(detail: SegmentDetail, cond: Condition, mode: TravelMode): AskTarget {
  return {
    context: { kind: 'segment', seg_id: detail.seg_id, t: detail.at, cond, mode },
    label: `${detail.name} · ${hourLabel(atlantaParts(new Date(detail.at)).hour)}`,
  }
}

export function areaAskTarget(area: Area, cond: Condition): AskTarget {
  return { context: { kind: 'area', cell: area.cell, t: area.at, cond }, label: AREA_ASK_LABEL }
}

export function routeAskTarget(routeKey: string): AskTarget {
  return { context: { kind: 'route', route_key: routeKey }, label: ROUTE_ASK_LABEL }
}

/** What is on screen when the map's agent button is tapped. */
export interface OnScreen {
  detail: SegmentDetail | null
  area: Area | null
  routeKey: string | null
  cond: Condition
  mode: TravelMode
}

/**
 * The agent button asks about what is on screen: an open City Pulse area card (it covers the
 * street sheet and route card), else an open street sheet, else the displayed route, else nothing
 * (the server then uses the current conditions). The person can still clear it in the panel.
 */
export function screenAskTarget({ detail, area, routeKey, cond, mode }: OnScreen): AskTarget | null {
  if (area) return areaAskTarget(area, cond)
  if (detail) return segmentAskTarget(detail, cond, mode)
  return routeKey ? routeAskTarget(routeKey) : null
}
