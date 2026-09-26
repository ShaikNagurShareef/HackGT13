/** Route sheet copy: Google-Maps-style headline, arrival time, and the evidence fallback line. */

import type { Route, Routes } from '../api/schemas'
import { formatMinutes, formatTime } from './time'

export interface RouteLine {
  kind: 'pp' | 'fast'
  label: string
  title: string
  sub: string
}

export interface RouteSummary {
  primary: RouteLine
  secondary: RouteLine | null
}

export function km(m: number): string {
  return m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m)} m`
}

export function arrivalAt(departAt: string, durationS: number): Date {
  return new Date(new Date(departAt).getTime() + durationS * 1000)
}

function arrive(routes: Routes, route: Route): string {
  return `arrive ${formatTime(arrivalAt(routes.depart_at, route.duration_s))}`
}

function timeCost(minutes: number | null): string {
  const rounded = Math.round(minutes ?? 0)
  return rounded > 0 ? `+${rounded} min vs fastest` : 'About the same time as fastest'
}

export function summarizeRoutes(routes: Routes): RouteSummary {
  const { fastest, pathpro } = routes
  if (!pathpro) {
    return {
      primary: {
        kind: 'fast',
        label: 'Route',
        title: `${formatMinutes(fastest.duration_s)} · already the lower-risk option`,
        sub: arrive(routes, fastest),
      },
      secondary: null,
    }
  }
  return {
    primary: {
      kind: 'pp',
      label: 'PathPro route',
      title: `${formatMinutes(pathpro.duration_s)} · ${routes.exposure_reduction_pct ?? 0}% less traffic risk`,
      sub: `${timeCost(routes.time_cost_min)} · ${arrive(routes, pathpro)}`,
    },
    secondary: {
      kind: 'fast',
      label: 'Fastest route',
      title: formatMinutes(fastest.duration_s),
      sub: `${km(fastest.high_risk_m)} high-risk · ${arrive(routes, fastest)}`,
    },
  }
}

/** One-sentence evidence summary; replaced by the grounded LLM text when it arrives. */
export function templateSummary(routes: Routes): string {
  const { fastest, pathpro } = routes
  const worst = fastest.top_segments.slice(0, 2).map((s) => s.name)
  if (!pathpro) {
    return worst.length
      ? `The fastest route is already the lower-risk option; its busiest stretch is ${worst[0]}.`
      : 'The fastest route is already the lower-risk option.'
  }
  const avoided = worst.filter((n) => !pathpro.top_segments.some((s) => s.name === n))
  const via = avoided.length ? ` by avoiding ${avoided.join(' and ')}` : ''
  return `The PathPro route adds ${routes.time_cost_min} min and cuts traffic-risk exposure ${routes.exposure_reduction_pct}%${via}.`
}
