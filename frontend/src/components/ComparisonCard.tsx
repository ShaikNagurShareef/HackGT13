import type { Route, Routes } from '../api/schemas'
import { cssColor } from '../lib/bands'
import { formatClock, formatMinutes } from '../lib/time'
import { TrustNote } from './Controls'

function km(m: number): string {
  return m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m)} m`
}

function RouteRow({ label, route, kind }: { label: string; route: Route; kind: 'fast' | 'pp' }) {
  return (
    <div className={`route-row route-${kind}`} data-testid={`route-${kind}`}>
      <span className="route-swatch" aria-hidden="true" />
      <div className="route-main">
        <div className="route-label">{label}</div>
        <div className="faint num">
          {formatMinutes(route.duration_s)} · {km(route.distance_m)} · {km(route.high_risk_m)} on high-risk streets
        </div>
      </div>
      <div className="route-score num" style={{ color: cssColor(route.risk_score) }}>
        <span className="route-score-value">{route.risk_score}</span>
        <span className="faint">{route.band}</span>
      </div>
    </div>
  )
}

/** One-sentence evidence summary; replaced by the grounded LLM text when it arrives. */
export function templateSummary(routes: Routes): string {
  const { fastest, pathpulse } = routes
  const worst = fastest.top_segments.slice(0, 2).map((s) => s.name)
  if (!pathpulse) {
    return worst.length
      ? `The fastest route is already the lower-risk option; its busiest stretch is ${worst[0]}.`
      : 'The fastest route is already the lower-risk option.'
  }
  const avoided = worst.filter((n) => !pathpulse.top_segments.some((s) => s.name === n))
  const via = avoided.length ? ` by avoiding ${avoided.join(' and ')}` : ''
  return `PathPulse adds ${routes.time_cost_min} min and cuts traffic-risk exposure ${routes.exposure_reduction_pct}%${via}.`
}

export interface ComparisonCardProps {
  routes: Routes
  explanation: string | null
  onClear: () => void
  onSelectSegment: (id: number) => void
}

export function ComparisonCard({ routes, explanation, onClear, onSelectSegment }: ComparisonCardProps) {
  const { fastest, pathpulse } = routes
  const depart = new Date(routes.depart_at)
  return (
    <section className="compare panel" aria-label="Route comparison" aria-live="polite">
      <header className="compare-head">
        <div>
          <div className="compare-title">
            {pathpulse ? (
              <>
                <span className="num">+{routes.time_cost_min} min</span>,{' '}
                <span className="num">{routes.exposure_reduction_pct}%</span> less traffic-risk exposure
              </>
            ) : (
              'The fastest route is already the lower-risk option.'
            )}
          </div>
          <div className="faint">
            Leaving {formatClock(depart)} · {routes.condition_used.label}
          </div>
        </div>
        <button type="button" className="icon-btn" aria-label="Clear route" onClick={onClear}>
          ×
        </button>
      </header>
      {pathpulse && <RouteRow label="PathPulse route" route={pathpulse} kind="pp" />}
      <RouteRow label={pathpulse ? 'Fastest route' : 'Route'} route={fastest} kind="fast" />
      <p className="explanation" data-testid="route-explanation">
        {explanation ?? templateSummary(routes)}
      </p>
      {routes.message && pathpulse && <p className="faint">{routes.message}</p>}
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
      <TrustNote />
    </section>
  )
}
