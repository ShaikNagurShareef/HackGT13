import type { RefObject } from 'react'
import type { Routes } from '../../api/schemas'
import type { DayPart } from '../../api/safetySchemas'
import { useTypewriter } from '../../hooks/useTypewriter'
import { cssColor } from '../../lib/bands'
import { routeReportsLine } from '../../lib/reports'
import { templateSummary } from '../../lib/routeSummary'
import { formatClock } from '../../lib/time'
import { TrustNote } from '../Controls'
import { Icon } from '../ui/Icon'
import { RouteSafetyEvidence } from './RouteSafetyEvidence'

export interface RouteDetailsProps {
  routes: Routes
  explanation: string | null
  explanationRef: RefObject<HTMLParagraphElement | null>
  onPreview: () => void
  onFocusSegment: (id: number) => void
  onSelectSegment: (id: number) => void
  dayParts: ReadonlyArray<DayPart>
}

/** Expanded route sheet: why, the evidence, and the preview walk. */
export function RouteDetails(props: RouteDetailsProps) {
  const { routes, explanation, explanationRef, onPreview, onFocusSegment, onSelectSegment, dayParts } = props
  const { fastest, pathpro } = routes
  // Typing lives here, not in the app container, so each tick re-renders only this text.
  const typed = useTypewriter(explanation)
  const avoided = routes.avoided
  const stretchWord = avoided.length === 1 ? 'stretch' : 'stretches'
  return (
    <>
      <h3 className="sheet-subhead">Why this route</h3>
      <p className="explanation" data-testid="route-explanation" ref={explanationRef} tabIndex={-1}>
        {typed ?? templateSummary(routes)}
      </p>
      <p className="faint">
        Leaving {formatClock(new Date(routes.depart_at))} · {routes.condition_used.label}
      </p>
      {pathpro && avoided.length > 0 && (
        <div className="avoided" aria-label="High-risk stretches the PathPro route avoids">
          <span className="faint">
            Avoids {avoided.length} high-risk {stretchWord}:
          </span>
          {avoided.slice(0, 4).map((a) => (
            <button key={a.seg_id} type="button" className="chip" onClick={() => onFocusSegment(a.seg_id)}>
              {a.name} <span className="num">{a.score}</span>
            </button>
          ))}
        </div>
      )}
      {routes.message && pathpro && <p className="faint">{routes.message}</p>}
      {routes.reports.length > 0 && (
        <p className="route-reports" data-testid="route-reports">
          <span className="report-dot" aria-hidden="true" /> {routeReportsLine(routes.reports)}
        </p>
      )}
      <RouteSafetyEvidence routes={routes} dayParts={dayParts} />
      {routes.unavoidable.length > 0 && (
        <p className="faint">Both routes use {routes.unavoidable.join(', ')} — take extra care there.</p>
      )}
      <div className="hot-list" aria-label="Highest-risk stretches on the fastest route">
        {fastest.top_segments.map((s) => (
          <button key={s.seg_id} type="button" className="chip" onClick={() => onSelectSegment(s.seg_id)}>
            <span className="dot" style={{ background: cssColor(s.score) }} aria-hidden="true" />
            {s.name} <span className="num">{s.score}</span>
          </button>
        ))}
      </div>
      <button type="button" className="btn preview-btn" onClick={onPreview}>
        <Icon name="play" size={16} /> Preview walk
      </button>
      <TrustNote />
    </>
  )
}
