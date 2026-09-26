import type { HelpPoint } from '../../api/safetySchemas'
import { helpPointLabel, type SafetyPick } from '../../lib/safety'

export const HELP_LIST_MAX = 6

export interface SafetyHelpListProps {
  points: ReadonlyArray<HelpPoint>
  onPick: (pick: SafetyPick) => void
}

/** Help points in the map view as buttons: the keyboard and screen-reader route to each one's card. */
export function SafetyHelpList({ points, onPick }: SafetyHelpListProps) {
  if (points.length === 0) return null
  // Blue-light phones first (stable sort keeps the server's order otherwise).
  const ordered = [...points].sort((a, b) => Number(b.kind === 'blue_light') - Number(a.kind === 'blue_light'))
  const shown = ordered.slice(0, HELP_LIST_MAX)
  const more = ordered.length - shown.length
  return (
    <div className="safety-help-list">
      <ul aria-label="Help points in view">
        {shown.map((point) => (
          <li key={`${point.kind}-${point.name}-${point.lat}-${point.lon}`}>
            <button type="button" className="help-row" onClick={() => onPick({ kind: 'help', point })}>
              {helpPointLabel(point)}
            </button>
          </li>
        ))}
      </ul>
      {more > 0 && <p className="faint">{more} more on the map</p>}
    </div>
  )
}
