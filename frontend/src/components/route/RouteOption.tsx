import type { Route } from '../../api/schemas'
import { cssColor } from '../../lib/bands'
import type { RouteLine } from '../../lib/routeSummary'

export interface RouteOptionProps {
  line: RouteLine
  route: Route
  selected: boolean
  onSelect: (kind: RouteLine['kind']) => void
}

/** One selectable route row: the headline line leads, the risk score sits at the edge. */
export function RouteOption({ line, route, selected, onSelect }: RouteOptionProps) {
  return (
    <button
      type="button"
      className={`route-option route-${line.kind}`}
      data-testid={`route-${line.kind}`}
      aria-pressed={selected}
      onClick={() => onSelect(line.kind)}
    >
      <span className="route-swatch" aria-hidden="true" />
      <span className="route-main">
        <span className="route-label">{line.label}</span>
        <span className="route-title num">{line.title}</span>
        <span className="route-sub num">{line.sub}</span>
      </span>
      <span className="route-score num" style={{ color: cssColor(route.risk_score) }}>
        <span className="route-score-value">{route.risk_score}</span>
        <span className="route-score-band" title={`${route.band} on the citywide 0–100 scale`}>
          risk
        </span>
      </span>
    </button>
  )
}
