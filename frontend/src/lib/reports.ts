import type { Report } from '../api/schemas'

/** "2 community reports on this route: Construction detour, Sidewalk blocked" (null when none). */
export function routeReportsLine(reports: ReadonlyArray<Report>): string | null {
  if (reports.length === 0) return null
  const labels = [...new Set(reports.map((r) => r.label))]
  const noun = reports.length === 1 ? 'community report' : 'community reports'
  return `${reports.length} ${noun} on this route: ${labels.join(', ')}`
}

/** "1 walker" / "3 walkers" flagged this. */
export function walkersLabel(confirmations: number): string {
  return `${confirmations} ${confirmations === 1 ? 'walker' : 'walkers'}`
}
