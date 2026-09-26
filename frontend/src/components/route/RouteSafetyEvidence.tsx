import type { Routes } from '../../api/schemas'
import type { DayPart, RouteSafety } from '../../api/safetySchemas'
import { formatRouteCrimes } from '../../lib/safety'
import { FairnessNote } from '../safety/FairnessNote'

export interface RouteSafetyEvidenceProps {
  routes: Routes
  dayParts: ReadonlyArray<DayPart>
}

/**
 * Expanded route panel only: reported crimes against persons near each route, stated side by
 * side without ranking or labelling either route, with the fairness note one tap away.
 */
export function RouteSafetyEvidence({ routes, dayParts }: RouteSafetyEvidenceProps) {
  const candidates: ReadonlyArray<[string, RouteSafety | null]> = routes.pathpro
    ? [
        ['PathPro route', routes.pathpro.safety],
        ['Fastest route', routes.fastest.safety],
      ]
    : [['This route', routes.fastest.safety]]
  const rows = candidates.flatMap(([name, safety]) => {
    const line = formatRouteCrimes(safety, dayParts)
    return line ? [{ name, line }] : []
  })
  if (rows.length === 0) return null
  return (
    <section className="route-safety-evidence" aria-label="Personal safety along these routes">
      <h3 className="sheet-subhead">Personal safety</h3>
      <ul>
        {rows.map((row) => (
          <li key={row.name}>
            {row.name}: {row.line}
          </li>
        ))}
      </ul>
      <details className="fairness-details">
        <summary>How to read this</summary>
        <FairnessNote />
      </details>
    </section>
  )
}
